"""PADRÃO COMPORTAMENTAL: State.

O ciclo de vida de uma atividade é modelado por estados concretos. Cada
estado decide quais ações são válidas e para qual estado a atividade vai.

    pendente --iniciar--> em andamento --concluir--> concluída
       |  \\                  |  \\                      |
       |   +--concluir-------+   +--cancelar--> cancelada
       +--cancelar--------------------^                 |
       ^------------------reabrir-----------------------+
"""
from __future__ import annotations

from abc import ABC

from .errors import InvalidTransition, ValidationError

ACTIONS = ("start", "pause", "complete", "cancel", "reopen")
_ACTION_LABELS = {
    "start": "iniciar",
    "pause": "pausar",
    "complete": "concluir",
    "cancel": "cancelar",
    "reopen": "reabrir",
}


class ActivityState(ABC):
    name = "state"
    label = ""

    def _refuse(self, action: str):
        raise InvalidTransition(
            f"Não é possível {_ACTION_LABELS[action]} uma atividade {self.label}"
        )

    def start(self, activity):
        self._refuse("start")

    def pause(self, activity):
        self._refuse("pause")

    def complete(self, activity):
        self._refuse("complete")

    def cancel(self, activity):
        self._refuse("cancel")

    def reopen(self, activity):
        self._refuse("reopen")


class PendingState(ActivityState):
    name = "pending"
    label = "pendente"

    def start(self, activity):
        activity._state = InProgressState()

    def complete(self, activity):
        activity._state = DoneState()

    def cancel(self, activity):
        activity._state = CancelledState()


class InProgressState(ActivityState):
    name = "in_progress"
    label = "em andamento"

    def pause(self, activity):
        activity._state = PendingState()

    def complete(self, activity):
        activity._state = DoneState()

    def cancel(self, activity):
        activity._state = CancelledState()


class DoneState(ActivityState):
    name = "done"
    label = "concluída"

    def reopen(self, activity):
        activity._state = PendingState()


class CancelledState(ActivityState):
    name = "cancelled"
    label = "cancelada"

    def reopen(self, activity):
        activity._state = PendingState()


_STATES = {s.name: s for s in (PendingState, InProgressState, DoneState, CancelledState)}


def state_from_name(name: str) -> ActivityState:
    try:
        return _STATES[name]()
    except KeyError:
        raise ValidationError(f"Status desconhecido: {name!r}") from None


def apply_action(activity, action: str) -> None:
    if action not in ACTIONS:
        raise ValidationError(f"Ação desconhecida: {action!r}. Use: {', '.join(ACTIONS)}")
    getattr(activity._state, action)(activity)
