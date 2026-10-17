"""PADRÃO ESTRUTURAL: Facade.

``CalendarFacade`` é a única porta de entrada para as camadas Flask: ela
orquestra fábrica, builder, corrente de validação, repositório (via proxy),
memento, estados, iteradores, interpretador, visitantes, relatórios e
exportadores, escondendo essa complexidade das rotas HTTP.
"""
from __future__ import annotations

import threading
from datetime import date

from .bridge import make_report
from .composite import build_category_tree
from .decorators import build_label
from .errors import NotFoundError, ValidationError
from .exporters import get_exporter
from .factory import creator_for
from .interpreter import parse_query
from .iterators import OccurrenceIterator
from .memento import HistoryCaretaker
from .observer import NotificationCenter
from .repository import ActivityRepository, AuditedRepositoryProxy
from .strategy import SORT_STRATEGIES, ActivitySorter
from .timeutil import DATETIME_FORMAT, parse_date
from .validation import validate_activity
from .visitor import DetailsVisitor, StatisticsVisitor


class CalendarFacade:
    def __init__(self, repository: ActivityRepository | None = None):
        self._repository = repository or ActivityRepository()
        self._store = AuditedRepositoryProxy(self._repository)
        self._history = HistoryCaretaker()
        self._notifications = NotificationCenter()
        self._repository.subscribe(self._notifications)
        self._lock = threading.RLock()

    # ------------------------------------------------------------ utilitários
    @staticmethod
    def _sanitize(data) -> dict:
        if not isinstance(data, dict):
            raise ValidationError("Corpo da requisição inválido: esperado um objeto JSON")
        cleaned = dict(data)
        cleaned.pop("status", None)  # o status só muda pelas transições (State)
        return cleaned

    def _validate(self, activity) -> None:
        errors = validate_activity(activity, self._store)
        if errors:
            raise ValidationError(errors)

    # ------------------------------------------------------------------ CRUD
    def list_activities(self, sort="start", status=None, kind=None, category=None) -> list[dict]:
        if sort not in SORT_STRATEGIES:
            raise ValidationError(f"Ordenação desconhecida: {sort!r}. Use: {', '.join(SORT_STRATEGIES)}")
        items = self._store.all()
        if status:
            items = [a for a in items if a.status == status]
        if kind:
            items = [a for a in items if a.kind == kind]
        if category:
            wanted = category.casefold()
            items = [
                a for a in items
                if a.category.casefold() == wanted or a.category.casefold().startswith(wanted + "/")
            ]
        return [a.to_dict() for a in ActivitySorter(SORT_STRATEGIES[sort]).sort(items)]

    def get_activity(self, activity_id: str) -> dict:
        return self._store.get(activity_id).to_dict()

    def create_activity(self, data) -> dict:
        with self._lock:
            data = self._sanitize(data)
            activity = creator_for(data.get("kind") or "task").create(data)
            self._validate(activity)
            self._store.add(activity)
            return activity.to_dict()

    def update_activity(self, activity_id: str, data) -> dict:
        with self._lock:
            current = self._store.get(activity_id)
            data = self._sanitize(data)
            if data.get("kind") and data["kind"] != current.kind:
                raise ValidationError("O tipo da atividade não pode ser alterado")
            merged = {
                **current.to_dict(),
                **data,
                "id": current.id,
                "kind": current.kind,
                "status": current.status,
            }
            updated = creator_for(current.kind).create(merged)
            self._validate(updated)
            memento = current.create_memento("update")
            self._store.update(updated)
            self._history.save(current.id, memento)  # só registra se a gravação deu certo
            return updated.to_dict()

    def delete_activity(self, activity_id: str) -> dict:
        with self._lock:
            current = self._store.get(activity_id)
            memento = current.create_memento("delete")
            self._store.remove(activity_id)
            self._history.save(current.id, memento)
            return {"deleted": activity_id}

    def duplicate_activity(self, activity_id: str, days: int = 1) -> dict:
        with self._lock:
            twin = self._store.get(activity_id).clone(days=days)  # Prototype
            self._validate(twin)
            self._store.add(twin)
            return twin.to_dict()

    # ------------------------------------------------------- State / Memento
    def transition(self, activity_id: str, action: str) -> dict:
        with self._lock:
            current = self._store.get(activity_id)
            memento = current.create_memento("update")
            current.transition(action)  # pode lançar InvalidTransition
            try:
                self._store.update(current)
            except Exception:
                current.restore_from(memento)  # desfaz a mudança em memória
                raise
            self._history.save(current.id, memento)
            return current.to_dict()

    def revert(self, activity_id: str) -> dict:
        with self._lock:
            current = self._store.get(activity_id)
            memento = self._history.pop_last(activity_id, "update")
            if memento is None:
                raise NotFoundError("Não há alteração anterior para desfazer nesta atividade")
            before = current.create_memento("update")
            current.restore_from(memento)
            try:
                self._store.update(current)
            except Exception:
                current.restore_from(before)
                self._history.save(activity_id, memento)
                raise
            return current.to_dict()

    def restore(self, activity_id: str) -> dict:
        with self._lock:
            memento = self._history.pop_last(activity_id, "delete")
            if memento is None:
                raise NotFoundError("Não há atividade excluída com este id para restaurar")
            activity = creator_for(memento.snapshot["kind"]).create(memento.snapshot)
            try:
                self._store.add(activity)
            except Exception:
                self._history.save(activity_id, memento)
                raise
            return activity.to_dict()

    def history(self, activity_id: str) -> list[dict]:
        return self._history.entries(activity_id)

    # ----------------------------------------------------------- consultas
    def calendar(self, start, end) -> list[dict]:
        """Ocorrências (já expandidas pelas recorrências) em [start, end]."""
        window_start = parse_date(start, "Data inicial")
        window_end = parse_date(end, "Data final")
        if window_end < window_start:
            raise ValidationError("A data final não pode ser anterior à inicial")
        if (window_end - window_start).days > 366:
            raise ValidationError("O intervalo máximo é de 366 dias")
        details = DetailsVisitor()
        occurrences = []
        for activity in self._store.all():
            for occ_start, occ_end in OccurrenceIterator(activity, window_start, window_end):
                occurrences.append(
                    {
                        **activity.to_dict(),
                        "occurrence_start": occ_start.strftime(DATETIME_FORMAT),
                        "occurrence_end": occ_end.strftime(DATETIME_FORMAT),
                        "date": occ_start.date().isoformat(),
                        "label": build_label(activity),
                        "kind_label": activity.kind_label,
                        "details": activity.accept(details),
                    }
                )
        occurrences.sort(key=lambda o: (o["occurrence_start"], o["title"].casefold()))
        return occurrences

    def search(self, query: str) -> list[dict]:
        expression = parse_query(query)
        found = [a for a in self._store.all() if expression.interpret(a)]
        return [a.to_dict() for a in ActivitySorter(SORT_STRATEGIES["start"]).sort(found)]

    def stats(self) -> dict:
        visitor = StatisticsVisitor()
        for activity in self._store.all():
            activity.accept(visitor)
        return visitor.result()

    def category_tree(self) -> dict:
        return build_category_tree(self._store.all()).to_dict()

    def report(self, kind: str, reference=None, fmt: str = "text") -> tuple[str, str]:
        ref = parse_date(reference, "Data de referência") if reference else date.today()
        report = make_report(kind, fmt, self.calendar)
        return report.render(ref), report.content_type

    def export(self, fmt: str) -> tuple[str, str, str]:
        exporter = get_exporter(fmt)
        ordered = ActivitySorter(SORT_STRATEGIES["start"]).sort(self._store.all())
        return exporter.export(ordered), exporter.content_type, f"calendario.{exporter.extension}"

    # ---------------------------------------------------- Observer / Proxy
    def notifications(self) -> list[dict]:
        return self._notifications.messages()

    def audit_log(self) -> list[dict]:
        return self._store.audit_entries()
