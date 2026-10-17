"""PADRÃO COMPORTAMENTAL: Chain of Responsibility.

Cada validador é um elo da corrente: examina a atividade, registra um erro
(se houver) e repassa ao próximo. O último elo (conflito de horários) decide
não agir quando já existem erros anteriores.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

PRIORITIES = ("low", "medium", "high")
RECURRENCES = ("none", "daily", "weekly", "monthly")


@dataclass
class ValidationContext:
    store: object  # qualquer objeto com .all()
    errors: list = field(default_factory=list)


class Validator(ABC):
    def __init__(self):
        self._next: Validator | None = None

    def set_next(self, nxt: "Validator") -> "Validator":
        self._next = nxt
        return nxt

    def handle(self, activity, context: ValidationContext) -> None:
        self.check(activity, context)
        if self._next is not None:
            self._next.handle(activity, context)

    @abstractmethod
    def check(self, activity, context: ValidationContext) -> None: ...


class TitleValidator(Validator):
    def check(self, activity, context):
        if not activity.title:
            context.errors.append("O título é obrigatório")
        elif len(activity.title) > 80:
            context.errors.append("O título deve ter no máximo 80 caracteres")


class EnumValidator(Validator):
    def check(self, activity, context):
        if activity.priority not in PRIORITIES:
            context.errors.append(f"Prioridade inválida: {activity.priority!r}")
        if activity.recurrence not in RECURRENCES:
            context.errors.append(f"Recorrência inválida: {activity.recurrence!r}")


class TimeRangeValidator(Validator):
    def check(self, activity, context):
        if activity.kind == "reminder":
            return
        if activity.end <= activity.start:
            context.errors.append("O término deve ser posterior ao início")
        elif activity.duration_minutes > 24 * 60:
            context.errors.append("A duração máxima de uma atividade é de 24 horas")


class DuplicateValidator(Validator):
    """Rejeita atividade idêntica (mesmo tipo, título, início e término) a outra já existente."""

    def check(self, activity, context):
        if context.errors:
            return
        title = activity.title.casefold()
        for other in context.store.all():
            if (
                other.id != activity.id
                and other.kind == activity.kind
                and other.title.casefold() == title
                and other.start == activity.start
                and other.end == activity.end
            ):
                context.errors.append(
                    f"Já existe uma atividade idêntica: '{other.title}' em {other.start:%d/%m/%Y %H:%M}"
                )
                return


class RecurrenceValidator(Validator):
    def check(self, activity, context):
        if activity.recurrence == "none":
            return
        until = activity.recurrence_until
        if until is not None and until < activity.start.date():
            context.errors.append("A data final da recorrência não pode ser anterior ao início")


class ReminderValidator(Validator):
    def check(self, activity, context):
        minutes = activity.reminder_minutes
        if minutes is not None and not 0 <= minutes <= 7 * 24 * 60:
            context.errors.append("A antecedência do lembrete deve estar entre 0 e 10080 minutos")


class ConflictValidator(Validator):
    """Reuniões não podem se sobrepor no horário."""

    def check(self, activity, context):
        if context.errors or activity.kind != "meeting":
            return
        for other in context.store.all():
            if other.kind != "meeting" or other.id == activity.id or other.status == "cancelled":
                continue
            if activity.start < other.end and other.start < activity.end:
                context.errors.append(
                    f"Conflito de horário com a reunião '{other.title}' "
                    f"({other.start:%d/%m %H:%M}-{other.end:%H:%M})"
                )


def build_validation_chain() -> Validator:
    head = TitleValidator()
    (
        head.set_next(EnumValidator())
        .set_next(TimeRangeValidator())
        .set_next(RecurrenceValidator())
        .set_next(ReminderValidator())
        .set_next(DuplicateValidator())
        .set_next(ConflictValidator())
    )
    return head


def validate_activity(activity, store) -> list[str]:
    context = ValidationContext(store)
    build_validation_chain().handle(activity, context)
    return context.errors
