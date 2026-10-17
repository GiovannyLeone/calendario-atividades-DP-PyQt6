"""PADRÃO COMPORTAMENTAL: Iterator.

* ``DateRangeIterator``  percorre dias de um intervalo.
* ``OccurrenceIterator`` percorre, de forma preguiçosa, as ocorrências de uma
  atividade (única ou recorrente) dentro de uma janela de datas.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from .timeutil import add_months


class DateRangeIterator:
    def __init__(self, start: date, end: date):
        self._current = start
        self._end = end

    def __iter__(self):
        return self

    def __next__(self) -> date:
        if self._current > self._end:
            raise StopIteration
        value = self._current
        self._current += timedelta(days=1)
        return value


class OccurrenceIterator:
    def __init__(self, activity, window_start: date, window_end: date):
        self._activity = activity
        self._ws = window_start
        self._we = window_end
        self._last = window_end
        if activity.recurrence != "none" and activity.recurrence_until:
            self._last = min(window_end, activity.recurrence_until)
        self._index = self._first_index()

    def __iter__(self):
        return self

    def _nth_start(self, k: int) -> datetime:
        a = self._activity
        if a.recurrence == "none":
            return a.start
        if a.recurrence == "daily":
            return a.start + timedelta(days=k)
        if a.recurrence == "weekly":
            return a.start + timedelta(weeks=k)
        return add_months(a.start, k)  # monthly

    def _first_index(self) -> int:
        a = self._activity
        if a.recurrence == "none":
            return 0
        gap_days = (self._ws - a.start.date()).days
        span_days = (a.end.date() - a.start.date()).days
        if a.recurrence == "daily":
            return max(0, gap_days - span_days)
        if a.recurrence == "weekly":
            return max(0, (gap_days - span_days) // 7)
        months = (self._ws.year - a.start.year) * 12 + (self._ws.month - a.start.month)
        return max(0, months - 2)

    def __next__(self) -> tuple[datetime, datetime]:
        a = self._activity
        while True:
            if a.recurrence == "none" and self._index > 0:
                raise StopIteration
            start = self._nth_start(self._index)
            if start.date() > self._last:
                raise StopIteration
            end = start + (a.end - a.start)
            self._index += 1
            if end.date() >= self._ws:
                return start, end
