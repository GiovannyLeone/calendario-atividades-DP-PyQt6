"""Ponto de entrada do cliente PyQt6."""
from __future__ import annotations

import sys

from .api import HttpCalendarApi
from .facade import ClientFacade
from .model import CalendarModel
from .proxy import CachingApiProxy


def build_facade(base_url: str | None = None) -> ClientFacade:
    """Monta API real -> proxy de cache -> modelo observável -> fachada."""
    api = CachingApiProxy(HttpCalendarApi(base_url))
    model = CalendarModel(api)
    return ClientFacade(api, model)


def main(argv=None) -> int:
    from PyQt6.QtWidgets import QApplication

    from .ui.main_window import MainWindow

    app = QApplication(argv if argv is not None else sys.argv)
    facade = build_facade()
    window = MainWindow(facade)
    window.show()
    facade.model.go_today()  # carrega o mês atual
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
