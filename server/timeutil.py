"""Funções utilitárias de data/hora."""
from __future__ import annotations

import calendar
from datetime import date, datetime

from .errors import ValidationError

DATETIME_FORMAT = "%Y-%m-%dT%H:%M"
DATE_FORMAT = "%Y-%m-%d"


def parse_datetime(value, label: str = "Data/hora") -> datetime:
    if isinstance(value, datetime):
        return value.replace(second=0, microsecond=0, tzinfo=None)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip())
        except ValueError:
            parsed = None
        if parsed is not None:
            return parsed.replace(second=0, microsecond=0, tzinfo=None)
    raise ValidationError(f"{label} inválida (use AAAA-MM-DDTHH:MM)")


def parse_date(value, label: str = "Data") -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.strip()).date()
        except ValueError:
            pass
    raise ValidationError(f"{label} inválida (use AAAA-MM-DD)")


def add_months(moment: datetime, months: int) -> datetime:
    """Soma meses preservando o dia (ajustado ao último dia do mês, se preciso)."""
    index = moment.month - 1 + months
    year = moment.year + index // 12
    month = index % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)
