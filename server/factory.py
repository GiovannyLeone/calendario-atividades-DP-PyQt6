"""PADRÃO CRIACIONAL: Factory Method.

``ActivityCreator`` declara o método de fábrica ``make_activity``; cada
criador concreto decide a classe a instanciar e seus valores padrão
(duração, campos específicos). O ``ActivityBuilder`` faz a montagem.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from .activity import Activity, Event, Meeting, Reminder, Task
from .builder import ActivityBuilder
from .errors import ValidationError


def _as_list(value) -> list:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [str(item).strip() for item in value if str(item).strip()]


class ActivityCreator(ABC):
    activity_class: type[Activity]
    default_minutes = 30

    def create(self, data: dict) -> Activity:
        """Operação do criador: depende do método de fábrica."""
        activity = self.make_activity(data)
        assert isinstance(activity, self.activity_class)
        return activity

    @abstractmethod
    def make_activity(self, data: dict) -> Activity:
        """Factory Method."""

    def _prepare(self, data: dict) -> ActivityBuilder:
        builder = (
            ActivityBuilder(self.activity_class)
            .with_id(data.get("id"))
            .with_title(data.get("title"))
            .described_as(data.get("description"))
            .in_category(data.get("category"))
            .with_priority(data.get("priority"))
            .starting_at(data.get("start"))
            .repeating(data.get("recurrence"), data.get("recurrence_until"))
            .reminding(data.get("reminder_minutes"))
            .with_status(data.get("status"))
        )
        if data.get("end"):
            builder.ending_at(data["end"])
        else:
            builder.lasting(self.default_minutes)
        return builder


class TaskCreator(ActivityCreator):
    activity_class = Task
    default_minutes = 30

    def make_activity(self, data):
        return self._prepare(data).build()


class MeetingCreator(ActivityCreator):
    activity_class = Meeting
    default_minutes = 60

    def make_activity(self, data):
        return (
            self._prepare(data)
            .with_extra(
                location=(data.get("location") or "").strip(),
                attendees=_as_list(data.get("attendees")),
            )
            .build()
        )


class ReminderCreator(ActivityCreator):
    activity_class = Reminder
    default_minutes = 0

    def make_activity(self, data):
        # lembrete é pontual: o término sempre coincide com o início
        data = {**data, "end": None}
        return self._prepare(data).lasting(0).build()


class EventCreator(ActivityCreator):
    activity_class = Event
    default_minutes = 120

    def make_activity(self, data):
        return (
            self._prepare(data)
            .with_extra(location=(data.get("location") or "").strip())
            .build()
        )


_CREATORS: dict[str, ActivityCreator] = {
    creator.activity_class.kind: creator
    for creator in (TaskCreator(), MeetingCreator(), ReminderCreator(), EventCreator())
}

KINDS = tuple(_CREATORS)


def creator_for(kind: str) -> ActivityCreator:
    try:
        return _CREATORS[kind]
    except KeyError:
        raise ValidationError(
            f"Tipo de atividade desconhecido: {kind!r}. Use: {', '.join(KINDS)}"
        ) from None


def create_activity(data: dict) -> Activity:
    return creator_for(data.get("kind") or "task").create(data)
