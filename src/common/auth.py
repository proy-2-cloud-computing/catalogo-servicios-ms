"""Identidad y autorizacion a partir de los claims del ID token de Cognito.

Regla de oro: el tenant_id SIEMPRE sale del token (custom:tenant_id), nunca
del body, de la ruta ni de los query params.
"""

from .responses import ApiError


def contexto(event):
    """Extrae tenant, usuario y grupos de los claims del authorizer."""
    request_context = event.get("requestContext") or {}
    authorizer = request_context.get("authorizer") or {}
    claims = authorizer.get("claims") or {}

    tenant_id = claims.get("custom:tenant_id")
    usuario_id = claims.get("sub")

    if not tenant_id or not usuario_id:
        raise ApiError(401, "NO_AUTORIZADO", "Token invalido o sin tenant_id")

    return {
        "tenant_id": str(tenant_id),
        "usuario_id": str(usuario_id),
        "email": claims.get("email"),
        "grupos": _normalizar_grupos(claims.get("cognito:groups")),
    }


def _normalizar_grupos(valor):
    """API Gateway puede entregar cognito:groups como lista o string.

    Formatos vistos: ["admin"], "admin", "agente,admin" y "[agente admin]".
    """
    if not valor:
        return set()
    if isinstance(valor, str):
        limpio = valor.strip()
        if limpio.startswith("[") and limpio.endswith("]"):
            limpio = limpio[1:-1]
        partes = limpio.replace(",", " ").split()
        return {parte.strip().strip('"').strip("'") for parte in partes if parte.strip()}
    return {str(grupo) for grupo in valor}


def es_admin(ctx):
    return "admin" in ctx["grupos"]


def requiere_admin(ctx):
    if not es_admin(ctx):
        raise ApiError(
            403,
            "SIN_PERMISO",
            "Solo el rol admin puede gestionar el catalogo",
        )
