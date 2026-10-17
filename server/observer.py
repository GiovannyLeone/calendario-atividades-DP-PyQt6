"""PADRÃO COMPORTAMENTAL: Observer.

``Observable`` (sujeito) é herdado pelo repositório, que notifica um
``ChangeEvent`` a cada criação/alteração/exclusão. ``NotificationCenter`` é
um observador que transforma eventos em mensagens legíveis.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ChangeEvent:
    kind: str  # created | updated | deleted
    activity_id: str
    title: str
    at: str

    @classmethod
    def now(cls, kind: str, activity_id: str, title: str) -> "ChangeEvent":
        return cls(kind, activity_id, title, datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))


class Observer(ABC):
    @abstractmethod
    def update(self, event: ChangeEvent) -> None: ...


class Observable:
    def __init__(self):
        self._observers: list[Observer] = []

    def subscribe(self, observer: Observer) -> None:
        if observer not in self._observers:
            self._observers.append(observer)

    def unsubscribe(self, observer: Observer) -> None:
        if observer in self._observers:
            self._observers.remove(observer)

    def notify(self, event: ChangeEvent) -> None:
        for observer in list(self._observers):
            observer.update(event)


class NotificationCenter(Observer):
    _VERBS = {"created": "criada", "updated": "atualizada", "deleted": "excluída"}

    def __init__(self, limit: int = 50):
        self._messages: deque = deque(maxlen=limit)

    def update(self, event: ChangeEvent) -> None:
        verb = self._VERBS.get(event.kind, event.kind)
        self._messages.appendleft(
            {
                "at": event.at,
                "kind": event.kind,
                "activity_id": event.activity_id,
                "message": f"Atividade '{event.title}' {verb}",
            }
        )

    def messages(self) -> list[dict]:
        return list(self._messages)
