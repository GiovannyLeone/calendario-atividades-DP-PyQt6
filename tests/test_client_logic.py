"""Cliente sem interface gráfica: Command, Observer/model, Proxy, Mediator, Flyweight, Abstract Factory, Facade."""
from datetime import date

import pytest

from client.api import ApiError, CalendarApi, HttpCalendarApi
from client.commands import (
    CommandHistory,
    CreateActivityCommand,
    DeleteActivityCommand,
    DuplicateActivityCommand,
    TransitionCommand,
    UpdateActivityCommand,
)
from client.facade import ClientFacade
from client.flyweight import ItemStyleFactory
from client.main import build_facade
from client.mediator import ActivityFormMediator
from client.model import CalendarModel
from client.observer import Observer
from client.proxy import CachingApiProxy
from client.themes import THEMES, ThemeFactory, build_stylesheet
from helpers import FlaskSession


@pytest.fixture
def real_api(client):
    """Cliente HTTP real falando com o app Flask de teste (contrato ponta a ponta)."""
    return HttpCalendarApi("http://servidor", session=FlaskSession(client))


def new_task(**overrides):
    data = {"kind": "task", "title": "Tarefa", "start": "2026-10-08T09:00", "end": "2026-10-08T10:00"}
    data.update(overrides)
    return data


# -------------------------------------------------------------- API + contrato
def test_http_api_roundtrip_against_real_server(real_api):
    created = real_api.create(new_task())
    assert real_api.list_activities()[0]["id"] == created["id"]
    assert real_api.calendar("2026-10-01", "2026-10-31")[0]["title"] == "Tarefa"
    assert real_api.transition(created["id"], "start")["status"] == "in_progress"
    assert real_api.search("status:in_progress")[0]["id"] == created["id"]
    assert real_api.stats()["total"] == 1
    assert real_api.categories()["count"] == 1
    assert "Tarefa" in real_api.report("daily", "2026-10-08")
    assert real_api.export("csv").startswith("id,kind")
    assert real_api.notifications()[-1]["message"].endswith("criada")  # mais recente primeiro
    assert real_api.health() == {"status": "ok"}


def test_http_api_translates_errors_to_api_error(real_api):
    with pytest.raises(ApiError) as exc:
        real_api.create(new_task(title=""))
    assert exc.value.status == 400 and "título" in exc.value.messages[0]
    with pytest.raises(ApiError) as exc:
        real_api.delete("inexistente")
    assert exc.value.status == 404


def test_http_api_reports_server_down():
    api = HttpCalendarApi("http://127.0.0.1:9", timeout=0.3)  # porta fechada
    with pytest.raises(ApiError) as exc:
        api.health()
    assert "indisponível" in str(exc.value)


# ---------------------------------------------------------------------- Command
def test_command_undo_redo_for_every_command(real_api):
    history = CommandHistory()
    create = CreateActivityCommand(real_api, new_task())
    history.execute(create)
    activity_id = real_api.list_activities()[0]["id"]

    history.execute(UpdateActivityCommand(real_api, activity_id, {"title": "Editada"}))
    assert real_api.list_activities()[0]["title"] == "Editada"
    history.undo()
    assert real_api.list_activities()[0]["title"] == "Tarefa"
    history.redo()
    assert real_api.list_activities()[0]["title"] == "Editada"

    history.execute(TransitionCommand(real_api, activity_id, "complete"))
    assert real_api.list_activities()[0]["status"] == "done"
    history.undo()
    assert real_api.list_activities()[0]["status"] == "pending"

    history.execute(DuplicateActivityCommand(real_api, activity_id, 2))
    assert len(real_api.list_activities()) == 2
    history.undo()
    assert len(real_api.list_activities()) == 1

    history.execute(DeleteActivityCommand(real_api, activity_id, "Editada"))
    assert real_api.list_activities() == []
    history.undo()
    assert real_api.list_activities()[0]["id"] == activity_id

    # desfaz tudo até a criação e refaz: o id original é preservado
    while history.can_undo:
        history.undo()
    assert real_api.list_activities() == []
    history.redo()
    assert real_api.list_activities()[0]["id"] == activity_id


def test_history_failed_command_is_not_recorded_and_new_command_clears_redo(real_api):
    history = CommandHistory()
    with pytest.raises(ApiError):
        history.execute(CreateActivityCommand(real_api, new_task(title="")))
    assert not history.can_undo
    history.execute(CreateActivityCommand(real_api, new_task()))
    history.undo()
    assert history.can_redo and history.next_redo_description == "Criar 'Tarefa'"
    history.execute(CreateActivityCommand(real_api, new_task(title="Outra")))
    assert not history.can_redo
    assert CommandHistory().undo() == "" and CommandHistory().redo() == ""


# --------------------------------------------------------- Observer + modelo
class Recorder(Observer):
    def __init__(self):
        self.changes = []

    def on_change(self, subject, change):
        self.changes.append(change)


