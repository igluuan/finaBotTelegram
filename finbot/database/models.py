from sqlalchemy import Column, Integer, String, Float, DateTime, Date, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()

class Card(Base):
    __tablename__ = "cards"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.telegram_id'), nullable=False)
    last_digits = Column(String(4), nullable=False)  # Ex: 1234
    name = Column(String(50)) # Ex: Nubank, Inter (Optional)
    type = Column(String(20)) # credit, debit, both
    created_at = Column(DateTime, default=func.now())

    user = relationship("User", back_populates="cards")

class User(Base):
    __tablename__ = 'users'
    telegram_id = Column(Integer, primary_key=True)
    name = Column(String)
    currency = Column(String, default='BRL')
    closing_day = Column(Integer, default=1)
    phone = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())

    expenses = relationship("Expense", back_populates="user")
    categories = relationship("Category", back_populates="user")
    budgets = relationship("Budget", back_populates="user")
    cards = relationship("Card", back_populates="user")

class Installment(Base):
    __tablename__ = "installments"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    user_id          = Column(Integer, nullable=False, index=True)
    card_last_digits = Column(String(4), nullable=False)
    description      = Column(String(255), nullable=False)
    total_amount     = Column(Float, nullable=False)
    installment_amount = Column(Float, nullable=False)   # calculated: total_amount / total_installments
    total_installments = Column(Integer, nullable=False)
    current_installment = Column(Integer, nullable=False)
    due_day          = Column(Integer, nullable=False)
    start_date       = Column(Date, nullable=False)
    is_paid          = Column(Boolean, default=False)
    created_at       = Column(DateTime, default=func.now())

    @property
    def remaining_installments(self):
        return self.total_installments - self.current_installment

    @property
    def remaining_amount(self):
        return self.installment_amount * (self.total_installments - self.current_installment + 1)

class Category(Base):
    __tablename__ = 'categories'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.telegram_id'))
    name = Column(String)
    emoji = Column(String)
    monthly_budget = Column(Float, default=0)

    user = relationship("User", back_populates="categories")

class Expense(Base):
    __tablename__ = 'expenses'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.telegram_id'))
    amount = Column(Float, nullable=False)
    category = Column(String, nullable=False)
    description = Column(String)
    payment_method = Column(String)  # New field: pix, cash, debit, credit(1234)
    date = Column(Date, default=func.current_date())
    created_at = Column(DateTime, default=func.now())

    user = relationship("User", back_populates="expenses")

class Budget(Base):
    __tablename__ = 'budgets'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.telegram_id'))
    category = Column(String)
    month = Column(Integer)
    year = Column(Integer)
    limit = Column(Float)

    user = relationship("User", back_populates="budgets")

class Earning(Base):
    __tablename__ = "earnings"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    user_id     = Column(Integer, nullable=False, index=True)
    amount      = Column(Float, nullable=False)
    category    = Column(String(50), nullable=False)  # salary, freelance, investment, others
    description = Column(String(255))
    is_recurring = Column(Boolean, default=False)      # repeat every month?
    receipt_day = Column(Integer, nullable=True)       # day of month (if recurring)
    date        = Column(Date, default=func.current_date())
    created_at  = Column(DateTime, default=func.now())
