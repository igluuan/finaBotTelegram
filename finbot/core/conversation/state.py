from typing import List, Dict, Any, Optional
import time
from dataclasses import dataclass, field

@dataclass
class ConversationState:
    user_id: str
    state: str = "START"
    transaction_draft: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, str]] = field(default_factory=list)
    last_updated: float = field(default_factory=time.time)

    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        # Keep only last 10 messages to save tokens
        if len(self.history) > 10:
            self.history = self.history[-10:]
        self.last_updated = time.time()

    def update_draft(self, data: Dict[str, Any]):
        self.transaction_draft.update(data)
        self.last_updated = time.time()

    def clear_draft(self):
        self.transaction_draft = {}
        self.last_updated = time.time()

class StateManager:
    def __init__(self):
        # In-memory store. In production, this should be Redis.
        self._store: Dict[str, ConversationState] = {}

    def get_state(self, user_id: str) -> ConversationState:
        if user_id not in self._store:
            self._store[user_id] = ConversationState(user_id=user_id)
        return self._store[user_id]

    def set_state(self, user_id: str, state: str):
        conversation = self.get_state(user_id)
        conversation.state = state
        conversation.last_updated = time.time()
    
    def update_data(self, user_id: str, data: dict):
        conversation = self.get_state(user_id)
        conversation.update_draft(data)
    
    def clear_user(self, user_id: str):
        if user_id in self._store:
            del self._store[user_id]

# Singleton instance
conversation_state_manager = StateManager()
