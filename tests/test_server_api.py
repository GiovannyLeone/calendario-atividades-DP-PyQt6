"""Comportamento do servidor via endpoints HTTP (Flask test client)."""
import json

from conftest import meeting_data


def create(client, **overrides):
    resp = client.post("/api/activities", json=meeting_data(**overrides))
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


def test_health(client):
    assert client.get("/api/health").get_json() == {"status": "ok"}


def test_create_get_list_update_delete_flow(client):
    created = create(client)
    assert created["kind"] == "meeting" and created["status"] == "pending"
    assert client.get(f"/api/activities/{created['id']}").get_json()["title"] == "Reunião de teste"
    assert len(client.get("/api/activities").get_json()) == 1

    updated = client.put(f"/api/activities/{created['id']}", json={"title": "Novo título", "priority": "high"})
    assert updated.status_code == 200
    assert updated.get_json()["title"] == "Novo título"
    assert updated.get_json()["location"] == "Sala 1"  # campos não enviados são preservados

    assert client.delete(f"/api/activities/{created['id']}").get_json() == {"deleted": created["id"]}
    assert client.get(f"/api/activities/{created['id']}").status_code == 404


def test_validation_errors_return_400_with_all_messages(client):
    resp = client.post("/api/activities", json={"kind": "task", "title": "", "start": "2026-10-08T10:00", "end": "2026-10-08T09:00"})
    assert resp.status_code == 400
    assert len(resp.get_json()["errors"]) == 2
    assert client.post("/api/activities", json={"kind": "task", "title": "x"}).status_code == 400
    assert client.post("/api/activities", json={"kind": "xyz", "title": "x", "start": "2026-10-08T10:00"}).status_code == 400
    assert client.post("/api/activities", data="não é json", content_type="text/plain").status_code == 400


def test_conflicting_meetings_are_rejected(client):
    create(client)
    resp = client.post("/api/activities", json=meeting_data(title="Outra", start="2026-10-08T10:30", end="2026-10-08T11:30"))
    assert resp.status_code == 400
    assert "Conflito" in resp.get_json()["error"]


def test_kind_cannot_be_changed_and_status_is_ignored_on_update(client):
    created = create(client)
    assert client.put(f"/api/activities/{created['id']}", json={"kind": "task"}).status_code == 400
    resp = client.put(f"/api/activities/{created['id']}", json={"status": "done"})
    assert resp.get_json()["status"] == "pending"


def test_transition_endpoint_and_invalid_transition(client):
    created = create(client)
    url = f"/api/activities/{created['id']}/transition"
    assert client.post(url, json={"action": "start"}).get_json()["status"] == "in_progress"
    assert client.post(url, json={"action": "complete"}).get_json()["status"] == "done"
    assert client.post(url, json={"action": "start"}).status_code == 409
    assert client.post(url, json={"action": "voar"}).status_code == 400


def test_duplicate_endpoint_uses_prototype(client):
    created = create(client)
    resp = client.post(f"/api/activities/{created['id']}/duplicate", json={"days": 7})
    assert resp.status_code == 201
    twin = resp.get_json()
    assert twin["id"] != created["id"] and twin["start"] == "2026-10-15T10:00"
    assert client.post(f"/api/activities/{created['id']}/duplicate", json={"days": "x"}).status_code == 400


def test_revert_and_restore_use_memento(client):
    created = create(client)
    cid = created["id"]
    client.put(f"/api/activities/{cid}", json={"title": "Editada"})
    client.post(f"/api/activities/{cid}/transition", json={"action": "start"})
    history = client.get(f"/api/activities/{cid}/history").get_json()
    assert len(history) == 2

    assert client.post(f"/api/activities/{cid}/revert").get_json()["status"] == "pending"
    assert client.post(f"/api/activities/{cid}/revert").get_json()["title"] == "Reunião de teste"
    assert client.post(f"/api/activities/{cid}/revert").status_code == 404  # nada mais a desfazer

    client.delete(f"/api/activities/{cid}")
    restored = client.post(f"/api/activities/{cid}/restore")
    assert restored.status_code == 201 and restored.get_json()["id"] == cid
    assert client.post(f"/api/activities/{cid}/restore").status_code == 404


