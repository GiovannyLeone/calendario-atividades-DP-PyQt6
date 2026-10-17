"""PADRÃO ESTRUTURAL: Decorator.

``Describable`` é o componente; ``Activity`` é o componente concreto.
Cada decorator acrescenta uma informação ao texto exibido da atividade
(prioridade, recorrência, lembrete, status) sem alterar a classe original.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

PRIORITY_LABELS = {"low": "Baixa", "medium": "Média", "high": "Alta"}
RECURRENCE_LABELS = {"daily": "diariamente", "weekly": "semanalmente", "monthly": "mensalmente"}
STATUS_LABELS = {
    "pending": "pendente",
    "in_progress": "em andamento",
    "done": "concluída",
    "cancelled": "cancelada",
}


class Describable(ABC):
    """Componente: algo que sabe se descrever em texto."""

    @abstractmethod
    def describe(self) -> str: ...


class ActivityDecorator(Describable):
    """Decorator base: delega ao componente embrulhado."""

    def __init__(self, wrapped: Describable):
        self._wrapped = wrapped

    def describe(self) -> str:
        return self._wrapped.describe()


class PriorityDecorator(ActivityDecorator):
    def __init__(self, wrapped: Describable, priority: str):
        super().__init__(wrapped)
        self._priority = priority

    def describe(self) -> str:
        return f"[{PRIORITY_LABELS.get(self._priority, self._priority)}] {self._wrapped.describe()}"


class RecurrenceDecorator(ActivityDecorator):
    def __init__(self, wrapped: Describable, recurrence: str):
        super().__init__(wrapped)
        self._recurrence = recurrence

    def describe(self) -> str:
        return f"{self._wrapped.describe()} (repete {RECURRENCE_LABELS.get(self._recurrence, self._recurrence)})"


class ReminderDecorator(ActivityDecorator):
    def __init__(self, wrapped: Describable, minutes: int):
        super().__init__(wrapped)
        self._minutes = minutes

    def describe(self) -> str:
        return f"{self._wrapped.describe()} (lembrar {self._minutes} min antes)"


class StatusDecorator(ActivityDecorator):
    def __init__(self, wrapped: Describable, status: str):
        super().__init__(wrapped)
        self._status = status

    def describe(self) -> str:
        return f"{self._wrapped.describe()} — {STATUS_LABELS.get(self._status, self._status)}"


def build_label(activity) -> str:
    """Empilha os decorators aplicáveis à atividade e devolve o texto final."""
    label: Describable = activity
    if activity.priority == "high":
        label = PriorityDecorator(label, activity.priority)
    if activity.recurrence != "none":
        label = RecurrenceDecorator(label, activity.recurrence)
    if activity.reminder_minutes is not None:
        label = ReminderDecorator(label, activity.reminder_minutes)
    if activity.status != "pending":
        label = StatusDecorator(label, activity.status)
    return label.describe()
