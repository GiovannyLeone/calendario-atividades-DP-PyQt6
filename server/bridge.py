"""PADRÃO ESTRUTURAL: Bridge.

Duas hierarquias independentes que variam separadamente:
  * Abstração:     ``Report`` -> ``DailyReport``, ``WeeklyReport``, ``MonthlyReport``
  * Implementação: ``ReportFormatter`` -> ``TextFormatter``, ``JsonFormatter``, ``HtmlFormatter``

Qualquer relatório pode ser renderizado em qualquer formato.
"""
from __future__ import annotations

import calendar
import html
import json
from abc import ABC, abstractmethod
from datetime import date, timedelta

from .errors import ValidationError
from .iterators import DateRangeIterator

WEEKDAYS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


def _group_by_date(start: date, end: date, entries: list[dict]):
    by_day: dict[str, list[dict]] = {}
    for entry in entries:
        by_day.setdefault(entry["date"], []).append(entry)
    for day in DateRangeIterator(start, end):
        yield day, by_day.get(day.isoformat(), [])


# ---------------------------------------------------------------- implementação
class ReportFormatter(ABC):
    content_type = "text/plain"

    @abstractmethod
    def format(self, title: str, start: date, end: date, entries: list[dict]) -> str: ...


class TextFormatter(ReportFormatter):
    content_type = "text/plain"

    def format(self, title, start, end, entries):
        lines = [title, f"Período: {start:%d/%m/%Y} a {end:%d/%m/%Y}", "=" * 48]
        for day, items in _group_by_date(start, end, entries):
            lines.append(f"{WEEKDAYS[day.weekday()]} {day:%d/%m/%Y}")
            if not items:
                lines.append("  — sem atividades")
            for item in items:
                lines.append(f"  {item['label']}  [{item['kind_label']}]")
        lines.append(f"Total de ocorrências: {len(entries)}")
        return "\n".join(lines) + "\n"


class JsonFormatter(ReportFormatter):
    content_type = "application/json"

    def format(self, title, start, end, entries):
        return json.dumps(
            {"title": title, "start": start.isoformat(), "end": end.isoformat(), "entries": entries},
            ensure_ascii=False,
            indent=2,
        )


class HtmlFormatter(ReportFormatter):
    content_type = "text/html"

    def format(self, title, start, end, entries):
        esc = html.escape
        parts = [
            "<!doctype html><html lang='pt-BR'><meta charset='utf-8'>",
            f"<title>{esc(title)}</title><body>",
            f"<h1>{esc(title)}</h1>",
            f"<p>Período: {start:%d/%m/%Y} a {end:%d/%m/%Y}</p>",
        ]
        for day, items in _group_by_date(start, end, entries):
            parts.append(f"<h2>{WEEKDAYS[day.weekday()]} {day:%d/%m/%Y}</h2><ul>")
            if not items:
                parts.append("<li><em>sem atividades</em></li>")
            for item in items:
                parts.append(f"<li>{esc(item['label'])} <small>[{esc(item['kind_label'])}]</small></li>")
            parts.append("</ul>")
        parts.append(f"<p><strong>Total de ocorrências:</strong> {len(entries)}</p></body></html>")
        return "\n".join(parts)


# ---------------------------------------------------------------- abstração
class Report(ABC):
    title = "Relatório"

    def __init__(self, provider, formatter: ReportFormatter):
        self._provider = provider  # callable (início, fim) -> lista de ocorrências
        self._formatter = formatter

    @property
    def content_type(self) -> str:
        return self._formatter.content_type

    @abstractmethod
    def period(self, reference: date) -> tuple[date, date]: ...

    def render(self, reference: date) -> str:
        start, end = self.period(reference)
        return self._formatter.format(self.title, start, end, self._provider(start, end))


class DailyReport(Report):
    title = "Relatório diário"

    def period(self, reference):
        return reference, reference


class WeeklyReport(Report):
    title = "Relatório semanal"

    def period(self, reference):
        monday = reference - timedelta(days=reference.weekday())
        return monday, monday + timedelta(days=6)


class MonthlyReport(Report):
    title = "Relatório mensal"

    def period(self, reference):
        last = calendar.monthrange(reference.year, reference.month)[1]
        return reference.replace(day=1), reference.replace(day=last)


REPORTS = {"daily": DailyReport, "weekly": WeeklyReport, "monthly": MonthlyReport}
FORMATTERS = {"text": TextFormatter, "json": JsonFormatter, "html": HtmlFormatter}


def make_report(kind: str, fmt: str, provider) -> Report:
    if kind not in REPORTS:
        raise ValidationError(f"Relatório desconhecido: {kind!r}. Use: {', '.join(REPORTS)}")
    if fmt not in FORMATTERS:
        raise ValidationError(f"Formato desconhecido: {fmt!r}. Use: {', '.join(FORMATTERS)}")
    return REPORTS[kind](provider, FORMATTERS[fmt]())
