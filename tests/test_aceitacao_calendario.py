"""Plano de testes de qualidade — 2. Calendário de atividades (T2.1 a T2.4).

Padrões demonstrados por comportamento observável:
  * Criacional   — Builder: atividade com campos obrigatórios e opcionais.
  * Estrutural   — Facade: criação, edição e consulta de eventos por uma interface simples.
  * Comportamental — Observer: calendário e lembretes se atualizam após alterações.

Critérios gerais do plano: entradas válidas, ausentes, fora de faixa, malformadas,
duplicadas e limites de negócio; persistência sem gravações parciais; códigos de erro
HTTP; consistência após nova consulta; comportamento em falha de rede; e mensagem exibida
no QT conferida junto com o estado persistido no servidor.
"""
import json
import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from client.api import ApiError, HttpCalendarApi
from client.facade import ClientFacade
from client.model import CalendarModel
from client.observer import Observer
from client.proxy import CachingApiProxy
from client.ui.main_window import MainWindow
from helpers import FlaskSession
from server.app import create_app
from server.builder import ActivityBuilder
from server.errors import ValidationError
from server.factory import creator_for
from server.observer import Observer as ServerObserver
from server.repository import ActivityRepository
from server.activity import Meeting, Task

TODAY = date(2026, 10, 8)


# ------------------------------------------------------------------ fixtures
@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def task(**overrides):
    data = {
        "kind": "task",
        "title": "Entregar relatório",
        "start": "2026-10-08T09:00",
        "end": "2026-10-08T10:00",
    }
    data.update(overrides)
    return data


def saved(app):
    """Estado persistido no arquivo JSON do servidor (fonte da verdade)."""
    path = app.config["FACADE"]._store._real._path  # repositório real por trás do proxy
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))["activities"]


def make_client(flask_client, today=TODAY, timeout=5.0):
    """Um 'cliente QT' completo (API HTTP -> proxy de cache -> modelo -> fachada)."""
    api = CachingApiProxy(HttpCalendarApi("http://servidor", session=FlaskSession(flask_client), timeout=timeout))
    model = CalendarModel(api, today=today)
    return ClientFacade(api, model)


class FakeDialog:
    """Substitui o diálogo modal: devolve os dados que o usuário 'preencheu'."""

    data: dict = {}

    def __init__(self, *args, **kwargs):
        pass

    def exec(self):
        return True

    def get_data(self):
        return dict(FakeDialog.data)


@pytest.fixture
def ui(app, client, qapp, monkeypatch):
    """Janela principal real, ligada ao servidor Flask de teste."""
    warnings: list[str] = []
    monkeypatch.setattr("client.ui.main_window.ActivityDialog", FakeDialog)
    monkeypatch.setattr(
        "client.ui.main_window.QMessageBox.warning", lambda parent, title, text, *a: warnings.append(text)
    )
    facade = make_client(client)
    window = MainWindow(facade)
    window.show()
    facade.model.go_today()
    window.warnings = warnings
    yield window
    window.close()


def day_texts(window):
    lst = window.day_panel._list
    return [lst.item(i).text() for i in range(lst.count())]


def cell_texts(window, day):
    model = window.month_view  # noqa: F841 (documenta o widget inspecionado)
    index = window._model.grid_dates().index(day)
    cell = window.month_view._cells[index]
    return [lbl.text() for lbl in cell._entries if not lbl.isHidden()]


