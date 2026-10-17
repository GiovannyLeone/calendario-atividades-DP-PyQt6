"""PADRÃO ESTRUTURAL: Facade (lado do cliente).

``ClientFacade`` oferece à interface gráfica operações de alto nível. Por
trás dela estão a API (com proxy de cache), os comandos com desfazer/refazer
e o modelo observável.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from .api import CalendarApi
from .commands import (
    Command,
    CommandHistory,
    CreateActivityCommand,
    DeleteActivityCommand,
    DuplicateActivityCommand,
    TransitionCommand,
    UpdateActivityCommand,
)
from .model import CalendarModel


class ClientFacade:
    def __init__(self, api: CalendarApi, model: CalendarModel, history: CommandHistory | None = None):
        self._api = api
        self.model = model
        self.history = history or CommandHistory()

    # -- escritas (todas passam por comandos) -------------------------------
    def _run(self, command: Command) -> None:
        self.history.execute(command)
        self.model.set_status(command.description)
        self.model.refresh()

    def create_activity(self, data: dict) -> None:
        self._run(CreateActivityCommand(self._api, data))

    def edit_activity(self, activity_id: str, data: dict) -> None:
        self._run(UpdateActivityCommand(self._api, activity_id, data))

    def delete_activity(self, activity_id: str, title: str = "") -> None:
        self._run(DeleteActivityCommand(self._api, activity_id, title))

    def duplicate_activity(self, activity_id: str, days: int = 1, title: str = "") -> None:
        self._run(DuplicateActivityCommand(self._api, activity_id, days, title))

    def change_status(self, activity_id: str, action: str, title: str = "") -> None:
        self._run(TransitionCommand(self._api, activity_id, action, title))

    def undo(self) -> None:
        description = self.history.undo()
        if description:
            self.model.set_status(f"Desfeito: {description}")
            self.model.refresh()

    def redo(self) -> None:
        description = self.history.redo()
        if description:
            self.model.set_status(f"Refeito: {description}")
            self.model.refresh()

    # -- leituras ----------------------------------------------------------------
    def search(self, query: str) -> list:
        return self._api.search(query)

    def stats(self) -> dict:
        return self._api.stats()

    def category_tree(self) -> dict:
        return self._api.categories()

    def server_notifications(self) -> list:
        return self._api.notifications()

    def report(self, kind: str, reference: date, fmt: str = "text") -> str:
        return self._api.report(kind, reference.isoformat(), fmt)

    def export_to_file(self, fmt: str, path: str) -> None:
        Path(path).write_text(self._api.export(fmt), encoding="utf-8", newline="")
