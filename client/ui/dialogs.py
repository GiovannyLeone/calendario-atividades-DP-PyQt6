"""Diálogos auxiliares: busca, relatórios, categorias e estatísticas."""
from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from ..api import ApiError
from ..facade import ClientFacade

KIND_LABELS = {"task": "Tarefa", "meeting": "Reunião", "reminder": "Lembrete", "event": "Evento"}
PRIORITY_LABELS = {"low": "Baixa", "medium": "Média", "high": "Alta"}
STATUS_LABELS = {
    "pending": "Pendente", "in_progress": "Em andamento", "done": "Concluída", "cancelled": "Cancelada",
}


def _fmt_minutes(total: int) -> str:
    hours, minutes = divmod(int(total), 60)
    return f"{hours}h{minutes:02d}"


class SearchDialog(QDialog):
    """Busca usando a linguagem de consulta interpretada pelo servidor."""

    HINT = 'Exemplos: priority:high AND status:pending  |  reunião NOT kind:task  |  category:Trabalho'

    def __init__(self, facade: ClientFacade, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Buscar atividades")
        self.setMinimumSize(520, 420)
        self._facade = facade
        self.selected_date: date | None = None

        self._query = QLineEdit()
        self._query.setPlaceholderText("Digite a consulta e pressione Enter")
        self._query.returnPressed.connect(self._search)
        search_button = QPushButton("Buscar")
        search_button.clicked.connect(self._search)
        self._message = QLabel(self.HINT)
        self._message.setWordWrap(True)
        self._results = QListWidget()
        self._results.itemDoubleClicked.connect(self._open_item)

        row = QHBoxLayout()
        row.addWidget(self._query, 1)
        row.addWidget(search_button)
        layout = QVBoxLayout(self)
        layout.addLayout(row)
        layout.addWidget(self._message)
        layout.addWidget(self._results, 1)
        layout.addWidget(QLabel("Dê dois cliques em um resultado para ir até o dia."))

    def _search(self) -> None:
        self._results.clear()
        try:
            found = self._facade.search(self._query.text())
        except ApiError as exc:
            self._message.setText("\n".join(exc.messages))
            return
        self._message.setText(f"{len(found)} resultado(s)")
        for activity in found:
            text = (
                f"{activity['start'][8:10]}/{activity['start'][5:7]}/{activity['start'][:4]} "
                f"{activity['start'][11:16]} — {activity['title']}  "
                f"[{KIND_LABELS.get(activity['kind'], activity['kind'])}, {activity['category']}]"
            )
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, activity["start"][:10])
            self._results.addItem(item)

    def _open_item(self, item: QListWidgetItem) -> None:
        self.selected_date = date.fromisoformat(item.data(Qt.ItemDataRole.UserRole))
        self.accept()


class ReportDialog(QDialog):
    def __init__(self, facade: ClientFacade, reference: date, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Relatórios")
        self.setMinimumSize(560, 460)
        self._facade = facade
        self._reference = reference

        self._kind = QComboBox()
        for label, value in (("Diário", "daily"), ("Semanal", "weekly"), ("Mensal", "monthly")):
            self._kind.addItem(label, value)
        self._format = QComboBox()
        for label, value in (("Texto", "text"), ("HTML", "html")):
            self._format.addItem(label, value)
        generate = QPushButton("Gerar")
        generate.clicked.connect(self._generate)
        self._view = QTextBrowser()

        row = QHBoxLayout()
        row.addWidget(QLabel(f"Referência: {reference:%d/%m/%Y}"))
        row.addStretch(1)
        row.addWidget(self._kind)
        row.addWidget(self._format)
        row.addWidget(generate)
        layout = QVBoxLayout(self)
        layout.addLayout(row)
        layout.addWidget(self._view, 1)
        self._generate()

    def _generate(self) -> None:
        fmt = self._format.currentData()
        try:
            content = self._facade.report(self._kind.currentData(), self._reference, fmt)
        except ApiError as exc:
            self._view.setPlainText("\n".join(exc.messages))
            return
        if fmt == "html":
            self._view.setHtml(content)
        else:
            self._view.setPlainText(content)


class CategoryTreeDialog(QDialog):
    """Mostra a árvore de categorias (Composite do servidor)."""

    def __init__(self, facade: ClientFacade, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Categorias")
        self.setMinimumSize(480, 420)
        tree = QTreeWidget()
        tree.setHeaderLabels(["Categoria / atividade", "Qtd.", "Tempo total"])
        tree.setColumnWidth(0, 250)
        try:
            data = facade.category_tree()
            tree.addTopLevelItem(self._build(data))
            tree.expandAll()
        except ApiError as exc:
            tree.addTopLevelItem(QTreeWidgetItem(["\n".join(exc.messages)]))
        layout = QVBoxLayout(self)
        layout.addWidget(tree)

    def _build(self, node: dict) -> QTreeWidgetItem:
        item = QTreeWidgetItem([node["name"], str(node["count"]), _fmt_minutes(node["total_minutes"])])
        for child in node.get("children", []):
            item.addChild(self._build(child))
        return item


class StatsDialog(QDialog):
    def __init__(self, facade: ClientFacade, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Estatísticas")
        self.setMinimumSize(460, 480)
        view = QTextBrowser()
        try:
            view.setPlainText(self._render(facade.stats(), facade.server_notifications()))
        except ApiError as exc:
            view.setPlainText("\n".join(exc.messages))
        layout = QVBoxLayout(self)
        layout.addWidget(view)

    @staticmethod
    def _render(stats: dict, notifications: list) -> str:
        def block(title, mapping, labels=None, minutes=None):
            lines = [title]
            for key, value in sorted(mapping.items()):
                label = (labels or {}).get(key, key)
                extra = f" ({_fmt_minutes(minutes[key])})" if minutes and key in minutes else ""
                lines.append(f"  {label}: {value}{extra}")
            return "\n".join(lines)

        parts = [
            f"Total de atividades: {stats['total']}",
            f"Tempo total planejado: {_fmt_minutes(stats['total_minutes'])}",
            f"Participantes em reuniões: {stats['meeting_attendees']}",
            "",
            block("Por tipo", stats["by_kind"], KIND_LABELS, stats["minutes_by_kind"]),
            "",
            block("Por prioridade", stats["by_priority"], PRIORITY_LABELS),
            "",
            block("Por status", stats["by_status"], STATUS_LABELS),
            "",
            block("Por categoria", stats["by_category"]),
            "",
            "Últimas notificações do servidor",
        ]
        if not notifications:
            parts.append("  (nenhuma nesta sessão do servidor)")
        for note in notifications[:8]:
            parts.append(f"  {note['at'][11:19]}  {note['message']}")
        return "\n".join(parts)
