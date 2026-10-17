"""Persistência em arquivo JSON (sem banco de dados).

Padrões neste módulo:
  * Singleton -> ``ActivityRepository`` (instância única, via ``SingletonMeta``)
  * Observer  -> o repositório é o sujeito que notifica mudanças
  * Proxy     -> ``AuditedRepositoryProxy`` (proxy de proteção/auditoria)
"""
from __future__ import annotations

import json
import os
import shutil
import threading
from abc import ABC, abstractmethod
from collections import deque
from datetime import datetime
from pathlib import Path

from .activity import Activity
from .errors import NotFoundError, ValidationError
from .factory import create_activity
from .observer import ChangeEvent, Observable
from .singleton import SingletonMeta

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_FILE = ROOT / "data" / "activities.json"
DEFAULT_SEED_FILE = ROOT / "data" / "activities_seed.json"


class ActivityStore(ABC):
    """Interface comum ao repositório real e ao proxy (Subject do Proxy)."""

    @abstractmethod
    def all(self) -> list[Activity]: ...

    @abstractmethod
    def get(self, activity_id: str) -> Activity: ...

    @abstractmethod
    def add(self, activity: Activity) -> None: ...

    @abstractmethod
    def update(self, activity: Activity) -> None: ...

    @abstractmethod
    def remove(self, activity_id: str) -> Activity: ...


class ActivityRepository(ActivityStore, Observable, metaclass=SingletonMeta):
    def __init__(self, path=None, seed_path=None):
        Observable.__init__(self)
        if path is None:
            path = DEFAULT_DATA_FILE
            seed_path = seed_path or DEFAULT_SEED_FILE
        self._path = Path(path)
        self._seed = Path(seed_path) if seed_path else None
        self._items: dict[str, Activity] = {}
        self._lock = threading.RLock()
        self._load()

    # -- carga/gravação ---------------------------------------------------
    def _load(self) -> None:
        if not self._path.exists():
            if self._seed and self._seed.exists():
                self._path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(self._seed, self._path)
            else:
                return
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        for item in raw.get("activities", []):
            activity = create_activity(item)
            self._items[activity.id] = activity

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "saved_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "activities": [a.to_dict() for a in self._items.values()],
        }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self._path)

    # -- ActivityStore ----------------------------------------------------
    def all(self) -> list[Activity]:
        with self._lock:
            return list(self._items.values())

    def get(self, activity_id: str) -> Activity:
        with self._lock:
            try:
                return self._items[activity_id]
            except KeyError:
                raise NotFoundError(f"Atividade '{activity_id}' não encontrada") from None

    def add(self, activity: Activity) -> None:
        with self._lock:
            if activity.id in self._items:
                raise ValidationError(f"Já existe uma atividade com o id '{activity.id}'")
            self._items[activity.id] = activity
            try:
                self._save()
            except Exception:
                del self._items[activity.id]  # sem estado parcial em memória
                raise
        self.notify(ChangeEvent.now("created", activity.id, activity.title))

    def update(self, activity: Activity) -> None:
        with self._lock:
            if activity.id not in self._items:
                raise NotFoundError(f"Atividade '{activity.id}' não encontrada")
            previous = self._items[activity.id]
            self._items[activity.id] = activity
            try:
                self._save()
            except Exception:
                self._items[activity.id] = previous
                raise
        self.notify(ChangeEvent.now("updated", activity.id, activity.title))

    def remove(self, activity_id: str) -> Activity:
        with self._lock:
            activity = self.get(activity_id)
            del self._items[activity_id]
            try:
                self._save()
            except Exception:
                self._items[activity_id] = activity
                raise
        self.notify(ChangeEvent.now("deleted", activity.id, activity.title))
        return activity


class AuditedRepositoryProxy(ActivityStore):
    """Proxy: mesma interface do repositório, registrando cada operação."""

    def __init__(self, real: ActivityStore, limit: int = 200):
        self._real = real
        self._log: deque = deque(maxlen=limit)

    def _record(self, operation: str, activity_id: str | None, call):
        entry = {
            "at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "operation": operation,
            "activity_id": activity_id,
        }
        try:
            result = call()
        except Exception as exc:  # registra a falha e propaga
            entry["outcome"] = f"erro: {exc}"
            self._log.appendleft(entry)
            raise
        entry["outcome"] = "ok"
        self._log.appendleft(entry)
        return result

    def all(self) -> list[Activity]:
        return self._real.all()

    def get(self, activity_id: str) -> Activity:
        return self._record("get", activity_id, lambda: self._real.get(activity_id))

    def add(self, activity: Activity) -> None:
        self._record("add", activity.id, lambda: self._real.add(activity))

    def update(self, activity: Activity) -> None:
        self._record("update", activity.id, lambda: self._real.update(activity))

    def remove(self, activity_id: str) -> Activity:
        return self._record("remove", activity_id, lambda: self._real.remove(activity_id))

    def audit_entries(self) -> list[dict]:
        return list(self._log)
