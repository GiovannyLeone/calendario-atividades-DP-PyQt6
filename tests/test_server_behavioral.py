"""Padrões comportamentais do servidor."""
from datetime import date, datetime

import pytest

from server.errors import InvalidTransition, QuerySyntaxError, ValidationError
from server.factory import create_activity
from server.interpreter import parse_query
from server.iterators import DateRangeIterator, OccurrenceIterator
from server.memento import HistoryCaretaker
from server.observer import NotificationCenter
from server.repository import ActivityRepository
from server.strategy import SORT_STRATEGIES, ActivitySorter
from server.validation import validate_activity
from server.visitor import DetailsVisitor, StatisticsVisitor


def make(**data):
    base = {"kind": "task", "title": "T", "start": "2026-10-08T09:00"}
    base.update(data)
    return create_activity(base)


class FakeStore:
    def __init__(self, items=()):
        self._items = list(items)

    def all(self):
        return self._items


# ---------------------------------------------------------------------- State
def test_state_valid_transitions_cycle():
    task = make()
    assert task.status == "pending"
    task.transition("start")
    assert task.status == "in_progress"
    task.transition("pause")
    assert task.status == "pending"
    task.transition("complete")
    assert task.status == "done"
    task.transition("reopen")
    assert task.status == "pending"
    task.transition("cancel")
    assert task.status == "cancelled"


@pytest.mark.parametrize(
    "status, action",
    [("pending", "reopen"), ("pending", "pause"), ("done", "start"), ("done", "cancel"), ("cancelled", "complete")],
)
def test_state_invalid_transitions_are_refused(status, action):
    task = make(status=status)
    with pytest.raises(InvalidTransition):
        task.transition(action)
    assert task.status == status


def test_state_unknown_action():
    with pytest.raises(ValidationError):
        make().transition("explodir")


# ----------------------------------------------------- Chain of Responsibility
def test_chain_collects_errors_from_several_links():
    activity = make(title="", priority="urgent", end="2026-10-08T08:00", reminder_minutes=-5)
    errors = validate_activity(activity, FakeStore())
    joined = " | ".join(errors)
    assert "título" in joined and "Prioridade" in joined
    assert "posterior ao início" in joined and "antecedência" in joined


def test_chain_conflict_detection_between_meetings():
    existing = make(kind="meeting", title="Existente", start="2026-10-08T10:00", end="2026-10-08T11:00")
    store = FakeStore([existing])
    clash = make(kind="meeting", title="Nova", start="2026-10-08T10:30", end="2026-10-08T11:30")
    assert any("Conflito" in e for e in validate_activity(clash, store))
    adjacent = make(kind="meeting", title="Nova", start="2026-10-08T11:00", end="2026-10-08T12:00")
    assert validate_activity(adjacent, store) == []
    task_same_time = make(title="Tarefa", start="2026-10-08T10:00", end="2026-10-08T11:00")
    assert validate_activity(task_same_time, store) == []
    assert validate_activity(existing, store) == []  # ignora a si mesma


def test_chain_recurrence_until_before_start_and_long_duration():
    bad_rec = make(recurrence="daily", recurrence_until="2026-10-01")
    assert any("recorrência" in e for e in validate_activity(bad_rec, FakeStore()))
    too_long = make(end="2026-10-10T09:00")
    assert any("24 horas" in e for e in validate_activity(too_long, FakeStore()))


# ------------------------------------------------------------------- Iterator
def test_date_range_iterator_is_inclusive():
    days = list(DateRangeIterator(date(2026, 10, 30), date(2026, 11, 2)))
    assert days == [date(2026, 10, 30), date(2026, 10, 31), date(2026, 11, 1), date(2026, 11, 2)]


def occurrences(activity, start, end):
    return [s for s, _ in OccurrenceIterator(activity, start, end)]


def test_occurrence_iterator_single_and_window():
    activity = make()
    assert occurrences(activity, date(2026, 10, 1), date(2026, 10, 31)) == [datetime(2026, 10, 8, 9, 0)]
    assert occurrences(activity, date(2026, 10, 9), date(2026, 10, 31)) == []
    assert occurrences(activity, date(2026, 10, 8), date(2026, 10, 8)) == [datetime(2026, 10, 8, 9, 0)]


def test_occurrence_iterator_weekly_with_until():
    activity = make(recurrence="weekly", recurrence_until="2026-10-22")
    got = occurrences(activity, date(2026, 10, 1), date(2026, 12, 31))
    assert [d.day for d in got] == [8, 15, 22]


def test_occurrence_iterator_daily_starts_inside_window():
    activity = make(start="2026-01-01T08:00", recurrence="daily")
    got = occurrences(activity, date(2026, 10, 8), date(2026, 10, 10))
    assert [d.date() for d in got] == [date(2026, 10, 8), date(2026, 10, 9), date(2026, 10, 10)]


def test_occurrence_iterator_monthly_clamps_end_of_month():
    activity = make(start="2026-01-31T08:00", recurrence="monthly")
    got = occurrences(activity, date(2026, 1, 1), date(2026, 4, 30))
    assert [(d.month, d.day) for d in got] == [(1, 31), (2, 28), (3, 31), (4, 30)]


def test_occurrence_iterator_multi_day_activity_overlaps_window():
    activity = make(start="2026-10-08T22:00", end="2026-10-09T02:00")
    assert len(occurrences(activity, date(2026, 10, 9), date(2026, 10, 9))) == 1


