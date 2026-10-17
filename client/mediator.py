"""PADRÃO COMPORTAMENTAL: Mediator.

No formulário de atividade os campos não se conhecem: todos avisam o
``ActivityFormMediator``, que concentra as regras de interação (qual campo
habilitar/desabilitar conforme tipo, recorrência, lembrete e título).

Os "colegas" são widgets Qt, mas o mediador só usa métodos simples
(``currentData``, ``text``, ``isChecked``, ``setEnabled``), o que permite
testá-lo com objetos falsos, sem interface gráfica.
"""
from __future__ import annotations


class ActivityFormMediator:
    def __init__(
        self,
        *,
        kind,
        title,
        end,
        location,
        attendees,
        recurrence,
        recurrence_until,
        reminder_enabled,
        reminder_minutes,
        save_button,
    ):
        self._kind = kind
        self._title = title
        self._end = end
        self._location = location
        self._attendees = attendees
        self._recurrence = recurrence
        self._until = recurrence_until
        self._reminder_enabled = reminder_enabled
        self._reminder_minutes = reminder_minutes
        self._save = save_button

    def changed(self, *_args) -> None:
        """Chamado por qualquer colega quando seu valor muda."""
        kind = self._kind.currentData()
        self._end.setEnabled(kind != "reminder")
        self._location.setEnabled(kind in ("meeting", "event"))
        self._attendees.setEnabled(kind == "meeting")
        self._until.setEnabled(self._recurrence.currentData() != "none")
        self._reminder_minutes.setEnabled(self._reminder_enabled.isChecked())
        self._save.setEnabled(bool(self._title.text().strip()))
