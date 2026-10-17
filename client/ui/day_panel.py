"""Painel lateral com as atividades do dia selecionado."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..flyweight import ItemStyleFactory
from ..model import CalendarModel
from ..observer import Observer

WEEKDAY_NAMES = [
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
]

STATUS_ACTIONS = [
    ("Iniciar", "start"),
    ("Pausar", "pause"),
    ("Concluir", "complete"),
    ("Cancelar", "cancel"),
    ("Reabrir", "reopen"),
]


class DayPanel(QWidget, Observer):
    new_requested = pyqtSignal()
    edit_requested = pyqtSignal(object)
    delete_requested = pyqtSignal(object)
    duplicate_requested = pyqtSignal(object)
    status_requested = pyqtSignal(object, str)

    def __init__(self, model: CalendarModel, styles: ItemStyleFactory, parent=None):
        QWidget.__init__(self, parent)
        self._model = model
        self._styles = styles
        self._title = QLabel()
        self._title.setStyleSheet("font-size: 15px; font-weight: bold;")
        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(lambda _item: self._emit_current(self.edit_requested))

        new_button = QPushButton("Nova")
        edit_button = QPushButton("Editar")
        duplicate_button = QPushButton("Duplicar")
        delete_button = QPushButton("Excluir")
        new_button.clicked.connect(self.new_requested)
        edit_button.clicked.connect(lambda: self._emit_current(self.edit_requested))
        duplicate_button.clicked.connect(lambda: self._emit_current(self.duplicate_requested))
        delete_button.clicked.connect(lambda: self._emit_current(self.delete_requested))

        status_button = QToolButton()
        status_button.setText("Status ▾")
        status_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(status_button)
        for label, action in STATUS_ACTIONS:
            menu.addAction(label, lambda a=action: self._emit_status(a))
        status_button.setMenu(menu)

        buttons = QHBoxLayout()
        for widget in (new_button, edit_button, duplicate_button, status_button, delete_button):
            buttons.addWidget(widget)

        layout = QVBoxLayout(self)
        layout.addWidget(self._title)
        layout.addWidget(self._list, 1)
        layout.addLayout(buttons)
        model.attach(self)

    # -- Observer ------------------------------------------------------------
    def on_change(self, subject, change: str) -> None:
        if change in ("refresh", "selection"):
            self.redraw()

    def redraw(self) -> None:
        day = self._model.selected
        self._title.setText(f"{WEEKDAY_NAMES[day.weekday()].capitalize()}, {day:%d/%m/%Y}")
        self._list.clear()
        items = self._model.occurrences_on(day)
        if not items:
            placeholder = QListWidgetItem("Nenhuma atividade neste dia")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self._list.addItem(placeholder)
            return
        for occ in items:
            item = QListWidgetItem(f"{occ['label']}\n{occ['details']}")
            style = self._styles.get(occ["kind"], occ["status"])  # Flyweight
            item.setBackground(QBrush(QColor(style.background)))
            item.setForeground(QBrush(QColor(style.foreground)))
            font = QFont(item.font())
            font.setStrikeOut(style.strike)
            font.setItalic(style.italic)
            font.setBold(style.bold)
            item.setFont(font)
            item.setData(Qt.ItemDataRole.UserRole, occ)
            self._list.addItem(item)

    # -- ações ----------------------------------------------------------------
    def _current(self):
        item = self._list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _emit_current(self, signal) -> None:
        occ = self._current()
        if occ is not None:
            signal.emit(occ)

    def _emit_status(self, action: str) -> None:
        occ = self._current()
        if occ is not None:
            self.status_requested.emit(occ, action)
