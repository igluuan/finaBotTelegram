from typing import List, Dict, Optional
from datetime import date, timedelta
from sqlalchemy import func, extract
from sqlalchemy.orm import Session
from finbot.database.models import Expense

class ExpenseRepository:
    @staticmethod
    def create(
        db: Session, 
        user_id: int, 
        amount: float, 
        category: str, 
        description: str, 
        payment_method: Optional[str] = None, 
        date_record: Optional[date] = None
    ) -> Expense:
        final_date = date_record or date.today()
        expense = Expense(
            user_id=user_id,
            amount=amount,
            category=category,
            description=description,
            payment_method=payment_method,
            date=final_date
        )
        db.add(expense)
        db.commit()
        db.refresh(expense)
        return expense

    @staticmethod
    def get_by_period(db: Session, user_id: int, start_date: date, end_date: date) -> List[Expense]:
        return db.query(Expense).filter(
            Expense.user_id == user_id,
            Expense.date >= start_date,
            Expense.date <= end_date
        ).all()

    @staticmethod
    def get_by_month(db: Session, user_id: int, month: int, year: int) -> List[Expense]:
        return db.query(Expense).filter(
            Expense.user_id == user_id,
            extract('month', Expense.date) == month,
            extract('year', Expense.date) == year
        ).all()

    @staticmethod
    def get_total_by_month(db: Session, user_id: int, month: int, year: int) -> float:
        result = db.query(func.sum(Expense.amount)).filter(
            Expense.user_id == user_id,
            extract('month', Expense.date) == month,
            extract('year', Expense.date) == year
        ).scalar()
        return result if result else 0.0

    @staticmethod
    def get_by_category_monthly(db: Session, user_id: int, month: int, year: int) -> List[Dict]:
        results = db.query(
            Expense.category,
            func.sum(Expense.amount).label('total')
        ).filter(
            Expense.user_id == user_id,
            extract('month', Expense.date) == month,
            extract('year', Expense.date) == year
        ).group_by(Expense.category).all()
        
        return [{"category": r[0], "total": r[1]} for r in results]

    @staticmethod
    def delete_last(db: Session, user_id: int) -> Optional[Expense]:
        last_expense = db.query(Expense).filter(Expense.user_id == user_id).order_by(Expense.id.desc()).first()
        if last_expense:
            db.delete(last_expense)
            db.commit()
            return last_expense
        return None

    @staticmethod
    def get_category_history(db: Session, user_id: int, category: str, days: int = 30) -> List[Expense]:
        limit_date = date.today() - timedelta(days=days)
        return db.query(Expense).filter(
            Expense.user_id == user_id,
            Expense.category == category,
            Expense.date >= limit_date
        ).all()

    @staticmethod
    def get_current_month_total(db: Session, user_id: int) -> float:
        today = date.today()
        # Filter from the first day of the current month
        start_date = today.replace(day=1)
        result = db.query(func.sum(Expense.amount)).filter(
            Expense.user_id == user_id,
            Expense.date >= start_date
        ).scalar()
        return result if result else 0.0
