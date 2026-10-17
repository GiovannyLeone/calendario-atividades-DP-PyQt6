"""PADRÃO ESTRUTURAL: Proxy (proxy de cache).

``CachingApiProxy`` implementa a mesma interface ``CalendarApi`` e guarda em
memória as respostas das consultas, evitando requisições repetidas (por
exemplo, ao navegar entre meses já carregados). Qualquer escrita invalida o
cache, garantindo dados consistentes.
"""
from __future__ import annotations

import copy
import time

from .api import CalendarApi


class CachingApiProxy(CalendarApi):
    def __init__(self, real: CalendarApi, ttl: float = 30.0, clock=time.monotonic):
        self._real = real
        self._ttl = ttl
        self._clock = clock
        self._cache: dict = {}
        self.hits = 0
        self.misses = 0

    # -- infraestrutura do cache -------------------------------------------
    def invalidate(self) -> None:
        self._cache.clear()

    def _cached(self, key, loader):
        now = self._clock()
        entry = self._cache.get(key)
        if entry is not None and now - entry[0] <= self._ttl:
            self.hits += 1
            return copy.deepcopy(entry[1])
        self.misses += 1
        value = loader()
        self._cache[key] = (now, copy.deepcopy(value))
        return value

    def _write(self, call, *args, **kwargs):
        try:
            return call(*args, **kwargs)
        finally:
            self.invalidate()  # mesmo em falha, o estado remoto é incerto

    # -- leituras (com cache) -------------------------------------------------
    def health(self):
        return self._real.health()

    def list_activities(self, sort="start"):
        return self._cached(("list", sort), lambda: self._real.list_activities(sort))

    def calendar(self, start, end):
        return self._cached(("calendar", start, end), lambda: self._real.calendar(start, end))

    def search(self, query):
        return self._cached(("search", query), lambda: self._real.search(query))

    def stats(self):
        return self._cached(("stats",), self._real.stats)

    def categories(self):
        return self._cached(("categories",), self._real.categories)

    def report(self, kind, reference, fmt="text"):
        return self._cached(("report", kind, reference, fmt), lambda: self._real.report(kind, reference, fmt))

    def export(self, fmt):
        return self._cached(("export", fmt), lambda: self._real.export(fmt))

    def notifications(self):
        return self._real.notifications()  # sempre fresco

    # -- escritas (invalidam o cache) -------------------------------------------
    def create(self, data):
        return self._write(self._real.create, data)

    def update(self, activity_id, data):
        return self._write(self._real.update, activity_id, data)

    def delete(self, activity_id):
        return self._write(self._real.delete, activity_id)

    def duplicate(self, activity_id, days=1):
        return self._write(self._real.duplicate, activity_id, days)

    def transition(self, activity_id, action):
        return self._write(self._real.transition, activity_id, action)

    def revert(self, activity_id):
        return self._write(self._real.revert, activity_id)

    def restore(self, activity_id):
        return self._write(self._real.restore, activity_id)
