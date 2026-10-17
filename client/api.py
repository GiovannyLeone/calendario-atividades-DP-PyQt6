"""Acesso à API do servidor.

``CalendarApi`` é a interface (Subject do Proxy). ``HttpCalendarApi`` é a
implementação real (requests); ``CachingApiProxy`` (proxy.py) a envolve.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod

import requests

DEFAULT_URL = os.environ.get("CALENDAR_API_URL", "http://127.0.0.1:5055")


class ApiError(Exception):
    def __init__(self, messages, status: int | None = None):
        if isinstance(messages, str):
            messages = [messages]
        self.messages = list(messages)
        self.status = status
        super().__init__("; ".join(self.messages))


class CalendarApi(ABC):
    def invalidate(self) -> None:
        """Descarta respostas guardadas (só o proxy de cache faz algo aqui)."""

    @abstractmethod
    def health(self) -> dict: ...

    @abstractmethod
    def list_activities(self, sort: str = "start") -> list: ...

    @abstractmethod
    def calendar(self, start: str, end: str) -> list: ...

    @abstractmethod
    def create(self, data: dict) -> dict: ...

    @abstractmethod
    def update(self, activity_id: str, data: dict) -> dict: ...

    @abstractmethod
    def delete(self, activity_id: str) -> dict: ...

    @abstractmethod
    def duplicate(self, activity_id: str, days: int = 1) -> dict: ...

    @abstractmethod
    def transition(self, activity_id: str, action: str) -> dict: ...

    @abstractmethod
    def revert(self, activity_id: str) -> dict: ...

    @abstractmethod
    def restore(self, activity_id: str) -> dict: ...

    @abstractmethod
    def search(self, query: str) -> list: ...

    @abstractmethod
    def stats(self) -> dict: ...

    @abstractmethod
    def categories(self) -> dict: ...

    @abstractmethod
    def report(self, kind: str, reference: str, fmt: str = "text") -> str: ...

    @abstractmethod
    def export(self, fmt: str) -> str: ...

    @abstractmethod
    def notifications(self) -> list: ...


class HttpCalendarApi(CalendarApi):
    def __init__(self, base_url: str | None = None, timeout: float = 5.0, session=None):
        self._base = (base_url or DEFAULT_URL).rstrip("/")
        self._timeout = timeout
        self._session = session or requests.Session()

    def _call(self, method: str, path: str, *, params=None, body=None, raw: bool = False):
        try:
            response = self._session.request(
                method, self._base + path, params=params, json=body, timeout=self._timeout
            )
        except requests.RequestException:
            raise ApiError(
                f"Servidor indisponível em {self._base}. Inicie-o com: python run_server.py"
            ) from None
        if response.status_code >= 400:
            try:
                payload = response.json()
                messages = payload.get("errors") or [payload.get("error", "Erro desconhecido")]
            except ValueError:
                messages = [f"Erro HTTP {response.status_code}"]
            raise ApiError(messages, response.status_code)
        return response.text if raw else response.json()

    def health(self):
        return self._call("GET", "/api/health")

    def list_activities(self, sort="start"):
        return self._call("GET", "/api/activities", params={"sort": sort})

    def calendar(self, start, end):
        return self._call("GET", "/api/calendar", params={"start": start, "end": end})

    def create(self, data):
        return self._call("POST", "/api/activities", body=data)

    def update(self, activity_id, data):
        return self._call("PUT", f"/api/activities/{activity_id}", body=data)

    def delete(self, activity_id):
        return self._call("DELETE", f"/api/activities/{activity_id}")

    def duplicate(self, activity_id, days=1):
        return self._call("POST", f"/api/activities/{activity_id}/duplicate", body={"days": days})

    def transition(self, activity_id, action):
        return self._call("POST", f"/api/activities/{activity_id}/transition", body={"action": action})

    def revert(self, activity_id):
        return self._call("POST", f"/api/activities/{activity_id}/revert")

    def restore(self, activity_id):
        return self._call("POST", f"/api/activities/{activity_id}/restore")

    def search(self, query):
        return self._call("GET", "/api/search", params={"q": query})

    def stats(self):
        return self._call("GET", "/api/stats")

    def categories(self):
        return self._call("GET", "/api/categories")

    def report(self, kind, reference, fmt="text"):
        return self._call(
            "GET", f"/api/reports/{kind}", params={"date": reference, "format": fmt}, raw=True
        )

    def export(self, fmt):
        return self._call("GET", f"/api/export/{fmt}", raw=True)

    def notifications(self):
        return self._call("GET", "/api/notifications")
