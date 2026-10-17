"""Utilitários de teste."""
from __future__ import annotations

import json


class FlaskSession:
    """Faz o ``HttpCalendarApi`` conversar com o app Flask sem abrir rede.

    Imita o trecho de ``requests.Session`` usado pelo cliente, para testar o
    contrato cliente <-> servidor de ponta a ponta.
    """

    class _Response:
        def __init__(self, resp):
            self.status_code = resp.status_code
            self.text = resp.get_data(as_text=True)

        def json(self):
            return json.loads(self.text)

    def __init__(self, flask_client):
        self._client = flask_client

    def request(self, method, url, params=None, json=None, timeout=None):
        path = url.split("://", 1)[-1]
        path = path[path.index("/"):]
        resp = self._client.open(path, method=method, query_string=params, json=json)
        return self._Response(resp)