def test_model_grid_and_navigation(real_api):
    model = CalendarModel(real_api, today=date(2026, 10, 8))
    dates = model.grid_dates()
    assert len(dates) == 42 and dates[0] == date(2026, 9, 27)  # domingo anterior a 1/out/2026
    assert dates[0].weekday() == 6
    model.next_month()
    assert (model.year, model.month) == (2026, 11)
    model.previous_month(); model.previous_month()
    assert (model.year, model.month) == (2026, 9)
    model.go_today()
    assert (model.year, model.month, model.selected) == (2026, 10, date(2026, 10, 8))
    model.select(date(2026, 12, 25))
    assert (model.year, model.month) == (2026, 12)
    model.month = 12; model.year = 2026
    model.next_month()
    assert (model.year, model.month) == (2027, 1)
    model.previous_month()
    assert (model.year, model.month) == (2026, 12)


def test_model_notifies_observers_and_filters_by_day(real_api):
    real_api.create(new_task())
    model = CalendarModel(real_api, today=date(2026, 10, 8))
    recorder = Recorder()
    model.attach(recorder)
    model.attach(recorder)  # idempotente
    model.refresh()
    model.select(date(2026, 10, 9))
    model.set_status("ok")
    assert recorder.changes == ["refresh", "selection", "status"]
    model.select(date(2026, 10, 8))
    assert [o["title"] for o in model.occurrences_on(date(2026, 10, 8))] == ["Tarefa"]
    assert model.occurrences_on(date(2026, 10, 9)) == []
    model.detach(recorder)
    model.refresh()
    assert len(recorder.changes) == 4  # +1 "selection" antes do detach, nenhum depois


def test_model_keeps_error_when_server_fails():
    model = CalendarModel(HttpCalendarApi("http://127.0.0.1:9", timeout=0.3), today=date(2026, 10, 8))
    model.refresh()
    assert model.occurrences == [] and "indisponível" in model.error


# ------------------------------------------------------------------------ Proxy
class CountingApi(CalendarApi):
    """API falsa que conta chamadas reais."""

    def __init__(self):
        self.calls = []

    def _hit(self, name, value=None):
        self.calls.append(name)
        return value

    def health(self): return self._hit("health", {})
    def list_activities(self, sort="start"): return self._hit("list", [])
    def calendar(self, start, end): return self._hit("calendar", [{"n": len(self.calls)}])
    def create(self, data): return self._hit("create", {"id": "1"})
    def update(self, activity_id, data): return self._hit("update", {})
    def delete(self, activity_id): return self._hit("delete", {})
    def duplicate(self, activity_id, days=1): return self._hit("duplicate", {"id": "2"})
    def transition(self, activity_id, action): return self._hit("transition", {})
    def revert(self, activity_id): return self._hit("revert", {})
    def restore(self, activity_id): return self._hit("restore", {})
    def search(self, query): return self._hit("search", [])
    def stats(self): return self._hit("stats", {})
    def categories(self): return self._hit("categories", {})
    def report(self, kind, reference, fmt="text"): return self._hit("report", "")
    def export(self, fmt): return self._hit("export", "")
    def notifications(self): return self._hit("notifications", [])


def test_caching_proxy_caches_reads_and_invalidates_on_writes():
    real = CountingApi()
    now = [0.0]
    proxy = CachingApiProxy(real, ttl=10, clock=lambda: now[0])
    first = proxy.calendar("a", "b")
    second = proxy.calendar("a", "b")
    assert first == second and real.calls == ["calendar"]
    assert (proxy.hits, proxy.misses) == (1, 1)
    second.append("mutação local")
    assert proxy.calendar("a", "b") == first  # cópias protegem o cache

    proxy.calendar("c", "d")
    assert real.calls == ["calendar", "calendar"]  # chave diferente

    proxy.create({})
    proxy.calendar("a", "b")
    assert real.calls[-2:] == ["create", "calendar"]  # escrita invalidou

    now[0] = 100.0
    proxy.calendar("a", "b")
    assert real.calls[-1] == "calendar" and real.calls.count("calendar") == 4  # TTL expirou

    proxy.notifications(); proxy.notifications()
    assert real.calls.count("notifications") == 2  # nunca em cache


def test_caching_proxy_invalidates_even_when_write_fails():
    class Failing(CountingApi):
        def delete(self, activity_id):
            raise ApiError("falhou")

    proxy = CachingApiProxy(Failing())
    proxy.stats()
    with pytest.raises(ApiError):
        proxy.delete("x")
    proxy.stats()
    assert proxy.misses == 2


# --------------------------------------------------------------------- Mediator
class FakeField:
    def __init__(self, data=None, text="", checked=False):
        self.data, self._text, self.checked, self.enabled = data, text, checked, True

    def currentData(self): return self.data
    def text(self): return self._text
    def isChecked(self): return self.checked
    def setEnabled(self, value): self.enabled = value


def make_mediator():
    fields = {name: FakeField() for name in (
        "end", "location", "attendees", "recurrence_until", "reminder_minutes", "save_button")}
    fields["kind"] = FakeField("task")
    fields["title"] = FakeField(text="")
    fields["recurrence"] = FakeField("none")
    fields["reminder_enabled"] = FakeField(checked=False)
    return fields, ActivityFormMediator(**fields)


