"""Padrões estruturais do servidor: Decorator, Composite, Bridge, Adapter, Proxy, Facade."""
import json
from datetime import date

import pytest

from server.bridge import make_report
from server.composite import build_category_tree
from server.decorators import build_label
from server.errors import NotFoundError, ValidationError
from server.exporters import ActivityIcsAdapter, IcsComponent, get_exporter
from server.factory import create_activity
from server.repository import ActivityRepository, AuditedRepositoryProxy


def make(**data):
    base = {"kind": "task", "title": "T", "start": "2026-10-08T09:00"}
    base.update(data)
    return create_activity(base)


# ------------------------------------------------------------------ Decorator
def test_decorators_stack_on_top_of_plain_description():
    plain = make()
    assert build_label(plain) == "09:00-09:30 T"
    rich = make(priority="high", recurrence="weekly", reminder_minutes=15)
    rich.transition("start")
    label = build_label(rich)
    assert label.startswith("[Alta] ")
    assert "(repete semanalmente)" in label
    assert "(lembrar 15 min antes)" in label
    assert label.endswith("— em andamento")


# ------------------------------------------------------------------ Composite
def test_composite_tree_aggregates_counts_and_minutes():
    items = [
        make(title="A", category="Trabalho/Reuniões", end="2026-10-08T10:00"),
        make(title="B", category="Trabalho/Reuniões", end="2026-10-08T09:30"),
        make(title="C", category="Trabalho", end="2026-10-08T09:15"),
        make(title="D", category="Estudos", end="2026-10-08T09:45"),
    ]
    tree = build_category_tree(items)
    assert tree.count() == 4
    assert tree.total_minutes() == 60 + 30 + 15 + 45
    data = tree.to_dict()
    names = [child["name"] for child in data["children"]]
    assert names == ["Estudos", "Trabalho"]
    trabalho = next(c for c in data["children"] if c["name"] == "Trabalho")
    assert trabalho["count"] == 3
    assert {c["name"] for c in trabalho["children"]} == {"Reuniões", "C"}


# --------------------------------------------------------------------- Bridge
PROVIDER_ENTRIES = [
    {"date": "2026-10-08", "label": "09:00-10:00 <Reunião>", "kind_label": "Reunião"},
]


@pytest.mark.parametrize(
    "kind, expected_period",
    [
        ("daily", (date(2026, 10, 8), date(2026, 10, 8))),
        ("weekly", (date(2026, 10, 5), date(2026, 10, 11))),
        ("monthly", (date(2026, 10, 1), date(2026, 10, 31))),
    ],
)
def test_bridge_every_report_works_with_every_formatter(kind, expected_period):
    calls = []

    def provider(start, end):
        calls.append((start, end))
        return PROVIDER_ENTRIES

    for fmt in ("text", "json", "html"):
        report = make_report(kind, fmt, provider)
        content = report.render(date(2026, 10, 8))
        assert content
    assert calls[0] == expected_period


def test_bridge_formats_differ_in_content_type_and_escape_html():
    provider = lambda s, e: PROVIDER_ENTRIES
    text = make_report("daily", "text", provider)
    json_report = make_report("daily", "json", provider)
    html_report = make_report("daily", "html", provider)
    assert text.content_type == "text/plain"
    assert json.loads(json_report.render(date(2026, 10, 8)))["entries"] == PROVIDER_ENTRIES
    assert "&lt;Reunião&gt;" in html_report.render(date(2026, 10, 8))
    assert "sem atividades" in make_report("weekly", "text", provider).render(date(2026, 10, 8))


def test_bridge_rejects_unknown_kind_or_format():
    with pytest.raises(ValidationError):
        make_report("anual", "text", lambda s, e: [])
    with pytest.raises(ValidationError):
        make_report("daily", "pdf", lambda s, e: [])


# -------------------------------------------------------------------- Adapter
def test_adapter_exposes_activity_as_ics_component():
    activity = make(
        kind="meeting", title="Sprint, planning", priority="high", recurrence="weekly",
        recurrence_until="2026-12-01", reminder_minutes=15, location="Sala 3",
    )
    adapter = ActivityIcsAdapter(activity)
    assert isinstance(adapter, IcsComponent)
    ics = adapter.to_ics()
    assert "SUMMARY:Sprint\\, planning" in ics
    assert "DTSTART:20261008T090000" in ics
    assert "RRULE:FREQ=WEEKLY;UNTIL=20261201T235959" in ics
    assert "TRIGGER:-PT15M" in ics and "LOCATION:Sala 3" in ics


# ------------------------------------------------------------- Template Method
def test_template_method_exporters_share_skeleton():
    activities = [make(title="A"), make(title="B, com vírgula")]
    csv_text = get_exporter("csv").export(activities)
    lines = csv_text.strip().splitlines()
    assert lines[0].startswith("id,kind,title") and len(lines) == 3
    assert '"B, com vírgula"' in lines[2]

    json_data = json.loads(get_exporter("json").export(activities))
    assert [item["title"] for item in json_data] == ["A", "B, com vírgula"]
    assert json.loads(get_exporter("json").export([])) == []

    ics = get_exporter("ics").export(activities)
    assert ics.startswith("BEGIN:VCALENDAR\r\n") and ics.strip().endswith("END:VCALENDAR")
    assert ics.count("BEGIN:VEVENT") == 2


# ---------------------------------------------------------------------- Proxy
def test_audit_proxy_records_operations_and_failures(tmp_path):
    ActivityRepository.reset()
    proxy = AuditedRepositoryProxy(ActivityRepository(tmp_path / "x.json"))
    activity = make()
    proxy.add(activity)
    assert proxy.get(activity.id) is activity
    with pytest.raises(NotFoundError):
        proxy.remove("nao-existe")
    log = proxy.audit_entries()
    assert [e["operation"] for e in log] == ["remove", "get", "add"]
    assert log[0]["outcome"].startswith("erro") and log[1]["outcome"] == "ok"
    ActivityRepository.reset()