# =========================================================== T2.1 — Criar e exibir
class TestT21CriarEExibir:
    def test_api_cria_e_consulta_atividade(self, client):
        resp = client.post("/api/activities", json=task(description="Q3", priority="high", category="Trabalho"))
        assert resp.status_code == 201
        created = resp.get_json()
        assert created["id"] and created["status"] == "pending"
        assert (created["title"], created["priority"], created["category"]) == ("Entregar relatório", "high", "Trabalho")

        assert client.get(f"/api/activities/{created['id']}").get_json() == created
        occ = client.get("/api/calendar?start=2026-10-01&end=2026-10-31").get_json()
        assert [(o["id"], o["date"]) for o in occ] == [(created["id"], "2026-10-08")]

    def test_ui_cria_pelo_controle_visivel_e_exibe_no_calendario(self, ui, app):
        FakeDialog.data = task()
        ui.day_panel.new_requested.emit()  # botão "Nova" do painel do dia

        assert any("Entregar relatório" in t for t in day_texts(ui))
        assert any("Entregar relatório" in t for t in cell_texts(ui, TODAY))
        assert [a["title"] for a in saved(app)] == ["Entregar relatório"]  # servidor persistiu
        assert ui.warnings == []

    def test_atividade_so_aparece_no_dia_e_mes_corretos(self, ui):
        FakeDialog.data = task(start="2026-10-20T08:00", end="2026-10-20T09:00")
        ui.day_panel.new_requested.emit()
        assert day_texts(ui) == ["Nenhuma atividade neste dia"]  # dia 08 segue vazio
        assert any("Entregar relatório" in t for t in cell_texts(ui, date(2026, 10, 20)))
        ui._model.select(date(2026, 10, 20))
        assert any("Entregar relatório" in t for t in day_texts(ui))
        ui._model.next_month()  # mês seguinte não deve exibir a atividade de outubro
        assert all("Entregar relatório" not in t for t in day_texts(ui))

    def test_tipos_de_atividade_sao_criados_com_padroes_proprios(self, client):
        for kind in ("task", "meeting", "reminder", "event"):
            body = task(kind=kind, title=f"Item {kind}")
            body["start"] = f"2026-10-{10 + len(kind):02d}T09:00"  # horários distintos: sem conflito
            body["end"] = body["start"][:11] + "10:00"
            assert client.post("/api/activities", json=body).status_code == 201, kind
        kinds = {a["kind"] for a in client.get("/api/activities").get_json()}
        assert kinds == {"task", "meeting", "reminder", "event"}


# ============================================== T2.2 — Validar período e obrigatórios
LONG_TITLE = "x" * 81

INVALID_PAYLOADS = {
    "titulo ausente": task(title=None),
    "titulo vazio": task(title=""),
    "titulo so espacos": task(title="   "),
    "titulo acima do limite": task(title=LONG_TITLE),
    "titulo malformado (numero)": task(title=123),
    "titulo malformado (lista)": task(title=["a"]),
    "inicio ausente": {k: v for k, v in task().items() if k != "start"},
    "inicio malformado": task(start="amanhã"),
    "inicio inexistente (31/02)": task(start="2026-02-31T10:00", end="2026-02-31T11:00"),
    "inicio numerico": task(start=20261008),
    "termino malformado": task(end="logo"),
    "termino antes do inicio": task(end="2026-10-08T08:00"),
    "termino igual ao inicio": task(end="2026-10-08T09:00"),
    "duracao acima de 24h": task(end="2026-10-09T09:01"),
    "prioridade invalida": task(priority="urgentissima"),
    "prioridade malformada": task(priority=["high"]),
    "recorrencia invalida": task(recurrence="quinzenal"),
    "recorrencia termina antes do inicio": task(recurrence="daily", recurrence_until="2026-10-01"),
    "recorrencia com data malformada": task(recurrence="daily", recurrence_until="fim do ano"),
    "lembrete negativo": task(reminder_minutes=-1),
    "lembrete acima do limite": task(reminder_minutes=10081),
    "lembrete malformado": task(reminder_minutes="abc"),
    "tipo desconhecido": task(kind="festa"),
    "categoria malformada": task(category=42),
}


