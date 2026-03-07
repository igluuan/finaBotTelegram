from typing import List, Optional, Dict
from datetime import datetime
from sqlalchemy.orm import Session
from finbot.core.config import TIMEZONE
from finbot.database.models import Installment

def get_today():
    return datetime.now(TIMEZONE).date() if TIMEZONE else datetime.now().date()

class InstallmentRepository:
    @staticmethod
    def create(db: Session, user_id: int, data: Dict) -> Installment:
        total_installments = data["total_installments"]
        total_amount = data["total_amount"]
        installment_amount = round(total_amount / total_installments, 2)
        
        installment = Installment(
            user_id             = user_id,
            card_last_digits    = data["card_last_digits"],
            description         = data["description"],
            total_amount        = total_amount,
            installment_amount  = installment_amount,
            total_installments  = total_installments,
            current_installment = data["current_installment"],
            due_day             = data["due_day"],
            start_date          = get_today(),
        )
        db.add(installment)
        db.commit()
        db.refresh(installment)
        return installment

    @staticmethod
    def get_active_installments(db: Session, user_id: int, card_last_digits: Optional[str] = None) -> List[Installment]:
        query = db.query(Installment).filter(
            Installment.user_id == user_id,
            Installment.is_paid == False
        )
        if card_last_digits:
            query = query.filter(Installment.card_last_digits == card_last_digits)
        return query.order_by(Installment.card_last_digits, Installment.due_day).all()

    @staticmethod
    def get_all_active(db: Session) -> List[Installment]:
        return db.query(Installment).filter(
            Installment.is_paid == False
        ).all()

    @staticmethod
    def mark_as_paid(db: Session, installment_id: int, user_id: int) -> bool:
        installment = db.query(Installment).filter(
            Installment.id == installment_id,
            Installment.user_id == user_id
        ).first()
        if not installment:
            return False
        installment.is_paid = True
        db.commit()
        return True

    @staticmethod
    def get_monthly_total(db: Session, user_id: int) -> float:
        installments = InstallmentRepository.get_active_installments(db, user_id)
        return sum(p.installment_amount for p in installments)
