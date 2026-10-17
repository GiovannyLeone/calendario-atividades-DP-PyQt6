"""PADRÃO COMPORTAMENTAL: Memento.

``ActivityMemento`` guarda um instantâneo imutável do estado de uma atividade
(o *originator* é ``Activity``). ``HistoryCaretaker`` guarda os mementos por
atividade sem conhecer seu conteúdo e permite desfazer alterações/exclusões.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ActivityMemento:
    snapshot: dict
    reason: str  # "update" ou "delete"
    saved_at: str

    @classmethod
    def of(cls, snapshot: dict, reason: str) -> "ActivityMemento":
        return cls(copy.deepcopy(snapshot), reason, datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))


class HistoryCaretaker:
    def __init__(self):
        self._stacks: dict[str, list[ActivityMemento]] = {}

    def save(self, activity_id: str, memento: ActivityMemento) -> None:
        self._stacks.setdefault(activity_id, []).append(memento)

    def pop_last(self, activity_id: str, reason: str) -> ActivityMemento | None:
        """Remove e devolve o memento mais recente com o motivo informado."""
        stack = self._stacks.get(activity_id, [])
        for index in range(len(stack) - 1, -1, -1):
            if stack[index].reason == reason:
                return stack.pop(index)
        return None

    def entries(self, activity_id: str) -> list[dict]:
        return [
            {"reason": m.reason, "saved_at": m.saved_at, "snapshot": copy.deepcopy(m.snapshot)}
            for m in reversed(self._stacks.get(activity_id, []))
        ]
