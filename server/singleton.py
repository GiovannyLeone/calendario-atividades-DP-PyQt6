"""PADRÃO CRIACIONAL: Singleton.

``SingletonMeta`` garante uma única instância por classe (thread-safe).
É usado por ``ActivityRepository``: toda a aplicação compartilha o mesmo
repositório de atividades.
"""
from __future__ import annotations

import threading
from abc import ABCMeta


class SingletonMeta(ABCMeta):
    _instances: dict = {}
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        with SingletonMeta._lock:
            if cls not in SingletonMeta._instances:
                SingletonMeta._instances[cls] = super().__call__(*args, **kwargs)
        return SingletonMeta._instances[cls]

    def reset(cls) -> None:
        """Descarta a instância atual (útil em testes)."""
        with SingletonMeta._lock:
            SingletonMeta._instances.pop(cls, None)
