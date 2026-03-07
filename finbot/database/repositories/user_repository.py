from typing import Optional
from sqlalchemy.orm import Session
from finbot.database.models import User

class UserRepository:
    @staticmethod
    def get_by_telegram_id(db: Session, telegram_id: int) -> Optional[User]:
        return db.query(User).filter(User.telegram_id == telegram_id).first()

    @staticmethod
    def create(db: Session, telegram_id: int, name: str) -> User:
        user = User(telegram_id=telegram_id, name=name)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def update_closing_day(db: Session, telegram_id: int, closing_day: int):
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if user:
            user.closing_day = closing_day
            db.commit()

    @staticmethod
    def get_by_phone(db: Session, phone: str) -> Optional[User]:
        return db.query(User).filter(User.phone == phone).first()

    @staticmethod
    def get_or_create_by_phone(db: Session, phone: str, name: str = "WhatsApp User") -> User:
        user = UserRepository.get_by_phone(db, phone)
        if not user:
            # Generate a fake negative telegram_id to avoid collision with real IDs
            # Limit to 2^31 to ensure it fits in Integers
            fake_id = (abs(hash(phone)) % (2**31)) * -1
            user = User(
                telegram_id=fake_id,
                name=name,
                phone=phone
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user
