"""Janela principal (também é um observador do modelo)."""
from __future__ import annotations

from datetime import date, datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QToolBar,
)

from ..api import ApiError
from ..facade import ClientFacade
from ..flyweight import ItemStyleFactory
from ..observer import Observer
from ..themes import THEMES, ThemeFactory, build_stylesheet
from .activity_dialog import ActivityDialog
from .day_panel import DayPanel
from .dialogs import CategoryTreeDialog, ReportDialog, SearchDialog, StatsDialog
from .month_view import MonthView

MONTH_NAMES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


AUTO_REFRESH_MS = 15_000  # outros clientes podem alterar o calendário: reconsulta periódica


class MainWindow(QMainWindow, Observer):
    def __init__(self, facade: ClientFacade, theme: ThemeFactory | None = None):
        QMainWindow.__init__(self)
        self._facade = facade
        self._model = facade.model
        self._theme = theme or THEMES["claro"]
        self.setWindowTitle("Calendário de Atividades")
        self.resize(1180, 720)

        styles = ItemStyleFactory()  # pool Flyweight único da aplicação
        self.month_view = MonthView(self._model, styles, self._theme)
        self.day_panel = DayPanel(self._model, styles)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.month_view)
        splitter.addWidget(self.day_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        self.month_view.day_selected.connect(self._model.select)
        self.month_view.day_activated.connect(self._new_activity_on)
        self.day_panel.new_requested.connect(lambda: self._new_activity_on(self._model.selected))
        self.day_panel.edit_requested.connect(self._edit_activity)
        self.day_panel.delete_requested.connect(self._delete_activity)
        self.day_panel.duplicate_requested.connect(self._duplicate_activity)
        self.day_panel.status_requested.connect(self._change_status)

        self._month_label = QLabel()
        self._month_label.setStyleSheet("font-size: 17px; font-weight: bold; padding: 0 12px;")
        self._build_toolbar()
        self._model.attach(self)
        self._apply_theme(self._theme)
        self._auto_refresh = QTimer(self)
        self._auto_refresh.timeout.connect(self._poll_server)
        self._auto_refresh.start(AUTO_REFRESH_MS)

    # -- barra de ferramentas ------------------------------------------------------
    def _action(self, text, slot, shortcut=None, checkable=False) -> QAction:
        action = QAction(text, self)
        action.setCheckable(checkable)
        if shortcut:
            action.setShortcut(shortcut)
        action.triggered.connect(slot)
        return action

    def _build_toolbar(self) -> None:
        bar = QToolBar("Principal")
        bar.setMovable(False)
        self.addToolBar(bar)
        bar.addAction(self._action("◀", self._model.previous_month))
        bar.addAction(self._action("Hoje", self._model.go_today))
        bar.addAction(self._action("▶", self._model.next_month))
        bar.addWidget(self._month_label)
        bar.addSeparator()
        bar.addAction(self._action("Nova atividade", lambda: self._new_activity_on(self._model.selected), "Ctrl+N"))
        self._undo_action = self._action("Desfazer", self._facade.undo, "Ctrl+Z")
        self._redo_action = self._action("Refazer", self._facade.redo, "Ctrl+Y")
        bar.addAction(self._undo_action)
        bar.addAction(self._redo_action)
        bar.addSeparator()
        bar.addAction(self._action("Buscar", self._search, "Ctrl+F"))
        bar.addAction(self._action("Categorias", self._show_categories))
        bar.addAction(self._action("Relatórios", self._show_reports))
        bar.addAction(self._action("Estatísticas", self._show_stats))
        bar.addAction(self._action("Exportar", self._export))
        bar.addSeparator()
        bar.addAction(self._action("Atualizar", lambda: self._model.reload(), "F5"))
        self._dark_action = self._action("Tema escuro", self._toggle_theme, checkable=True)
        bar.addAction(self._dark_action)

    def _poll_server(self) -> None:
        if QApplication.activeModalWidget() is None:  # não redesenha por baixo de um diálogo aberto
            self._model.reload()

    # -- Observer ---------------------------------------------------------------------
    def on_change(self, subject, change: str) -> None:
        self._month_label.setText(f"{MONTH_NAMES[subject.month - 1]} {subject.year}")
        history = self._facade.history
        self._undo_action.setEnabled(history.can_undo)
        self._redo_action.setEnabled(history.can_redo)
        self._undo_action.setToolTip(history.next_undo_description)
        self._redo_action.setToolTip(history.next_redo_description)
        if subject.error:
            self.statusBar().showMessage(subject.error)
        elif change == "status":
            self.statusBar().showMessage(subject.status_message, 6000)
        elif change == "refresh" and not subject.status_message:
            self.statusBar().showMessage(f"{len(subject.occurrences)} ocorrência(s) no período exibido")

    # -- tema (Abstract Factory) -----------------------------------------------------------
    def _apply_theme(self, theme: ThemeFactory) -> None:
        self._theme = theme
        QApplication.instance().setStyleSheet(build_stylesheet(theme))
        self.month_view.set_theme(theme)

    def _toggle_theme(self, checked: bool) -> None:
        self._apply_theme(THEMES["escuro" if checked else "claro"])

    # -- operações --------------------------------------------------------------------------
    def _guard(self, func, *args) -> bool:
        try:
            func(*args)
            return True
        except ApiError as exc:
            QMessageBox.warning(self, "Não foi possível concluir", "\n".join(exc.messages))
            self._model.reload()
            return False

    def _new_activity_on(self, day: date) -> None:
        self._model.select(day)
        dialog = ActivityDialog(self, default_day=day)
        if dialog.exec():
            self._guard(self._facade.create_activity, dialog.get_data())

    def _edit_activity(self, occurrence: dict) -> None:
        dialog = ActivityDialog(self, initial=occurrence)
        if dialog.exec():
            data = dialog.get_data()
            data.pop("kind")  # o tipo é imutável
            self._guard(self._facade.edit_activity, occurrence["id"], data)

    def _delete_activity(self, occurrence: dict) -> None:
        answer = QMessageBox.question(
            self,
            "Excluir atividade",
            f"Excluir '{occurrence['title']}'?\n(Você poderá desfazer com Ctrl+Z.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._guard(self._facade.delete_activity, occurrence["id"], occurrence["title"])

    def _duplicate_activity(self, occurrence: dict) -> None:
        days, ok = QInputDialog.getInt(self, "Duplicar atividade", "Deslocar a cópia em quantos dias?", 1, -365, 365)
        if ok:
            self._guard(self._facade.duplicate_activity, occurrence["id"], days, occurrence["title"])

    def _change_status(self, occurrence: dict, action: str) -> None:
        self._guard(self._facade.change_status, occurrence["id"], action, occurrence["title"])

    def _search(self) -> None:
        dialog = SearchDialog(self._facade, self)
        if dialog.exec() and dialog.selected_date:
            self._model.select(dialog.selected_date)

    def _show_categories(self) -> None:
        CategoryTreeDialog(self._facade, self).exec()

    def _show_reports(self) -> None:
        ReportDialog(self._facade, self._model.selected, self).exec()

    def _show_stats(self) -> None:
        StatsDialog(self._facade, self).exec()

    def _export(self) -> None:
        options = {"iCalendar (.ics)": "ics", "CSV (.csv)": "csv", "JSON (.json)": "json"}
        choice, ok = QInputDialog.getItem(self, "Exportar calendário", "Formato:", list(options), 0, False)
        if not ok:
            return
        fmt = options[choice]
        suggested = f"calendario-{datetime.now():%Y%m%d}.{fmt}"
        path, _ = QFileDialog.getSaveFileName(self, "Salvar arquivo", suggested)
        if path:
            if self._guard(self._facade.export_to_file, fmt, path):
                self.statusBar().showMessage(f"Calendário exportado para {path}", 6000)
