"""PADRÃO ESTRUTURAL: Composite.

As categorias formam uma árvore (``Trabalho/Reuniões``). ``CategoryNode`` é o
composto e ``ActivityLeaf`` é a folha; ambos oferecem ``count()``,
``total_minutes()`` e ``to_dict()`` de forma uniforme.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class CategoryComponent(ABC):
    name: str

    @abstractmethod
    def count(self) -> int: ...

    @abstractmethod
    def total_minutes(self) -> int: ...

    @abstractmethod
    def to_dict(self) -> dict: ...


class ActivityLeaf(CategoryComponent):
    def __init__(self, activity):
        self._activity = activity
        self.name = activity.title

    def count(self) -> int:
        return 1

    def total_minutes(self) -> int:
        return self._activity.duration_minutes

    def to_dict(self) -> dict:
        return {
            "type": "activity",
            "name": self.name,
            "id": self._activity.id,
            "kind": self._activity.kind,
            "status": self._activity.status,
            "count": 1,
            "total_minutes": self.total_minutes(),
        }


class CategoryNode(CategoryComponent):
    def __init__(self, name: str):
        self.name = name
        self._categories: dict[str, CategoryNode] = {}
        self._leaves: list[ActivityLeaf] = []

    def add_activity(self, path: list[str], activity) -> None:
        if not path:
            self._leaves.append(ActivityLeaf(activity))
            return
        head, *rest = path
        child = self._categories.setdefault(head, CategoryNode(head))
        child.add_activity(rest, activity)

    def children(self) -> list[CategoryComponent]:
        cats = sorted(self._categories.values(), key=lambda c: c.name.casefold())
        leaves = sorted(self._leaves, key=lambda l: l.name.casefold())
        return [*cats, *leaves]

    def count(self) -> int:
        return sum(child.count() for child in self.children())

    def total_minutes(self) -> int:
        return sum(child.total_minutes() for child in self.children())

    def to_dict(self) -> dict:
        return {
            "type": "category",
            "name": self.name,
            "count": self.count(),
            "total_minutes": self.total_minutes(),
            "children": [child.to_dict() for child in self.children()],
        }


def build_category_tree(activities) -> CategoryNode:
    root = CategoryNode("Todas as categorias")
    for activity in activities:
        path = [p for p in activity.category.split("/") if p]
        root.add_activity(path, activity)
    return root
