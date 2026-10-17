"""PADRÃO COMPORTAMENTAL: Command.

Cada ação do usuário que altera dados vira um objeto com ``execute`` e
``undo``. ``CommandHistory`` (invoker) mantém as pilhas de desfazer/refazer.

O desfazer se apoia no servidor (Memento): criar -> excluir; excluir ->
restaurar; alterar/mudar status -> reverter.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from .api import CalendarApi


class Command(ABC):
    description = ""

    @abstractmethod
    def execute(self) -> None: ...

    @abstractmethod
    def undo(self) -> None: ...


class CreateActivityCommand(Command):
    def __init__(self, api: CalendarApi, data: dict):
        self._api = api
        self._data = dict(data)
        self._activity_id: str | None = None
        self.description = f"Criar '{data.get('title', '')}'"

    def execute(self):
        payload = dict(self._data)
        if self._activity_id:  # refazer: reaproveita o mesmo id
            payload["id"] = self._activity_id
        created = self._api.create(payload)
        self._activity_id = created["id"]

    def undo(self):
        self._api.delete(self._activity_id)


class UpdateActivityCommand(Command):
    def __init__(self, api: CalendarApi, activity_id: str, data: dict):
        self._api = api
        self._id = activity_id
        self._data = dict(data)
        self.description = f"Editar '{data.get('title', activity_id)}'"

    def execute(self):
        self._api.update(self._id, self._data)

    def undo(self):
        self._api.revert(self._id)


class DeleteActivityCommand(Command):
    def __init__(self, api: CalendarApi, activity_id: str, title: str = ""):
        self._api = api
        self._id = activity_id
        self.description = f"Excluir '{title or activity_id}'"

    def execute(self):
        self._api.delete(self._id)

    def undo(self):
        self._api.restore(self._id)


class TransitionCommand(Command):
    LABELS = {
        "start": "Iniciar",
        "pause": "Pausar",
        "complete": "Concluir",
        "cancel": "Cancelar",
        "reopen": "Reabrir",
    }

    def __init__(self, api: CalendarApi, activity_id: str, action: str, title: str = ""):
        self._api = api
        self._id = activity_id
        self._action = action
        self.description = f"{self.LABELS.get(action, action)} '{title or activity_id}'"

    def execute(self):
        self._api.transition(self._id, self._action)

    def undo(self):
        self._api.revert(self._id)


class DuplicateActivityCommand(Command):
    def __init__(self, api: CalendarApi, activity_id: str, days: int = 1, title: str = ""):
        self._api = api
        self._id = activity_id
        self._days = days
        self._copy_id: str | None = None
        self.description = f"Duplicar '{title or activity_id}'"

    def execute(self):
        self._copy_id = self._api.duplicate(self._id, self._days)["id"]

    def undo(self):
        self._api.delete(self._copy_id)


class CommandHistory:
    def __init__(self):
        self._undo: list[Command] = []
        self._redo: list[Command] = []

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def next_undo_description(self) -> str:
        return self._undo[-1].description if self._undo else ""

    @property
    def next_redo_description(self) -> str:
        return self._redo[-1].description if self._redo else ""

    def execute(self, command: Command) -> None:
        command.execute()  # se falhar, nada entra no histórico
        self._undo.append(command)
        self._redo.clear()

    def undo(self) -> str:
        if not self._undo:
            return ""
        command = self._undo[-1]
        command.undo()
        self._undo.pop()
        self._redo.append(command)
        return command.description

    def redo(self) -> str:
        if not self._redo:
            return ""
        command = self._redo[-1]
        command.execute()
        self._redo.pop()
        self._undo.append(command)
        return command.description
