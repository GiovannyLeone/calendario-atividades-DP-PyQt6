"""Modelo de domínio: hierarquia de atividades.

Padrões presentes neste módulo:
  * Prototype  -> ``Activity.clone``
  * Visitor    -> ``Activity.accept`` (elemento visitável)
  * State      -> ``Activity.transition`` (contexto do estado)
  * Memento    -> ``create_memento`` / ``restore_from`` (originator)
  * Decorator  -> ``Activity`` é o componente concreto (ver decorators.py)
"""
from __future__ import annotations

import copy
import uuid
from abc import abstractmethod
from datetime import timedelta

from .decorators import Describable
from .memento import ActivityMemento
from .state import PendingState, apply_action, state_from_name
from .timeutil import DATETIME_FORMAT, parse_date, parse_datetime


def new_id() -> str:
    return uuid.uuid4().hex[:8]


class Activity(Describable):
    kind = "activity"
    kind_label = "Atividade"
    extra_defaults: dict = {}

    def __init__(
        self,
        title,
        start,
        end=None,
        *,
        id=None,
        description="",
        category="Geral",
        priority="medium",
        recurrence="none",
        recurrence_until=None,
        reminder_minutes=None,
        status="pending",
        **extra,
    ):
        self.id = id or new_id()
        self.title = title
        self.description = description
        self.start = start
        self.end = end if end is not None else start
        self.category = category
        self.priority = priority
        self.recurrence = recurrence
        self.recurrence_until = recurrence_until  # date | None
        self.reminder_minutes = reminder_minutes
        self._state = state_from_name(status)
        for name, default in self.extra_defaults.items():
            setattr(self, name, copy.deepcopy(extra.get(name, default)))

    # -- estado (State) ---------------------------------------------------
    @property
    def status(self) -> str:
        return self._state.name

    @property
    def status_label(self) -> str:
        return self._state.label

    def transition(self, action: str) -> None:
        apply_action(self, action)

    # -- utilidades ---------------------------------------------------------
    @property
    def duration_minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)

    def describe(self) -> str:
        return f"{self.start:%H:%M}-{self.end:%H:%M} {self.title}"

    @abstractmethod
    def accept(self, visitor):
        """Visitor: cada subclasse chama o método de visita do seu tipo."""

    def to_dict(self) -> dict:
        data = {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "description": self.description,
            "start": self.start.strftime(DATETIME_FORMAT),
            "end": self.end.strftime(DATETIME_FORMAT),
            "category": self.category,
            "priority": self.priority,
            "recurrence": self.recurrence,
            "recurrence_until": self.recurrence_until.isoformat() if self.recurrence_until else None,
            "reminder_minutes": self.reminder_minutes,
            "status": self.status,
        }
        for name in self.extra_defaults:
            data[name] = copy.deepcopy(getattr(self, name))
        return data

    # -- Prototype --------------------------------------------------------
    def clone(self, days: int = 1) -> "Activity":
        """Cria uma cópia independente deslocada em ``days`` dias."""
        twin = copy.deepcopy(self)
        shift = timedelta(days=days)
        twin.id = new_id()
        twin.title = f"{self.title} (cópia)"
        twin.start = self.start + shift
        twin.end = self.end + shift
        if twin.recurrence_until:
            twin.recurrence_until = self.recurrence_until + shift
        twin._state = PendingState()
        return twin

    # -- Memento (originator) ---------------------------------------------
    def create_memento(self, reason: str) -> ActivityMemento:
        return ActivityMemento.of(self.to_dict(), reason)

    def restore_from(self, memento: ActivityMemento) -> None:
        snap = memento.snapshot
        self.title = snap["title"]
        self.description = snap["description"]
        self.start = parse_datetime(snap["start"])
        self.end = parse_datetime(snap["end"])
        self.category = snap["category"]
        self.priority = snap["priority"]
        self.recurrence = snap["recurrence"]
        self.recurrence_until = (
            parse_date(snap["recurrence_until"]) if snap.get("recurrence_until") else None
        )
        self.reminder_minutes = snap["reminder_minutes"]
        self._state = state_from_name(snap["status"])
        for name, default in self.extra_defaults.items():
            setattr(self, name, copy.deepcopy(snap.get(name, default)))


class Task(Activity):
    kind = "task"
    kind_label = "Tarefa"

    def accept(self, visitor):
        return visitor.visit_task(self)


class Meeting(Activity):
    kind = "meeting"
    kind_label = "Reunião"
    extra_defaults = {"location": "", "attendees": []}

    def accept(self, visitor):
        return visitor.visit_meeting(self)


class Reminder(Activity):
    kind = "reminder"
    kind_label = "Lembrete"

    def describe(self) -> str:
        return f"{self.start:%H:%M} {self.title}"

    def accept(self, visitor):
        return visitor.visit_reminder(self)


class Event(Activity):
    kind = "event"
    kind_label = "Evento"
    extra_defaults = {"location": ""}

    def accept(self, visitor):
        return visitor.visit_event(self)
