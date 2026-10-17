"""Atalho: sobe o servidor Flask em segundo plano e abre o cliente PyQt6."""
import sys
import threading
import time

import requests

from server.app import DEFAULT_PORT, create_app

URL = f"http://127.0.0.1:{DEFAULT_PORT}"


def _serve() -> None:
    create_app().run(host="127.0.0.1", port=DEFAULT_PORT, debug=False, use_reloader=False)


def _wait_for_server(timeout: float = 8.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if requests.get(f"{URL}/api/health", timeout=0.5).status_code == 200:
                return True
        except requests.RequestException:
            time.sleep(0.2)
    return False


if __name__ == "__main__":
    threading.Thread(target=_serve, daemon=True).start()
    if not _wait_for_server():
        sys.exit("Não foi possível iniciar o servidor Flask.")
    from client.main import main

    sys.exit(main())
