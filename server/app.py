"""Aplicação Flask: rotas HTTP finas que delegam tudo ao ``CalendarFacade``.

Também usa o Decorator *de função* do Python (``api_endpoint``) para traduzir
exceções de domínio em respostas HTTP padronizadas.
"""
from __future__ import annotations

import functools

from flask import Flask, Response, current_app, jsonify, request

from .errors import InvalidTransition, NotFoundError, QuerySyntaxError, ValidationError
from .facade import CalendarFacade
from .repository import ActivityRepository

DEFAULT_PORT = 5055


def api_endpoint(func):
    """Decorator de função: converte exceções de domínio em JSON + status HTTP."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
        except ValidationError as exc:
            return jsonify({"error": str(exc), "errors": exc.errors}), 400
        except QuerySyntaxError as exc:
            return jsonify({"error": str(exc), "errors": [str(exc)]}), 400
        except NotFoundError as exc:
            return jsonify({"error": str(exc), "errors": [str(exc)]}), 404
        except InvalidTransition as exc:
            return jsonify({"error": str(exc), "errors": [str(exc)]}), 409
        except OSError:
            current_app.logger.exception("Falha ao gravar os dados")
            message = "Não foi possível gravar os dados no servidor. Nada foi alterado."
            return jsonify({"error": message, "errors": [message]}), 500
        except Exception:  # defeito inesperado: o cliente recebe JSON, nunca HTML
            current_app.logger.exception("Erro interno")
            message = "Erro interno do servidor"
            return jsonify({"error": message, "errors": [message]}), 500
        if isinstance(result, Response):
            return result
        if isinstance(result, tuple):
            body, status = result
            return jsonify(body), status
        return jsonify(result)

    return wrapper


def _body() -> dict:
    return request.get_json(silent=True) or {}


def create_app(data_file=None) -> Flask:
    app = Flask(__name__)
    app.json.ensure_ascii = False
    facade = CalendarFacade(ActivityRepository(data_file))
    app.config["FACADE"] = facade

    @app.get("/api/health")
    @api_endpoint
    def health():
        return {"status": "ok"}

    # ------------------------------------------------------------ atividades
    @app.get("/api/activities")
    @api_endpoint
    def list_activities():
        return facade.list_activities(
            sort=request.args.get("sort", "start"),
            status=request.args.get("status"),
            kind=request.args.get("kind"),
            category=request.args.get("category"),
        )

    @app.post("/api/activities")
    @api_endpoint
    def create_activity():
        return facade.create_activity(_body()), 201

    @app.get("/api/activities/<activity_id>")
    @api_endpoint
    def get_activity(activity_id):
        return facade.get_activity(activity_id)

    @app.put("/api/activities/<activity_id>")
    @api_endpoint
    def update_activity(activity_id):
        return facade.update_activity(activity_id, _body())

    @app.delete("/api/activities/<activity_id>")
    @api_endpoint
    def delete_activity(activity_id):
        return facade.delete_activity(activity_id)

    @app.post("/api/activities/<activity_id>/duplicate")
    @api_endpoint
    def duplicate_activity(activity_id):
        try:
            days = int(_body().get("days", 1))
        except (TypeError, ValueError):
            raise ValidationError("'days' deve ser um número inteiro") from None
        return facade.duplicate_activity(activity_id, days), 201

    @app.post("/api/activities/<activity_id>/transition")
    @api_endpoint
    def transition(activity_id):
        return facade.transition(activity_id, _body().get("action", ""))

    @app.post("/api/activities/<activity_id>/revert")
    @api_endpoint
    def revert(activity_id):
        return facade.revert(activity_id)

    @app.post("/api/activities/<activity_id>/restore")
    @api_endpoint
    def restore(activity_id):
        return facade.restore(activity_id), 201

    @app.get("/api/activities/<activity_id>/history")
    @api_endpoint
    def history(activity_id):
        return facade.history(activity_id)

    # ------------------------------------------------------------- consultas
    @app.get("/api/calendar")
    @api_endpoint
    def calendar_view():
        return facade.calendar(request.args.get("start"), request.args.get("end"))

    @app.get("/api/search")
    @api_endpoint
    def search():
        return facade.search(request.args.get("q", ""))

    @app.get("/api/stats")
    @api_endpoint
    def stats():
        return facade.stats()

    @app.get("/api/categories")
    @api_endpoint
    def categories():
        return facade.category_tree()

    @app.get("/api/reports/<kind>")
    @api_endpoint
    def report(kind):
        content, content_type = facade.report(
            kind, request.args.get("date"), request.args.get("format", "text")
        )
        return Response(content, mimetype=content_type)

    @app.get("/api/export/<fmt>")
    @api_endpoint
    def export(fmt):
        content, content_type, filename = facade.export(fmt)
        return Response(
            content,
            mimetype=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.get("/api/notifications")
    @api_endpoint
    def notifications():
        return facade.notifications()

    @app.get("/api/audit")
    @api_endpoint
    def audit():
        return facade.audit_log()

    return app
