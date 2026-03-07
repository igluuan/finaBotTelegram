from typing import List, Dict
from sqlalchemy import func, extract
from sqlalchemy.orm import Session
from finbot.database.models import Budget, Expense

class BudgetRepository:
    @staticmethod
    def set_budget(db: Session, user_id: int, category: str, month: int, year: int, limit: float):
        budget = db.query(Budget).filter(
            Budget.user_id == user_id,
            Budget.category == category,
            Budget.month == month,
            Budget.year == year
        ).first()
        
        if budget:
            budget.limit = limit
        else:
            budget = Budget(user_id=user_id, category=category, month=month, year=year, limit=limit)
            db.add(budget)
        db.commit()

    @staticmethod
    def get_status(db: Session, user_id: int, month: int, year: int) -> List[Dict]:
        # Fetch expenses grouped by category
        expenses_query = db.query(
            Expense.category,
            func.sum(Expense.amount).label('total')
        ).filter(
            Expense.user_id == user_id,
            extract('month', Expense.date) == month,
            extract('year', Expense.date) == year
        ).group_by(Expense.category).all()
        
        expenses_map = {r.category: r.total for r in expenses_query}
        
        # Fetch budgets for the month
        budgets_query = db.query(Budget).filter(
            Budget.user_id == user_id,
            Budget.month == month,
            Budget.year == year
        ).all()
        
        budgets_map = {b.category: b.limit for b in budgets_query}
        
        # Combine categories
        all_categories = set(expenses_map.keys()) | set(budgets_map.keys())
        
        stats = []
        for cat in all_categories:
            total_spent = expenses_map.get(cat, 0.0)
            limit = budgets_map.get(cat, 0.0)
            percentage = (total_spent / limit * 100) if limit > 0 else 0
            
            stats.append({
                "category": cat,
                "spent": total_spent,
                "limit": limit,
                "percentage": percentage
            })
            
        return stats
