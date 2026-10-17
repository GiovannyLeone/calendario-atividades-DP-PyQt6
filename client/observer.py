"""PADRÃO COMPORTAMENTAL: Observer (lado do cliente).

``CalendarModel`` é o sujeito; as views (mês, painel do dia, janela principal)
são observadores e se redesenham quando o modelo muda.

``Observer`` é uma classe simples (não ABC) para poder ser combinada com
widgets Qt por herança múltipla; o método se chama ``on_change`` para não
colidir com ``QWidget.update``.
"""
from __future__ import annotations


class Observer:
    def on_change(self, subject, change: str) -> None:
        raise NotImplementedError


class Subject:
    def __init__(self):
        self._observers: list[Observer] = []

    def attach(self, observer: Observer) -> None:
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer: Observer) -> None:
        if observer in self._observers:
            self._observers.remove(observer)

    def notify(self, change: str = "refresh") -> None:
        for observer in list(self._observers):
            observer.on_change(self, change)
