"""Exceções de domínio do servidor."""
from __future__ import annotations


class DomainError(Exception):
    """Erro base para regras de negócio."""


class ValidationError(DomainError):
    """Dados inválidos; pode carregar várias mensagens."""

    def __init__(self, errors):
        if isinstance(errors, str):
            errors = [errors]
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


class NotFoundError(DomainError):
    """Recurso inexistente."""


class InvalidTransition(DomainError):
    """Transição de estado não permitida."""


class QuerySyntaxError(DomainError):
    """Consulta de busca com sintaxe inválida."""
