"""Inicia apenas o servidor Flask (http://127.0.0.1:5055)."""
from server.app import DEFAULT_PORT, create_app

if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=DEFAULT_PORT, debug=False)