def test_calendar_expands_recurrences_and_decorates_labels(client):
    client.post(
        "/api/activities",
        json={"kind": "task", "title": "Treino", "start": "2026-10-05T07:00", "end": "2026-10-05T08:00",
              "recurrence": "weekly", "recurrence_until": "2026-10-31", "priority": "high"},
    )
    data = client.get("/api/calendar?start=2026-10-01&end=2026-10-31").get_json()
    assert [o["date"] for o in data] == ["2026-10-05", "2026-10-12", "2026-10-19", "2026-10-26"]
    assert data[0]["label"].startswith("[Alta] 07:00-08:00 Treino")
    assert "repete semanalmente" in data[0]["label"] and data[0]["details"].startswith("Tarefa")
    assert client.get("/api/calendar?start=2026-10-31&end=2026-10-01").status_code == 400
    assert client.get("/api/calendar?start=2026-01-01&end=2028-01-01").status_code == 400
    assert client.get("/api/calendar").status_code == 400


def test_search_endpoint(client):
    create(client)
    create(client, title="Almoço", start="2026-10-09T12:00", end="2026-10-09T13:00", kind="event")
    found = client.get("/api/search", query_string={"q": "kind:meeting AND category:Trabalho"}).get_json()
    assert [a["title"] for a in found] == ["Reunião de teste"]
    assert client.get("/api/search", query_string={"q": "((("}).status_code == 400
    assert client.get("/api/search").status_code == 400


def test_stats_and_categories(client):
    create(client)
    stats = client.get("/api/stats").get_json()
    assert stats["total"] == 1 and stats["by_kind"] == {"meeting": 1} and stats["meeting_attendees"] == 2
    tree = client.get("/api/categories").get_json()
    assert tree["count"] == 1 and tree["children"][0]["name"] == "Trabalho"


def test_reports_and_exports_endpoints(client):
    create(client)
    text = client.get("/api/reports/daily?date=2026-10-08")
    assert text.status_code == 200 and "Reunião de teste" in text.get_data(as_text=True)
    html = client.get("/api/reports/weekly?date=2026-10-08&format=html")
    assert html.mimetype == "text/html"
    assert json.loads(client.get("/api/reports/monthly?date=2026-10-08&format=json").get_data(as_text=True))["entries"]
    assert client.get("/api/reports/anual").status_code == 400

    ics = client.get("/api/export/ics")
    assert ics.mimetype == "text/calendar" and "attachment" in ics.headers["Content-Disposition"]
    assert b"BEGIN:VEVENT" in ics.data
    assert client.get("/api/export/csv").mimetype == "text/csv"
    assert client.get("/api/export/xml").status_code == 400


def test_notifications_and_audit_endpoints(client):
    created = create(client)
    client.delete(f"/api/activities/{created['id']}")
    notes = [n["message"] for n in client.get("/api/notifications").get_json()]
    assert notes == ["Atividade 'Reunião de teste' excluída", "Atividade 'Reunião de teste' criada"]
    audit = client.get("/api/audit").get_json()
    assert {"add", "remove"} <= {entry["operation"] for entry in audit}


def test_list_filters_and_sorting(client):
    create(client)
    client.post("/api/activities", json={"kind": "task", "title": "A tarefa", "start": "2026-10-07T09:00", "priority": "high"})
    assert [a["title"] for a in client.get("/api/activities?sort=title").get_json()] == ["A tarefa", "Reunião de teste"]
    assert [a["title"] for a in client.get("/api/activities?sort=priority").get_json()][0] == "A tarefa"
    assert len(client.get("/api/activities?kind=meeting").get_json()) == 1
    assert len(client.get("/api/activities?category=Trabalho").get_json()) == 1
    assert client.get("/api/activities?sort=xyz").status_code == 400


def test_seed_file_is_valid_and_loadable(tmp_path):
    from pathlib import Path

    from server.app import create_app
    from server.repository import ActivityRepository

    seed = Path(__file__).resolve().parent.parent / "data" / "activities_seed.json"
    ActivityRepository.reset()
    app = create_app.__wrapped__(tmp_path / "w.json") if hasattr(create_app, "__wrapped__") else None
    ActivityRepository.reset()
    repo = ActivityRepository(tmp_path / "copy.json", seed_path=seed)
    assert len(repo.all()) == 10
    client = create_app(tmp_path / "copy.json").test_client()
    data = client.get("/api/calendar?start=2026-10-01&end=2026-10-31").get_json()
    assert len(data) > 20  # daily + weekly expandem bastante
    ActivityRepository.reset()