# ---------------------------------------------------------------- Interpreter
def matches(query, activity):
    return parse_query(query).interpret(activity)


def test_interpreter_terms_and_operators():
    meeting = make(kind="meeting", title="Planejamento da sprint", category="Trabalho/Reuniões", priority="high")
    assert matches("priority:high", meeting)
    assert matches("priority:high AND kind:meeting", meeting)
    assert not matches("priority:low OR kind:task", meeting)
    assert matches("NOT kind:task", meeting)
    assert matches("category:Trabalho", meeting)  # prefixo da árvore de categorias
    assert not matches("category:Reuniões", meeting)
    assert matches("sprint", meeting) and matches("SPRINT planejamento", meeting)  # AND implícito
    assert matches('title:"da sprint"', meeting)
    assert matches("date:2026-10-08", meeting)


def test_interpreter_precedence_and_parentheses():
    task = make(priority="low", status="done")
    # AND tem precedência sobre OR
    assert matches("priority:high AND status:pending OR status:done", task)
    assert not matches("priority:high AND (status:pending OR status:done)", task)
    assert matches("NOT (priority:high OR kind:meeting)", task)


@pytest.mark.parametrize("query", ["", "   ", "(priority:high", "priority:high AND", "AND x", "foo:bar", "a ) b"])
def test_interpreter_syntax_errors(query):
    with pytest.raises(QuerySyntaxError):
        parse_query(query)


# ------------------------------------------------------------------- Strategy
def test_strategy_sorters_are_interchangeable():
    items = [
        make(title="b", priority="low", start="2026-10-08T09:00"),
        make(title="A", priority="high", start="2026-10-09T09:00"),
        make(title="c", priority="medium", start="2026-10-07T09:00"),
    ]
    sorter = ActivitySorter(SORT_STRATEGIES["start"])
    assert [a.title for a in sorter.sort(items)] == ["c", "b", "A"]
    sorter.set_strategy(SORT_STRATEGIES["priority"])
    assert [a.title for a in sorter.sort(items)] == ["A", "c", "b"]
    sorter.set_strategy(SORT_STRATEGIES["title"])
    assert [a.title for a in sorter.sort(items)] == ["A", "b", "c"]


# -------------------------------------------------------------------- Visitor
def test_visitors_run_over_all_kinds():
    items = [
        make(kind="meeting", title="M", attendees=["a", "b"], location="Sala", end="2026-10-08T10:00"),
        make(kind="task", title="T", priority="high"),
        make(kind="reminder", title="R"),
        make(kind="event", title="E", location="Auditório"),
    ]
    stats = StatisticsVisitor()
    for item in items:
        item.accept(stats)
    result = stats.result()
    assert result["total"] == 4
    assert result["by_kind"] == {"meeting": 1, "task": 1, "reminder": 1, "event": 1}
    assert result["meeting_attendees"] == 2
    assert result["total_minutes"] == 60 + 30 + 0 + 120
    details = [item.accept(DetailsVisitor()) for item in items]
    assert details[0] == "Reunião · local: Sala · 2 participante(s)"
    assert details[1] == "Tarefa · prioridade alta"
    assert details[2] == "Lembrete às 09:00"
    assert details[3] == "Evento · local: Auditório"


# -------------------------------------------------------------------- Memento
def test_memento_snapshot_and_restore_roundtrip():
    activity = make(title="Original", priority="low", kind="meeting", attendees=["Ana"])
    memento = activity.create_memento("update")
    activity.title = "Alterado"
    activity.attendees.append("Bia")
    activity.transition("complete")
    activity.restore_from(memento)
    assert activity.title == "Original" and activity.attendees == ["Ana"]
    assert activity.status == "pending"


def test_caretaker_is_lifo_per_reason():
    caretaker = HistoryCaretaker()
    activity = make()
    for title in ("v1", "v2"):
        activity.title = title
        caretaker.save(activity.id, activity.create_memento("update"))
    caretaker.save(activity.id, activity.create_memento("delete"))
    assert caretaker.pop_last(activity.id, "update").snapshot["title"] == "v2"
    assert caretaker.pop_last(activity.id, "delete") is not None
    assert caretaker.pop_last(activity.id, "delete") is None
    assert len(caretaker.entries(activity.id)) == 1


# ------------------------------------------------------------------- Observer
def test_observer_repository_notifies_notification_center(tmp_path):
    ActivityRepository.reset()
    repo = ActivityRepository(tmp_path / "o.json")
    center = NotificationCenter()
    repo.subscribe(center)
    activity = make(title="Obs")
    repo.add(activity)
    activity.title = "Obs2"
    repo.update(activity)
    repo.remove(activity.id)
    messages = [m["message"] for m in center.messages()]
    assert messages == ["Atividade 'Obs2' excluída", "Atividade 'Obs2' atualizada", "Atividade 'Obs' criada"]
    repo.unsubscribe(center)
    repo.add(make(title="Silêncio"))
    assert len(center.messages()) == 3
    ActivityRepository.reset()


def test_repository_persists_to_json_and_reloads(tmp_path):
    path = tmp_path / "persist.json"
    ActivityRepository.reset()
    repo = ActivityRepository(path)
    activity = make(kind="meeting", title="Persistida", attendees=["Ana"])
    repo.add(activity)
    ActivityRepository.reset()
    reloaded = ActivityRepository(path)
    assert reloaded.get(activity.id).attendees == ["Ana"]
    ActivityRepository.reset()