class TestT22ValidarPeriodoECamposObrigatorios:
    @pytest.mark.parametrize("name", list(INVALID_PAYLOADS))
    def test_entrada_invalida_e_rejeitada_sem_persistir(self, client, app, name):
        resp = client.post("/api/activities", json=INVALID_PAYLOADS[name])
        assert resp.status_code == 400, name
        body = resp.get_json()
        assert body["error"] and body["errors"], "mensagem clara para o usuário"
        assert client.get("/api/activities").get_json() == []
        assert saved(app) == []  # nenhum dado indevido persistido

    @pytest.mark.parametrize("body", [[], "texto", 7, None])
    def test_corpo_que_nao_e_objeto_json_e_rejeitado(self, client, body):
        resp = client.post("/api/activities", json=body)
        assert resp.status_code == 400
        assert resp.get_json()["errors"]

    def test_limites_validos_sao_aceitos(self, client):
        ok = [
            task(title="x" * 80),
            task(title="24h", start="2026-10-10T00:00", end="2026-10-11T00:00"),
            task(title="lembrete 0", start="2026-10-12T08:00", end="2026-10-12T09:00", reminder_minutes=0),
            task(title="lembrete max", start="2026-10-13T08:00", end="2026-10-13T09:00", reminder_minutes=10080),
            task(title="so titulo e inicio", end=None, start="2026-10-14T08:00"),
            {"kind": "reminder", "title": "Ligar", "start": "2026-10-15T08:00"},
        ]
        for body in ok:
            body = {k: v for k, v in body.items() if v is not None}
            assert client.post("/api/activities", json=body).status_code == 201, body["title"]

    def test_atividade_duplicada_e_rejeitada(self, client, app):
        assert client.post("/api/activities", json=task()).status_code == 201
        again = client.post("/api/activities", json=task(title="  entregar RELATÓRIO "))
        assert again.status_code == 400
        assert "já existe" in again.get_json()["error"].lower()
        assert len(saved(app)) == 1

    def test_duplicar_duas_vezes_com_o_mesmo_deslocamento_e_rejeitado(self, client):
        created = client.post("/api/activities", json=task()).get_json()
        week = client.post(f"/api/activities/{created['id']}/duplicate", json={"days": 7})
        assert week.status_code == 201 and week.get_json()["start"] == "2026-10-15T09:00"
        again = client.post(f"/api/activities/{created['id']}/duplicate", json={"days": 7})
        assert again.status_code == 400 and "já existe" in again.get_json()["error"].lower()
        other_day = client.post(f"/api/activities/{created['id']}/duplicate", json={"days": 8})
        assert other_day.status_code == 201

    def test_conflito_entre_reunioes_e_rejeitado(self, client):
        meeting = {"kind": "meeting", "title": "A", "start": "2026-10-08T10:00", "end": "2026-10-08T11:00"}
        assert client.post("/api/activities", json=meeting).status_code == 201
        clash = client.post("/api/activities", json={**meeting, "title": "B", "start": "2026-10-08T10:30", "end": "2026-10-08T11:30"})
        assert clash.status_code == 400 and "Conflito" in clash.get_json()["error"]
        adjacent = client.post("/api/activities", json={**meeting, "title": "C", "start": "2026-10-08T11:00", "end": "2026-10-08T12:00"})
        assert adjacent.status_code == 201  # fronteira exata não é conflito

    def test_edicao_invalida_nao_altera_o_registro(self, client, app):
        created = client.post("/api/activities", json=task()).get_json()
        resp = client.put(f"/api/activities/{created['id']}", json={"end": "2026-10-08T08:00"})
        assert resp.status_code == 400
        assert client.get(f"/api/activities/{created['id']}").get_json() == created
        assert saved(app)[0]["end"] == "2026-10-08T10:00"
        assert client.put("/api/activities/inexistente", json={"title": "x"}).status_code == 404

    def test_ids_inexistentes_retornam_404_e_acoes_invalidas_409(self, client):
        created = client.post("/api/activities", json=task()).get_json()
        assert client.get("/api/activities/nao-existe").status_code == 404
        assert client.delete("/api/activities/nao-existe").status_code == 404
        assert client.post(f"/api/activities/{created['id']}/transition", json={"action": "reopen"}).status_code == 409
        assert client.post(f"/api/activities/{created['id']}/transition", json={"action": "voar"}).status_code in (400, 409)

    def test_ui_mostra_mensagem_de_erro_e_servidor_nao_persiste(self, ui, app):
        FakeDialog.data = task(end="2026-10-08T08:00")  # término antes do início
        ui.day_panel.new_requested.emit()
        assert len(ui.warnings) == 1 and "posterior ao início" in ui.warnings[0]
        assert saved(app) == []
        assert day_texts(ui) == ["Nenhuma atividade neste dia"]

        FakeDialog.data = task(title="")
        ui.day_panel.new_requested.emit()
        assert "título é obrigatório" in ui.warnings[-1]
        assert saved(app) == []

    def test_ui_lista_todos_os_erros_de_uma_vez(self, ui):
        FakeDialog.data = task(title="", end="2026-10-08T08:00", priority="x")
        ui.day_panel.new_requested.emit()
        message = ui.warnings[0]
        assert "título" in message and "posterior ao início" in message and "Prioridade" in message


