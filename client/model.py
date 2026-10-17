"""Modelo observável do calendário (sujeito do Observer)."""
from __future__ import annotations

from datetime import date, timedelta

from .api import ApiError, CalendarApi
from .observer import Subject


class CalendarModel(Subject):
    GRID_DAYS = 42  # 6 semanas x 7 dias

    def __init__(self, api: CalendarApi, today: date | None = None):
        super().__init__()
        self._api = api
        self.today = today or date.today()
        self.year = self.today.year
        self.month = self.today.month
        self.selected = self.today
        self.occurrences: list[dict] = []
        self.error: str | None = None
        self.status_message = ""

    # -- grade do mês (domingo a sábado) ------------------------------------
    def grid_start(self) -> date:
        first = date(self.year, self.month, 1)
        return first - timedelta(days=(first.weekday() + 1) % 7)

    def grid_dates(self) -> list[date]:
        start = self.grid_start()
        return [start + timedelta(days=i) for i in range(self.GRID_DAYS)]

    # -- dados -----------------------------------------------------------------
    def refresh(self) -> None:
        dates = self.grid_dates()
        try:
            self.occurrences = self._api.calendar(dates[0].isoformat(), dates[-1].isoformat())
            self.error = None
        except ApiError as exc:
            self.occurrences = []
            self.error = str(exc)
        self.notify("refresh")

    def reload(self) -> None:
        """Como ``refresh``, mas ignora o cache: mostra o que está no servidor agora."""
        self._api.invalidate()
        self.refresh()

    def occurrences_on(self, day: date) -> list[dict]:
        key = day.isoformat()
        return [o for o in self.occurrences if o["date"] == key]

    def set_status(self, message: str) -> None:
        self.status_message = message
        self.notify("status")

    # -- navegação -------------------------------------------------------------
    def next_month(self) -> None:
        self._goto(self.year + (self.month // 12), self.month % 12 + 1)

    def previous_month(self) -> None:
        self._goto(self.year - (1 if self.month == 1 else 0), 12 if self.month == 1 else self.month - 1)

    def go_today(self) -> None:
        self.selected = self.today
        self._goto(self.today.year, self.today.month)

    def select(self, day: date) -> None:
        self.selected = day
        if (day.year, day.month) != (self.year, self.month):
            self._goto(day.year, day.month)
        else:
            self.notify("selection")

    def _goto(self, year: int, month: int) -> None:
        self.year, self.month = year, month
        # mantém a seleção dentro do mês exibido
        if (self.selected.year, self.selected.month) != (year, month):
            self.selected = date(year, month, 1)
        self.refresh()
