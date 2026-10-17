"""PADRÃO CRIACIONAL: Builder.

``ActivityBuilder`` monta uma atividade passo a passo (interface fluente),
cuidando de normalização e conversão de tipos. Quem usa não precisa conhecer
o construtor longo de ``Activity``.
"""
from __future__ import annotations

from datetime import timedelta

from .errors import ValidationError
from .timeutil import parse_date, parse_datetime


def _text(value, label: str) -> str:
    """Aceita texto (ou ausência); qualquer outro tipo é entrada malformada."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValidationError(f"{label} deve ser um texto")
    return value.strip()


class ActivityBuilder:
    def __init__(self, activity_class):
        self._cls = activity_class
        self._fields: dict = {}
        self._extra: dict = {}
        self._start = None
        self._end = None
        self._duration = None

    def with_id(self, activity_id):
        if activity_id:
            self._fields["id"] = str(activity_id)
        return self

    def with_title(self, title):
        self._fields["title"] = _text(title, "O título")
        return self

    def described_as(self, text):
        self._fields["description"] = _text(text, "A descrição")
        return self

    def in_category(self, category):
        parts = [p.strip() for p in _text(category, "A categoria").split("/") if p.strip()]
        self._fields["category"] = "/".join(parts) or "Geral"
        return self

    def with_priority(self, priority):
        self._fields["priority"] = priority or "medium"
        return self

    def starting_at(self, value):
        self._start = parse_datetime(value, "Data/hora de início")
        return self

    def ending_at(self, value):
        self._end = parse_datetime(value, "Data/hora de término")
        return self

    def lasting(self, minutes: int):
        self._duration = timedelta(minutes=minutes)
        return self

    def repeating(self, recurrence, until=None):
        self._fields["recurrence"] = recurrence or "none"
        self._fields["recurrence_until"] = (
            parse_date(until, "Data final da recorrência") if until else None
        )
        return self

    def reminding(self, minutes):
        if minutes in (None, ""):
            self._fields["reminder_minutes"] = None
            return self
        try:
            self._fields["reminder_minutes"] = int(minutes)
        except (TypeError, ValueError):
            raise ValidationError(
                "A antecedência do lembrete deve ser um número inteiro de minutos"
            ) from None
        return self

    def with_status(self, status):
        self._fields["status"] = status or "pending"
        return self

    def with_extra(self, **extra):
        self._extra.update(extra)
        return self

    def build(self):
        if self._start is None:
            raise ValidationError("Data/hora de início é obrigatória")
        end = self._end
        if end is None:
            end = self._start + (self._duration or timedelta(0))
        return self._cls(
            self._fields.get("title", ""),
            self._start,
            end,
            **{k: v for k, v in self._fields.items() if k != "title"},
            **self._extra,
        )