# ================================================ T2.3 — Persistência e entre clientes
class TestT23PersistenciaEAtualizacaoEntreClientes:
    def test_dados_sobrevivem_a_reinicio_do_servidor(self, app, client, tmp_path):
        created = client.post("/api/activities", json=task()).get_json()
        client.put(f"/api/activities/{created['id']}", json={"title": "Editada"})

        ActivityRepository.reset()  # "reinicia" o servidor apontando para o mesmo arquivo
        restarted = create_app(tmp_path / "activities.json").test_client()
        after = restarted.get(f"/api/activities/{created['id']}").get_json()
        assert after["title"] == "Editada" and after["start"] == "2026-10-08T09:00"
        assert not list(tmp_path.glob("*.tmp")), "sem arquivo temporário sobrando"
        json.loads((tmp_path / "activities.json").read_text(encoding="utf-8"))  # JSON íntegro

    def test_segundo_cliente_ve_alteracoes_do_primeiro_apos_nova_consulta(self, app):
        a = make_client(app.test_client())
        b = make_client(app.test_client())
        a.model.go_today()
        b.model.go_today()
        assert b.model.occurrences == []

        a.create_activity(task())
        b.model.reload()  # "Atualizar" (F5)
        assert [o["title"] for o in b.model.occurrences] == ["Entregar relatório"]

        a.edit_activity(a.model.occurrences[0]["id"], {"title": "Renomeada"})
        b.model.reload()
        assert [o["title"] for o in b.model.occurrences] == ["Renomeada"]

        b.delete_activity(b.model.occurrences[0]["id"], "Renomeada")
        a.model.reload()
        assert a.model.occurrences == []

    def test_cache_do_cliente_nao_esconde_dados_novos_depois_de_reload(self, app):
        a = make_client(app.test_client())
        b = make_client(app.test_client())
        b.model.go_today()
        b.model.refresh()  # aquece o cache de B
        a.create_activity(task())
        b.model.reload()
        assert len(b.model.occurrences) == 1

    def test_janela_atualiza_quando_outro_cliente_altera(self, ui, app):
        other = make_client(app.test_client())
        other.create_activity(task(title="Criada por outro cliente"))
        ui._model.reload()
        assert any("Criada por outro cliente" in t for t in day_texts(ui))

    def test_consistencia_apos_nova_consulta_lista_e_calendario(self, client):
        ids = [client.post("/api/activities", json=task(title=f"T{i}", start=f"2026-10-{10 + i}T09:00", end=f"2026-10-{10 + i}T10:00")).get_json()["id"] for i in range(3)]
        listed = {a["id"] for a in client.get("/api/activities").get_json()}
        in_calendar = {o["id"] for o in client.get("/api/calendar?start=2026-10-01&end=2026-10-31").get_json()}
        assert listed == in_calendar == set(ids)

    def test_falha_de_gravacao_nao_deixa_dado_parcial(self, app, client, monkeypatch):
        keep = client.post("/api/activities", json=task(title="Existente")).get_json()
        before = saved(app)
        repo = app.config["FACADE"]._store._real

        def broken_save():
            raise OSError("disco cheio")

        monkeypatch.setattr(repo, "_save", broken_save)
        resp = client.post("/api/activities", json=task(title="Nova", start="2026-10-09T09:00", end="2026-10-09T10:00"))
        assert resp.status_code == 500 and resp.get_json()["errors"]
        assert client.put(f"/api/activities/{keep['id']}", json={"title": "Mudou"}).status_code == 500
        assert client.delete(f"/api/activities/{keep['id']}").status_code == 500

        monkeypatch.undo()
        assert saved(app) == before  # arquivo intacto
        titles = [a["title"] for a in client.get("/api/activities").get_json()]
        assert titles == ["Existente"]  # memória coerente com o disco: nada pela metade

    def test_cliente_informa_falha_de_rede_sem_travar(self, qapp, monkeypatch):
        warnings = []
        monkeypatch.setattr("client.ui.main_window.ActivityDialog", FakeDialog)
        monkeypatch.setattr("client.ui.main_window.QMessageBox.warning", lambda p, t, text, *a: warnings.append(text))
        api = CachingApiProxy(HttpCalendarApi("http://127.0.0.1:9", timeout=0.3))
        facade = ClientFacade(api, CalendarModel(api, today=TODAY))
        window = MainWindow(facade)
        window.show()
        facade.model.go_today()
        assert "indisponível" in facade.model.error
        assert "indisponível" in window.statusBar().currentMessage()

        FakeDialog.data = task()
        window.day_panel.new_requested.emit()  # a janela continua respondendo
        assert warnings and "indisponível" in warnings[0]
        window.close()

    def test_falha_de_rede_no_meio_da_operacao_e_reportada_como_erro_recuperavel(self, app):
        facade = make_client(app.test_client())
        facade.model.go_today()
        real = facade._api._real

        class Down:
            def request(self, *a, **k):
                import requests
                raise requests.ConnectionError("caiu")

        real._session = Down()
        with pytest.raises(ApiError) as exc:
            facade.create_activity(task())
        assert "indisponível" in str(exc.value)
        assert not facade.history.can_undo  # operação que falhou não entra no histórico
        real._session = FlaskSession(app.test_client())  # rede volta
        facade.create_activity(task())
        assert len(saved(app)) == 1

    def test_autorizacao_nao_se_aplica_mas_rotas_desconhecidas_e_metodos_invalidos_sao_tratados(self, client):
        assert client.get("/api/nao-existe").status_code == 404
        assert client.patch("/api/activities").status_code == 405


