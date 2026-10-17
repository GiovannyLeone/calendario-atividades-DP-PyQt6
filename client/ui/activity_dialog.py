"""Formulário de criação/edição de atividade (usa o Mediator)."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from PyQt6.QtCore import QDate, QDateTime, QTime
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..mediator import ActivityFormMediator

KINDS = [("Tarefa", "task"), ("Reunião", "meeting"), ("Lembrete", "reminder"), ("Evento", "event")]
PRIORITIES = [("Baixa", "low"), ("Média", "medium"), ("Alta", "high")]
RECURRENCES = [("Não repete", "none"), ("Diariamente", "daily"), ("Semanalmente", "weekly"), ("Mensalmente", "monthly")]
CATEGORIES = [
    "Geral", "Trabalho", "Trabalho/Reuniões", "Trabalho/Desenvolvimento",
    "Estudos", "Pessoal", "Pessoal/Finanças", "Pessoal/Social", "Saúde",
]


def _qdatetime(value: datetime) -> QDateTime:
    return QDateTime(QDate(value.year, value.month, value.day), QTime(value.hour, value.minute))


def _pydatetime(widget: QDateTimeEdit) -> datetime:
    return widget.dateTime().toPyDateTime().replace(second=0, microsecond=0, tzinfo=None)


class ActivityDialog(QDialog):
    def __init__(self, parent=None, initial: dict | None = None, default_day: date | None = None):
        super().__init__(parent)
        self._editing = initial is not None
        self.setWindowTitle("Editar atividade" if self._editing else "Nova atividade")
        self.setMinimumWidth(460)

        self.kind = QComboBox()
        for label, value in KINDS:
            self.kind.addItem(label, value)
        self.title = QLineEdit()
        self.title.setMaxLength(80)
        self.description = QPlainTextEdit()
        self.description.setFixedHeight(60)
        self.category = QComboBox()
        self.category.setEditable(True)
        self.category.addItems(CATEGORIES)
        self.priority = QComboBox()
        for label, value in PRIORITIES:
            self.priority.addItem(label, value)
        self.priority.setCurrentIndex(1)

        base = datetime.combine(default_day or date.today(), datetime.min.time()).replace(hour=9)
        self.start = QDateTimeEdit(_qdatetime(base))
        self.end = QDateTimeEdit(_qdatetime(base + timedelta(hours=1)))
        for widget in (self.start, self.end):
            widget.setCalendarPopup(True)
            widget.setDisplayFormat("dd/MM/yyyy HH:mm")

        self.recurrence = QComboBox()
        for label, value in RECURRENCES:
            self.recurrence.addItem(label, value)
        self.until = QDateEdit(QDate(base.year, base.month, base.day).addMonths(3))
        self.until.setCalendarPopup(True)
        self.until.setDisplayFormat("dd/MM/yyyy")

        self.reminder_enabled = QCheckBox("Lembrar")
        self.reminder_minutes = QSpinBox()
        self.reminder_minutes.setRange(0, 10080)
        self.reminder_minutes.setValue(15)
        self.reminder_minutes.setSuffix(" min antes")
        reminder_row = QWidget()
        row_layout = QHBoxLayout(reminder_row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(self.reminder_enabled)
        row_layout.addWidget(self.reminder_minutes, 1)

        self.location = QLineEdit()
        self.attendees = QLineEdit()
        self.attendees.setPlaceholderText("nomes separados por vírgula")

        form = QFormLayout()
        form.addRow("Tipo", self.kind)
        form.addRow("Título", self.title)
        form.addRow("Descrição", self.description)
        form.addRow("Categoria", self.category)
        form.addRow("Prioridade", self.priority)
        form.addRow("Início", self.start)
        form.addRow("Término", self.end)
        form.addRow("Repetição", self.recurrence)
        form.addRow("Repetir até", self.until)
        form.addRow("Lembrete", reminder_row)
        form.addRow("Local", self.location)
        form.addRow("Participantes", self.attendees)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.buttons)

        # Mediator: todos os campos avisam o mediador, que ajusta os demais.
        self._mediator = ActivityFormMediator(
            kind=self.kind,
            title=self.title,
            end=self.end,
            location=self.location,
            attendees=self.attendees,
            recurrence=self.recurrence,
            recurrence_until=self.until,
            reminder_enabled=self.reminder_enabled,
            reminder_minutes=self.reminder_minutes,
            save_button=self.buttons.button(QDialogButtonBox.StandardButton.Save),
        )
        self.kind.currentIndexChanged.connect(self._mediator.changed)
        self.title.textChanged.connect(self._mediator.changed)
        self.recurrence.currentIndexChanged.connect(self._mediator.changed)
        self.reminder_enabled.toggled.connect(self._mediator.changed)

        if initial:
            self._load(initial)
        self._mediator.changed()

    def _load(self, data: dict) -> None:
        self.kind.setCurrentIndex(max(0, self.kind.findData(data["kind"])))
        self.kind.setEnabled(False)  # o tipo não pode ser alterado
        self.title.setText(data["title"])
        self.description.setPlainText(data.get("description", ""))
        self.category.setCurrentText(data.get("category", "Geral"))
        self.priority.setCurrentIndex(max(0, self.priority.findData(data["priority"])))
        self.start.setDateTime(_qdatetime(datetime.fromisoformat(data["start"])))
        self.end.setDateTime(_qdatetime(datetime.fromisoformat(data["end"])))
        self.recurrence.setCurrentIndex(max(0, self.recurrence.findData(data["recurrence"])))
        if data.get("recurrence_until"):
            until = date.fromisoformat(data["recurrence_until"])
            self.until.setDate(QDate(until.year, until.month, until.day))
        if data.get("reminder_minutes") is not None:
            self.reminder_enabled.setChecked(True)
            self.reminder_minutes.setValue(int(data["reminder_minutes"]))
        self.location.setText(data.get("location", ""))
        self.attendees.setText(", ".join(data.get("attendees", [])))

    def get_data(self) -> dict:
        kind = self.kind.currentData()
        start = _pydatetime(self.start)
        end = start if kind == "reminder" else _pydatetime(self.end)
        recurrence = self.recurrence.currentData()
        return {
            "kind": kind,
            "title": self.title.text().strip(),
            "description": self.description.toPlainText().strip(),
            "category": self.category.currentText().strip(),
            "priority": self.priority.currentData(),
            "start": start.strftime("%Y-%m-%dT%H:%M"),
            "end": end.strftime("%Y-%m-%dT%H:%M"),
            "recurrence": recurrence,
            "recurrence_until": self.until.date().toPyDate().isoformat() if recurrence != "none" else None,
            "reminder_minutes": self.reminder_minutes.value() if self.reminder_enabled.isChecked() else None,
            "location": self.location.text().strip(),
            "attendees": self.attendees.text().strip(),
        }
