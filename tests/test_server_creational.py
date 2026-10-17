"""Padrões criacionais do servidor: Singleton, Factory Method, Builder, Prototype."""
from datetime import datetime

import pytest

from server.activity import Event, Meeting, Reminder, Task
from server.builder import ActivityBuilder
from server.errors import ValidationError
from server.factory import create_activity, creator_for
from server.repository import ActivityRepository


def test_singleton_returns_same_instance(tmp_path):
    ActivityRepository.reset()
    first = ActivityRepository(tmp_path / "a.json")
    second = ActivityRepository(tmp_path / "outro.json")  # argumento ignorado
    assert first is second
    ActivityRepository.reset()
    assert ActivityRepository(tmp_path / "b.json") is not first
    ActivityRepository.reset()


@pytest.mark.parametrize(
    "kind, cls, minutes",
    [("task", Task, 30), ("meeting", Meeting, 60), ("event", Event, 120)],
)
def test_factory_method_creates_right_class_with_default_duration(kind, cls, minutes):
    activity = create_activity({"kind": kind, "title": "X", "start": "2026-10-08T09:00"})
    assert isinstance(activity, cls)
    assert activity.duration_minutes == minutes


def test_factory_reminder_is_instantaneous():
    activity = create_activity(
        {"kind": "reminder", "title": "Pagar", "start": "2026-10-08T09:00", "end": "2026-10-08T12:00"}
    )
    assert isinstance(activity, Reminder)
    assert activity.start == activity.end


def test_factory_meeting_specific_fields_accept_csv_attendees():
    activity = create_activity(
        {"kind": "meeting", "title": "M", "start": "2026-10-08T09:00", "attendees": "Ana, Bia ,", "location": " Sala 2 "}
    )
    assert activity.attendees == ["Ana", "Bia"]
    assert activity.location == "Sala 2"


def test_factory_rejects_unknown_kind():
    with pytest.raises(ValidationError):
        creator_for("inexistente")


def test_builder_fluent_interface_normalizes_values():
    activity = (
        ActivityBuilder(Task)
        .with_title("  Estudar  ")
        .in_category(" Estudos / Python ")
        .starting_at("2026-10-08T09:00")
        .lasting(45)
        .repeating("weekly", "2026-12-01")
        .reminding("10")
        .build()
    )
    assert activity.title == "Estudar"
    assert activity.category == "Estudos/Python"
    assert activity.end == datetime(2026, 10, 8, 9, 45)
    assert activity.recurrence == "weekly" and activity.recurrence_until.isoformat() == "2026-12-01"
    assert activity.reminder_minutes == 10


def test_builder_requires_valid_start_and_reminder():
    with pytest.raises(ValidationError):
        ActivityBuilder(Task).with_title("x").build()
    with pytest.raises(ValidationError):
        ActivityBuilder(Task).starting_at("ontem")
    with pytest.raises(ValidationError):
        ActivityBuilder(Task).reminding("abc")


def test_prototype_clone_is_independent_copy():
    original = create_activity(
        {"kind": "meeting", "title": "Sprint", "start": "2026-10-08T09:00", "attendees": ["Ana"], "status": "in_progress"}
    )
    twin = original.clone(days=7)
    assert twin.id != original.id
    assert twin.title == "Sprint (cópia)"
    assert twin.start == datetime(2026, 10, 15, 9, 0)
    assert twin.status == "pending"
    twin.attendees.append("Bia")
    assert original.attendees == ["Ana"]  # cópia profunda
