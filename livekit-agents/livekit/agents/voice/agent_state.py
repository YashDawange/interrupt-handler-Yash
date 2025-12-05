from __future__ import annotations

class AgentState:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgentState, cls).__new__(cls)
            cls._instance.speaking = False
        return cls._instance

    @classmethod
    def get_instance(cls) -> AgentState:
        if cls._instance is None:
            cls()
        return cls._instance
