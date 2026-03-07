from typing import List, Optional
from datetime import datetime
from sqlalchemy import func, extract
from sqlalchemy.orm import Session
from finbot.core.config import TIMEZONE
from finbot.database.models import Earning

def get_today():
    return datetime.now(TIMEZONE).date() if TIMEZONE else datetime.now().date()

class EarningRepository:
    @staticmethod
    def create(db: Session, user_id: int, data: dict) -> Earning:
        date_record = data.get("date")
        final_date = date_record or get_today()
        
        earning = Earning(
            user_id         = user_id,
            amount          = data["amount"],
            category        = data["category"],
            description     = data["description"],
            is_recurring    = data.get("is_recurring", False),
            receipt_day     = data.get("receipt_day"),
            date            = final_date,
        )
        db.add(earning)
        db.commit()
        db.refresh(earning)
        return earning

    @staticmethod
    def get_current_month_earnings(db: Session, user_id: int) -> List[Earning]:
        today = get_today()
        start_date = today.replace(day=1)
        return db.query(Earning).filter(
            Earning.user_id == user_id,
            Earning.date >= start_date
        ).order_by(Earning.date.desc()).all()

    @staticmethod
    def get_current_month_total(db: Session, user_id: int) -> float:
        today = get_today()
        start_date = today.replace(day=1)
        result = db.query(func.sum(Earning.amount)).filter(
            Earning.user_id == user_id,
            Earning.date >= start_date
        ).scalar()
        return result if result else 0.0

    @staticmethod
    def get_recurring_by_day(db: Session, day: int) -> List[Earning]:
        return db.query(Earning).filter(
            Earning.is_recurring == True,
            Earning.receipt_day == day
        ).all()

    @staticmethod
    def exists_in_month(db: Session, user_id: int, description: str, month: int, year: int) -> bool:
        return db.query(Earning).filter(
            Earning.user_id == user_id,
            Earning.description == description,
            extract('month', Earning.date) == month,
            extract('year', Earning.date) == year
        ).count() > 0
