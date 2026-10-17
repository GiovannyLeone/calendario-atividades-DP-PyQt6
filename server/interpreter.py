"""PADRÃO COMPORTAMENTAL: Interpreter.

Linguagem de consulta para buscar atividades, por exemplo:

    priority:high AND (category:Trabalho OR status:done)
    reunião NOT kind:task
    title:"revisar pull" date:2026-10-08

Gramática (precedência: NOT > AND > OR; AND implícito entre termos):

    expr   := andexp ( "OR" andexp )*
    andexp := factor ( ["AND"] factor )*
    factor := "NOT" factor | "(" expr ")" | termo
    termo  := PALAVRA | CAMPO ":" VALOR        (VALOR pode estar entre aspas)

Cada regra vira uma classe ``Expression`` (árvore sintática abstrata).
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod

from .errors import QuerySyntaxError

FIELDS = ("title", "description", "category", "priority", "status", "kind", "date")

_TOKEN = re.compile(r'\s*([A-Za-zÀ-ÿ_]+:"[^"]*"|"[^"]*"|\(|\)|[^\s()]+)')


class Expression(ABC):
    @abstractmethod
    def interpret(self, activity) -> bool: ...


class TermExpression(Expression):
    def __init__(self, field: str | None, value: str):
        self.field = field
        self.value = value.casefold()

    def interpret(self, activity) -> bool:
        v = self.value
        if self.field is None:
            haystack = f"{activity.title} {activity.description} {activity.category}".casefold()
            return v in haystack
        if self.field in ("title", "description"):
            return v in getattr(activity, self.field).casefold()
        if self.field == "category":
            cat = activity.category.casefold()
            return cat == v or cat.startswith(v + "/")
        if self.field == "date":
            return activity.start.date().isoformat() == v
        return str(getattr(activity, self.field)).casefold() == v


class AndExpression(Expression):
    def __init__(self, left: Expression, right: Expression):
        self.left, self.right = left, right

    def interpret(self, activity) -> bool:
        return self.left.interpret(activity) and self.right.interpret(activity)


class OrExpression(Expression):
    def __init__(self, left: Expression, right: Expression):
        self.left, self.right = left, right

    def interpret(self, activity) -> bool:
        return self.left.interpret(activity) or self.right.interpret(activity)


class NotExpression(Expression):
    def __init__(self, inner: Expression):
        self.inner = inner

    def interpret(self, activity) -> bool:
        return not self.inner.interpret(activity)


class QueryParser:
    """Analisador descendente recursivo que constrói a árvore de expressões."""

    def __init__(self, text: str):
        self._tokens = _TOKEN.findall(text or "")
        self._pos = 0

    def parse(self) -> Expression:
        if not self._tokens:
            raise QuerySyntaxError("A consulta está vazia")
        node = self._expr()
        if self._peek() is not None:
            raise QuerySyntaxError(f"Trecho inesperado na consulta: {self._peek()!r}")
        return node

    def _peek(self) -> str | None:
        return self._tokens[self._pos] if self._pos < len(self._tokens) else None

    def _take(self) -> str:
        token = self._tokens[self._pos]
        self._pos += 1
        return token

    def _is(self, keyword: str) -> bool:
        token = self._peek()
        return token is not None and token.upper() == keyword

    def _expr(self) -> Expression:
        node = self._and()
        while self._is("OR"):
            self._take()
            node = OrExpression(node, self._and())
        return node

    def _and(self) -> Expression:
        node = self._factor()
        while True:
            token = self._peek()
            if token is None or token == ")" or self._is("OR"):
                return node
            if self._is("AND"):
                self._take()
            node = AndExpression(node, self._factor())

    def _factor(self) -> Expression:
        token = self._peek()
        if token is None:
            raise QuerySyntaxError("A consulta terminou inesperadamente")
        if self._is("NOT"):
            self._take()
            return NotExpression(self._factor())
        if token == "(":
            self._take()
            node = self._expr()
            if self._peek() != ")":
                raise QuerySyntaxError("Parêntese não fechado na consulta")
            self._take()
            return node
        if token == ")" or self._is("AND") or self._is("OR"):
            raise QuerySyntaxError(f"Termo esperado, mas encontrado {token!r}")
        return self._term(self._take())

    @staticmethod
    def _term(token: str) -> Expression:
        if ":" in token and not token.startswith('"'):
            field, value = token.split(":", 1)
            field = field.lower()
            if field not in FIELDS:
                raise QuerySyntaxError(
                    f"Campo desconhecido: {field!r}. Use: {', '.join(FIELDS)}"
                )
            return TermExpression(field, value.strip('"'))
        return TermExpression(None, token.strip('"'))


def parse_query(text: str) -> Expression:
    return QueryParser(text).parse()
