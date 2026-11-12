"""Helpers para construir eventos de API Gateway (REST + authorizer Cognito)."""

import json


def evento(body=None, servicio_id=None, query=None, tenant="empresa-alfa",
           sub="u-admin", grupos=("admin",)):
    claims = {"sub": sub}
    if tenant is not None:
        claims["custom:tenant_id"] = tenant
    if grupos is not None:
        claims["cognito:groups"] = list(grupos)
    return {
        "body": None if body is None else json.dumps(body),
        "pathParameters": None if servicio_id is None else {"id": servicio_id},
        "queryStringParameters": query,
        "headers": {"Authorization": "id-token"},
        "requestContext": {"authorizer": {"claims": claims}},
    }


def cuerpo(respuesta):
    return json.loads(respuesta["body"])
