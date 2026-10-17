"""Grade mensal do calendário (observador do modelo)."""
from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QGridLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from ..flyweight import ItemStyleFactory
from ..model import CalendarModel
from ..observer import Observer
from ..themes import ThemeFactory

WEEKDAYS = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]
MAX_VISIBLE = 3


class DayCell(QFrame):
    selected = pyqtSignal(object)  # date
    activated = pyqtSignal(object)  # date (duplo clique)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dayCell")
        self.setMinimumSize(96, 84)
        self._date: date | None = None
        self._header = QLabel()
        self._entries = [QLabel() for _ in range(MAX_VISIBLE)]
        self._more = QLabel()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        layout.addWidget(self._header)
        for label in self._entries:
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            layout.addWidget(label)
        layout.addWidget(self._more)
        layout.addStretch(1)

    def show_day(self, day, occurrences, styles: ItemStyleFactory, theme: ThemeFactory, *, selected, today, other_month):
        self._date = day
        palette = theme.create_palette()
        self.setStyleSheet(theme.create_cell_style().css(selected, today, other_month))
        muted = palette.muted if other_month else palette.text
        weight = "bold" if today else "normal"
        self._header.setText(str(day.day))
        self._header.setStyleSheet(f"color: {muted}; font-weight: {weight}; background: transparent;")
        for index, label in enumerate(self._entries):
            if index < len(occurrences):
                occ = occurrences[index]
                style = styles.get(occ["kind"], occ["status"])  # Flyweight compartilhado
                label.setText(f"{occ['occurrence_start'][11:16]} {occ['title']}")
                label.setStyleSheet(style.css())
                label.setToolTip(occ["label"])
                label.show()
            else:
                label.hide()
        extra = len(occurrences) - MAX_VISIBLE
        self._more.setText(f"+{extra} mais" if extra > 0 else "")
        self._more.setStyleSheet(f"color: {palette.muted}; font-size: 11px; background: transparent;")

    def mousePressEvent(self, event):
        if self._date is not None:
            self.selected.emit(self._date)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self._date is not None:
            self.activated.emit(self._date)
        super().mouseDoubleClickEvent(event)


class MonthView(QWidget, Observer):
    day_selected = pyqtSignal(object)
    day_activated = pyqtSignal(object)

    def __init__(self, model: CalendarModel, styles: ItemStyleFactory, theme: ThemeFactory, parent=None):
        QWidget.__init__(self, parent)
        self._model = model
        self._styles = styles
        self._theme = theme
        grid = QGridLayout(self)
        grid.setSpacing(3)
        for column, name in enumerate(WEEKDAYS):
            label = QLabel(name)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(label, 0, column)
        self._cells: list[DayCell] = []
        for index in range(model.GRID_DAYS):
            cell = DayCell()
            cell.selected.connect(self.day_selected)
            cell.activated.connect(self.day_activated)
            grid.addWidget(cell, 1 + index // 7, index % 7)
            self._cells.append(cell)
        for column in range(7):
            grid.setColumnStretch(column, 1)
        for row in range(1, 7):
            grid.setRowStretch(row, 1)
        model.attach(self)

    def set_theme(self, theme: ThemeFactory) -> None:
        self._theme = theme
        self.redraw()

    def on_change(self, subject, change: str) -> None:
        if change in ("refresh", "selection"):
            self.redraw()

    def redraw(self) -> None:
        model = self._model
        for day, cell in zip(model.grid_dates(), self._cells):
            cell.show_day(
                day,
                model.occurrences_on(day),
                self._styles,
                self._theme,
                selected=day == model.selected,
                today=day == model.today,
                other_month=day.month != model.month,
            )
