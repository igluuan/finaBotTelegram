from typing import Dict, Any

class StateManager:
    def __init__(self):
        # Em produção, use Redis. Aqui usamos memória para simplicidade.
        self._store: Dict[str, Dict[str, Any]] = {}

    def get_state(self, user_id: str) -> str:
        return self._store.get(user_id, {}).get("state", "START")

    def set_state(self, user_id: str, state: str):
        if user_id not in self._store:
            self._store[user_id] = {}
        self._store[user_id]["state"] = state

    def get_data(self, user_id: str) -> dict:
        return self._store.get(user_id, {}).get("data", {})

    def update_data(self, user_id: str, data: dict):
        if user_id not in self._store:
            self._store[user_id] = {"data": {}}
        if "data" not in self._store[user_id]:
            self._store[user_id]["data"] = {}
        self._store[user_id]["data"].update(data)

    def clear_user(self, user_id: str):
        if user_id in self._store:
            del self._store[user_id]

state_manager = StateManager()