# ==================================================== T2.4 — Builder e Observer
class TestT24BuilderEObserver:
    # -- Builder (criacional) ---------------------------------------------------------------
    def test_builder_com_campos_obrigatorios_aplica_padroes_dos_opcionais(self):
        activity = ActivityBuilder(Task).with_title("  Estudar  ").starting_at("2026-10-08T09:00").build()
        assert activity.title == "Estudar"
        assert (activity.category, activity.priority, activity.recurrence) == ("Geral", "medium", "none")
        assert activity.end == activity.start and activity.status == "pending"
        assert activity.reminder_minutes is None and activity.recurrence_until is None

    def test_builder_com_todos_os_opcionais_encadeados(self):
        activity = (
            ActivityBuilder(Task)
            .with_title("Revisar")
            .described_as(" PR do time ")
            .in_category(" Trabalho / Código ")
            .with_priority("high")
            .starting_at("2026-10-08T09:00")
            .lasting(90)
            .repeating("weekly", "2026-12-01")
            .reminding("15")
            .build()
        )
        assert (activity.description, activity.category, activity.priority) == ("PR do time", "Trabalho/Código", "high")
        assert activity.end.strftime("%H:%M") == "10:30"
        assert (activity.recurrence, str(activity.recurrence_until), activity.reminder_minutes) == ("weekly", "2026-12-01", 15)

    def test_builder_isola_a_responsabilidade_de_montar_e_rejeita_dado_malformado(self):
        with pytest.raises(ValidationError):
            ActivityBuilder(Task).with_title("x").build()  # início obrigatório
        with pytest.raises(ValidationError):
            ActivityBuilder(Task).starting_at("não é data")
        with pytest.raises(ValidationError):
            ActivityBuilder(Task).reminding("muito")

    def test_factory_usa_builder_e_devolve_o_tipo_certo_com_padroes_do_tipo(self):
        meeting = creator_for("meeting").create({"title": "Daily", "start": "2026-10-08T09:00"})
        assert isinstance(meeting, Meeting) and meeting.end > meeting.start  # duração padrão do tipo

    # -- Facade (estrutural) ----------------------------------------------------------------
    def test_facade_do_servidor_simplifica_criar_editar_consultar(self, facade, app):
        created = facade.create_activity(task())
        edited = facade.update_activity(created["id"], {"title": "Novo título", "priority": "low"})
        assert (edited["title"], edited["priority"]) == ("Novo título", "low")
        assert facade.get_activity(created["id"])["title"] == "Novo título"
        assert [o["title"] for o in facade.calendar("2026-10-01", "2026-10-31")] == ["Novo título"]
        assert [a["title"] for a in facade.search("priority:low")] == ["Novo título"]
        assert saved(app)[0]["title"] == "Novo título"

    def test_facade_do_cliente_unifica_comandos_modelo_e_consultas(self, app):
        facade = make_client(app.test_client())
        facade.model.go_today()
        facade.create_activity(task())
        act_id = facade.model.occurrences[0]["id"]
        facade.edit_activity(act_id, {"title": "Editada"})
        assert facade.search("title:Editada")[0]["id"] == act_id
        facade.undo()  # desfaz a edição
        assert facade.model.occurrences[0]["title"] == "Entregar relatório"

    # -- Observer (comportamental) ----------------------------------------------------------
    def test_observer_do_servidor_recebe_eventos_na_ordem_e_deixa_de_receber_ao_cancelar(self, app, client):
        repo = app.config["FACADE"]._store._real

        class Recorder(ServerObserver):
            def __init__(self):
                self.events = []

            def update(self, event):
                self.events.append((event.kind, event.title))

        recorder = Recorder()
        repo.subscribe(recorder)
        created = client.post("/api/activities", json=task()).get_json()
        client.put(f"/api/activities/{created['id']}", json={"title": "B"})
        client.delete(f"/api/activities/{created['id']}")
        assert recorder.events == [("created", "Entregar relatório"), ("updated", "B"), ("deleted", "B")]

        repo.unsubscribe(recorder)
        client.post("/api/activities", json=task())
        assert len(recorder.events) == 3

    def test_observer_nao_dispara_para_operacoes_rejeitadas(self, client):
        client.post("/api/activities", json=task(title=""))
        client.post("/api/activities", json=task(end="2026-10-08T08:00"))
        assert client.get("/api/notifications").get_json() == []

    def test_notificacoes_do_servidor_refletem_cada_alteracao(self, client):
        created = client.post("/api/activities", json=task()).get_json()
        client.put(f"/api/activities/{created['id']}", json={"title": "B"})
        messages = [n["message"] for n in client.get("/api/notifications").get_json()]
        assert messages[0].endswith("atualizada") and messages[-1].endswith("criada")

    def test_observer_do_cliente_atualiza_calendario_e_lembretes_apos_alteracoes(self, ui):
        seen = []

        class Spy(Observer):
            def on_change(self, subject, change):
                seen.append(change)

        ui._model.attach(Spy())
        FakeDialog.data = task()
        ui.day_panel.new_requested.emit()
        assert "refresh" in seen  # modelo notificou os observadores
        assert all("lembrar" not in t for t in day_texts(ui))

        # edita acrescentando lembrete: painel do dia e célula do mês se redesenham sozinhos
        ui.day_panel._list.setCurrentRow(0)
        occurrence = ui.day_panel._list.currentItem().data(0x0100)
        FakeDialog.data = task(reminder_minutes=30)
        ui.day_panel.edit_requested.emit(occurrence)
        assert any("lembrar 30" in t for t in day_texts(ui))
        assert any("Entregar relatório" in t for t in cell_texts(ui, TODAY))

        # desfazer (Ctrl+Z) volta a tela ao estado anterior, também via Observer
        ui._facade.undo()
        assert all("lembrar" not in t for t in day_texts(ui))

        # excluir remove da tela
        ui._facade.undo()
        assert day_texts(ui) == ["Nenhuma atividade neste dia"]

    def test_observer_de_selecao_nao_refaz_chamada_ao_servidor(self, app):
        facade = make_client(app.test_client())
        facade.model.go_today()
        proxy = facade._api
        misses = proxy.misses
        facade.model.select(date(2026, 10, 15))  # mesmo mês: só redesenha
        assert proxy.misses == misses

    def test_estado_da_atividade_muda_e_a_tela_reflete(self, ui):
        FakeDialog.data = task()
        ui.day_panel.new_requested.emit()
        ui.day_panel._list.setCurrentRow(0)
        occurrence = ui.day_panel._list.currentItem().data(0x0100)
        ui.day_panel.status_requested.emit(occurrence, "start")
        assert any("em andamento" in t.lower() for t in day_texts(ui))
        ui.day_panel.status_requested.emit(occurrence, "start")  # transição inválida
        assert ui.warnings and "iniciar" in ui.warnings[-1].lower()
