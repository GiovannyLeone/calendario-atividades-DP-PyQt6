"""PADRÃO ESTRUTURAL: Flyweight.

Um mês exibe dezenas de atividades, mas só existem poucas combinações de
(tipo, status). ``ItemStyleFactory`` mantém um *pool* de objetos ``ItemStyle``
imutáveis (estado intrínseco: cores e fonte) compartilhados por todas as
células; o texto e a posição (estado extrínseco) ficam com quem usa.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ItemStyle:
    background: str
    foreground: str
    strike: bool = False
    italic: bool = False
    bold: bool = False

    def css(self) -> str:
        decoration = "line-through" if self.strike else "none"
        style = "italic" if self.italic else "normal"
        weight = "bold" if self.bold else "normal"
        return (
            f"background-color: {self.background}; color: {self.foreground};"
            f" border-radius: 3px; padding: 1px 4px; font-size: 11px;"
            f" text-decoration: {decoration}; font-style: {style}; font-weight: {weight};"
        )


class ItemStyleFactory:
    KIND_COLORS = {
        "task": ("#d6e8ff", "#12315a"),
        "meeting": ("#ffe3c2", "#5a3205"),
        "reminder": ("#ffd6e0", "#5a1226"),
        "event": ("#d9f2d0", "#1f4a12"),
    }

    def __init__(self):
        self._pool: dict[tuple[str, str], ItemStyle] = {}

    def get(self, kind: str, status: str) -> ItemStyle:
        key = (kind, status)
        style = self._pool.get(key)
        if style is None:
            style = self._create(kind, status)
            self._pool[key] = style
        return style

    def _create(self, kind: str, status: str) -> ItemStyle:
        background, foreground = self.KIND_COLORS.get(kind, ("#e6e6e6", "#222222"))
        if status == "cancelled":
            return ItemStyle("#e3e3e3", "#6b6b6b", strike=True, italic=True)
        if status == "done":
            return ItemStyle(background, foreground, strike=True)
        if status == "in_progress":
            return ItemStyle(background, foreground, bold=True)
        return ItemStyle(background, foreground)

    def __len__(self) -> int:
        return len(self._pool)
