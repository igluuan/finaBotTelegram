from typing import List, Optional
from sqlalchemy.orm import Session
from finbot.database.models import Card, Installment

class CardRepository:
    @staticmethod
    def create(db: Session, user_id: int, last_digits: str, name: Optional[str] = None, type: str = "both") -> Card:
        existing = db.query(Card).filter(
            Card.user_id == user_id,
            Card.last_digits == last_digits
        ).first()
        if existing:
            return existing
        
        card = Card(user_id=user_id, last_digits=last_digits, name=name, type=type)
        db.add(card)
        db.commit()
        db.refresh(card)
        return card

    @staticmethod
    def get_all(db: Session, user_id: int) -> List[Card]:
        return db.query(Card).filter(Card.user_id == user_id).all()

    @staticmethod
    def delete(db: Session, user_id: int, last_digits: str) -> bool:
        card = db.query(Card).filter(
            Card.user_id == user_id, 
            Card.last_digits == last_digits
        ).first()
        if card:
            db.delete(card)
            db.commit()
            return True
        return False

    @staticmethod
    def get_unique_used_cards(db: Session, user_id: int) -> List[str]:
        """Returns list of unique card last digits used by the user in installments."""
        cards = db.query(Installment.card_last_digits).filter(
            Installment.user_id == user_id
        ).distinct().all()
        return [c[0] for c in cards if c[0]]
