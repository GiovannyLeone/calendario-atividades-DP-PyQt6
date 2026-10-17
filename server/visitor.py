"""PADRÃO COMPORTAMENTAL: Visitor.

Operações novas sobre a hierarquia de atividades sem alterar as classes:
  * ``StatisticsVisitor`` agrega números por tipo, prioridade, status etc.
  * ``DetailsVisitor``    devolve um texto de detalhes específico de cada tipo.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter

from .decorators import PRIORITY_LABELS


class ActivityVisitor(ABC):
    @abstractmethod
    def visit_task(self, task): ...

    @abstractmethod
    def visit_meeting(self, meeting): ...

    @abstractmethod
    def visit_reminder(self, reminder): ...

    @abstractmethod
    def visit_event(self, event): ...


class StatisticsVisitor(ActivityVisitor):
    def __init__(self):
        self.total = 0
        self.total_minutes = 0
        self.attendees = 0
        self.by_kind: Counter = Counter()
        self.minutes_by_kind: Counter = Counter()
        self.by_priority: Counter = Counter()
        self.by_status: Counter = Counter()
        self.by_category: Counter = Counter()

    def _register(self, activity) -> None:
        self.total += 1
        self.total_minutes += activity.duration_minutes
        self.by_kind[activity.kind] += 1
        self.minutes_by_kind[activity.kind] += activity.duration_minutes
        self.by_priority[activity.priority] += 1
        self.by_status[activity.status] += 1
        self.by_category[activity.category.split("/")[0]] += 1

    def visit_task(self, task):
        self._register(task)

    def visit_meeting(self, meeting):
        self._register(meeting)
        self.attendees += len(meeting.attendees)

    def visit_reminder(self, reminder):
        self._register(reminder)

    def visit_event(self, event):
        self._register(event)

    def result(self) -> dict:
        return {
            "total": self.total,
            "total_minutes": self.total_minutes,
            "meeting_attendees": self.attendees,
            "by_kind": dict(self.by_kind),
            "minutes_by_kind": dict(self.minutes_by_kind),
            "by_priority": dict(self.by_priority),
            "by_status": dict(self.by_status),
            "by_category": dict(self.by_category),
        }


class DetailsVisitor(ActivityVisitor):
    def visit_task(self, task):
        return f"Tarefa · prioridade {PRIORITY_LABELS[task.priority].lower()}"

    def visit_meeting(self, meeting):
        parts = ["Reunião"]
        if meeting.location:
            parts.append(f"local: {meeting.location}")
        if meeting.attendees:
            parts.append(f"{len(meeting.attendees)} participante(s)")
        return " · ".join(parts)

    def visit_reminder(self, reminder):
        return f"Lembrete às {reminder.start:%H:%M}"

    def visit_event(self, event):
        parts = ["Evento"]
        if event.location:
            parts.append(f"local: {event.location}")
        return " · ".join(parts)