def test_mediator_coordinates_form_fields():
    f, mediator = make_mediator()
    mediator.changed()
    assert f["end"].enabled and not f["location"].enabled and not f["attendees"].enabled
    assert not f["recurrence_until"].enabled and not f["reminder_minutes"].enabled
    assert not f["save_button"].enabled  # título vazio

    f["kind"].data = "meeting"; f["title"]._text = " Sprint "
    f["recurrence"].data = "weekly"; f["reminder_enabled"].checked = True
    mediator.changed()
    assert f["location"].enabled and f["attendees"].enabled
    assert f["recurrence_until"].enabled and f["reminder_minutes"].enabled and f["save_button"].enabled

    f["kind"].data = "reminder"
    mediator.changed()
    assert not f["end"].enabled and not f["attendees"].enabled

    f["kind"].data = "event"
    mediator.changed()
    assert f["location"].enabled and not f["attendees"].enabled


# --------------------------------------------------------------------- Flyweight
def test_flyweight_shares_style_instances():
    factory = ItemStyleFactory()
    a = factory.get("task", "pending")
    assert factory.get("task", "pending") is a
    assert factory.get("task", "done") is not a
    for _ in range(50):
        factory.get("meeting", "pending")
    assert len(factory) == 3
    assert factory.get("task", "done").strike and factory.get("task", "cancelled").italic
    assert factory.get("task", "in_progress").bold and "line-through" in factory.get("event", "done").css()
    assert factory.get("desconhecido", "pending").background == "#e6e6e6"


# --------------------------------------------------------------- Abstract Factory
def test_abstract_factory_families_are_consistent():
    light, dark = THEMES["claro"], THEMES["escuro"]
    for factory in (light, dark):
        assert isinstance(factory, ThemeFactory)
        palette = factory.create_palette()
        assert factory.create_button_style().palette.name == palette.name
        assert factory.create_cell_style().palette.name == palette.name
    assert light.create_palette().window != dark.create_palette().window
    assert light.create_button_style().css() != dark.create_button_style().css()
    selected = dark.create_cell_style().css(selected=True, today=False, other_month=False)
    assert dark.create_palette().selected in selected and "dayCell" in selected
    assert dark.create_palette().window in build_stylesheet(dark)
    assert light.create_palette().window in build_stylesheet(light)


# ------------------------------------------------------------------------ Facade
def test_client_facade_runs_commands_updates_model_and_undoes(real_api):
    model = CalendarModel(real_api, today=date(2026, 10, 8))
    facade = ClientFacade(real_api, model)
    recorder = Recorder()
    model.attach(recorder)

    facade.create_activity(new_task())
    assert [o["title"] for o in model.occurrences_on(date(2026, 10, 8))] == ["Tarefa"]
    assert model.status_message == "Criar 'Tarefa'"
    activity_id = model.occurrences_on(date(2026, 10, 8))[0]["id"]

    facade.change_status(activity_id, "start", "Tarefa")
    assert model.occurrences_on(date(2026, 10, 8))[0]["status"] == "in_progress"
    facade.edit_activity(activity_id, {"title": "Nova"})
    facade.duplicate_activity(activity_id, 1, "Nova")
    assert len(model.occurrences) == 2

    facade.undo()
    assert len(model.occurrences) == 1 and model.status_message.startswith("Desfeito")
    facade.redo()
    assert len(model.occurrences) == 2 and model.status_message.startswith("Refeito")

    facade.delete_activity(activity_id, "Nova")
    assert len(model.occurrences) == 1
    facade.undo()
    assert len(model.occurrences) == 2
    assert "refresh" in recorder.changes and "status" in recorder.changes

    assert facade.search("title:Nova")[0]["id"] == activity_id
    assert facade.stats()["total"] == 2
    assert facade.category_tree()["count"] == 2
    assert "Nova" in facade.report("daily", date(2026, 10, 8))
    assert len(facade.server_notifications()) > 0


def test_client_facade_propagates_validation_errors(real_api):
    facade = ClientFacade(real_api, CalendarModel(real_api, today=date(2026, 10, 8)))
    with pytest.raises(ApiError):
        facade.create_activity(new_task(title=""))
    assert not facade.history.can_undo
    facade.undo(); facade.redo()  # sem efeito, sem erro


def test_client_facade_exports_to_file(real_api, tmp_path):
    facade = ClientFacade(real_api, CalendarModel(real_api, today=date(2026, 10, 8)))
    facade.create_activity(new_task())
    target = tmp_path / "saida.ics"
    facade.export_to_file("ics", str(target))
    assert "BEGIN:VCALENDAR" in target.read_text(encoding="utf-8")


def test_build_facade_wires_proxy_between_api_and_model():
    facade = build_facade("http://127.0.0.1:9")
    assert isinstance(facade.model, CalendarModel)
    assert isinstance(facade._api, CachingApiProxy)
