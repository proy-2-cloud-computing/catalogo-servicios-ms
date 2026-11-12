"""Respuestas JSON, CORS y manejo uniforme de errores.

Todas las respuestas (incluidos los errores) llevan los headers CORS. Los
errores que genera API Gateway (401 del authorizer) se cubren con los
GatewayResponse del serverless.yml.
"""

import json
import logging
import os
from decimal import Decimal
from functools import wraps

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


class ApiError(Exception):
    """Error de negocio que se traduce a una respuesta HTTP."""

    def __init__(self, status, code, message, detalle=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.detalle = detalle


def _json_default(valor):
    if isinstance(valor, Decimal):
        if valor == valor.to_integral_value():
            return int(valor)
        return float(valor)
    if isinstance(valor, set):
        return sorted(valor)
    raise TypeError(f"Tipo no serializable: {type(valor)!r}")


def _headers():
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "GET,POST,PUT,OPTIONS",
    }


def json_response(status, payload):
    return {
        "statusCode": status,
        "headers": _headers(),
        "body": json.dumps(payload, default=_json_default, ensure_ascii=False),
    }


def ok(payload, status=200):
    return json_response(status, payload)


def creado(payload):
    return json_response(201, payload)


def error_response(status, code, message, detalle=None):
    cuerpo = {"error": {"code": code, "message": message}}
    if detalle is not None:
        cuerpo["error"]["detalle"] = detalle
    return json_response(status, cuerpo)


def api_handler(func):
    """Convierte ApiError y errores inesperados en respuestas JSON con CORS."""

    @wraps(func)
    def wrapper(event, context):
        try:
            return func(event, context)
        except ApiError as error:
            if error.status >= 500:
                logger.error("%s: %s", error.code, error.message)
            return error_response(
                error.status, error.code, error.message, error.detalle
            )
        except Exception:  # pragma: no cover - red de seguridad
            logger.exception("Error no controlado en %s", func.__module__)
            return error_response(
                500, "ERROR_INTERNO", "Error interno del servidor"
            )

    return wrapper
