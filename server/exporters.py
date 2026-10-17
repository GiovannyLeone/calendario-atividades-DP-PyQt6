"""Exportação do calendário.

Padrões neste módulo:
  * Template Method -> ``Exporter.export`` define o esqueleto (cabeçalho, itens,
    rodapé) e as subclasses preenchem os passos.
  * Adapter         -> ``ActivityIcsAdapter`` adapta ``Activity`` à interface
    ``IcsComponent`` exigida pelo formato iCalendar.
"""
from __future__ import annotations

import csv
import io
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from .errors import ValidationError


# ----------------------------------------------------------------- Template Method
class Exporter(ABC):
    content_type = "text/plain"
    extension = "txt"
    newline = "\n"

    def export(self, activities) -> str:  # método-modelo
        header = self.header()
        body = self.join_items([self.item(a) for a in activities])
        footer = self.footer()
        parts = [p for p in (header, body, footer) if p]
        return self.newline.join(parts) + self.newline

    def header(self) -> str:
        return ""

    def footer(self) -> str:
        return ""

    def join_items(self, items: list[str]) -> str:
        return self.newline.join(items)

    @abstractmethod
    def item(self, activity) -> str: ...


class CsvExporter(Exporter):
    content_type = "text/csv"
    extension = "csv"
    COLUMNS = (
        "id", "kind", "title", "description", "start", "end", "category",
        "priority", "status", "recurrence", "recurrence_until", "reminder_minutes",
    )

    def _row(self, values) -> str:
        buffer = io.StringIO()
        csv.writer(buffer, lineterminator="").writerow(values)
        return buffer.getvalue()

    def header(self):
        return self._row(self.COLUMNS)

    def item(self, activity):
        data = activity.to_dict()
        return self._row([data[c] if data[c] is not None else "" for c in self.COLUMNS])


class JsonExporter(Exporter):
    content_type = "application/json"
    extension = "json"

    def header(self):
        return "["

    def footer(self):
        return "]"

    def join_items(self, items):
        return ",\n".join("  " + item for item in items)

    def item(self, activity):
        return json.dumps(activity.to_dict(), ensure_ascii=False)


# ----------------------------------------------------------------------- Adapter
class IcsComponent(ABC):
    """Interface-alvo: algo que sabe se escrever como VEVENT."""

    @abstractmethod
    def to_ics(self) -> str: ...


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    )


class ActivityIcsAdapter(IcsComponent):
    """Adapter: adapta ``Activity`` (adaptado) para ``IcsComponent`` (alvo)."""

    _RRULE = {"daily": "DAILY", "weekly": "WEEKLY", "monthly": "MONTHLY"}
    _PRIORITY = {"high": 1, "medium": 5, "low": 9}

    def __init__(self, activity):
        self._activity = activity

    def to_ics(self) -> str:
        a = self._activity
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        lines = [
            "BEGIN:VEVENT",
            f"UID:{a.id}@calendario-atividades",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{a.start:%Y%m%dT%H%M%S}",
            f"DTEND:{a.end:%Y%m%dT%H%M%S}",
            f"SUMMARY:{_escape(a.title)}",
            f"CATEGORIES:{_escape(a.category)}",
            f"PRIORITY:{self._PRIORITY[a.priority]}",
        ]
        if a.description:
            lines.append(f"DESCRIPTION:{_escape(a.description)}")
        location = getattr(a, "location", "")
        if location:
            lines.append(f"LOCATION:{_escape(location)}")
        if a.recurrence in self._RRULE:
            rule = f"RRULE:FREQ={self._RRULE[a.recurrence]}"
            if a.recurrence_until:
                rule += f";UNTIL={a.recurrence_until:%Y%m%d}T235959"
            lines.append(rule)
        if a.status == "cancelled":
            lines.append("STATUS:CANCELLED")
        if a.reminder_minutes is not None:
            lines += [
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                f"DESCRIPTION:{_escape(a.title)}",
                f"TRIGGER:-PT{a.reminder_minutes}M",
                "END:VALARM",
            ]
        lines.append("END:VEVENT")
        return "\r\n".join(lines)


class IcsExporter(Exporter):
    content_type = "text/calendar"
    extension = "ics"
    newline = "\r\n"

    def header(self):
        return "\r\n".join(
            ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Calendario de Atividades//PT-BR//EN"]
        )

    def footer(self):
        return "END:VCALENDAR"

    def item(self, activity):
        return ActivityIcsAdapter(activity).to_ics()


EXPORTERS = {"csv": CsvExporter, "json": JsonExporter, "ics": IcsExporter}


def get_exporter(fmt: str) -> Exporter:
    try:
        return EXPORTERS[fmt]()
    except KeyError:
        raise ValidationError(
            f"Formato de exportação desconhecido: {fmt!r}. Use: {', '.join(EXPORTERS)}"
        ) from None
