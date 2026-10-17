"""PADRÃO COMPORTAMENTAL: Strategy.

Algoritmos de ordenação intercambiáveis. ``ActivitySorter`` é o contexto e
recebe a estratégia escolhida (ex.: parâmetro ``?sort=`` da API).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


class SortStrategy(ABC):
    @abstractmethod
    def key(self, activity): ...

    def sort(self, activities):
        return sorted(activities, key=self.key)


class ByStartSort(SortStrategy):
    def key(self, activity):
        return (activity.start, activity.title.casefold())


class ByPrioritySort(SortStrategy):
    def key(self, activity):
        return (_PRIORITY_RANK.get(activity.priority, 9), activity.start)


class ByTitleSort(SortStrategy):
    def key(self, activity):
        return (activity.title.casefold(), activity.start)


class ByCategorySort(SortStrategy):
    def key(self, activity):
        return (activity.category.casefold(), activity.start)


SORT_STRATEGIES: dict[str, SortStrategy] = {
    "start": ByStartSort(),
    "priority": ByPrioritySort(),
    "title": ByTitleSort(),
    "category": ByCategorySort(),
}


class ActivitySorter:
    """Contexto da Strategy."""

    def __init__(self, strategy: SortStrategy):
        self._strategy = strategy

    def set_strategy(self, strategy: SortStrategy) -> None:
        self._strategy = strategy

    def sort(self, activities):
        return self._strategy.sort(activities)
