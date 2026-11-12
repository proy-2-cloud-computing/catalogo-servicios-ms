"""GET /catalogo: lista servicios del tenant, paginado.

Query params:
  limit      1..100 (25 por defecto)
  next       token opaco devuelto por la pagina anterior
  estado     activo (por defecto) | inactivo | todos  -> inactivo/todos solo admin
  categoria  acceso | hardware | software | soporte | otro (opcional)
"""

from src.common import db
from src.common.auth import contexto, requiere_admin
from src.common.responses import api_handler, ok
from src.common.validation import leer_categoria, leer_estado_listado, leer_limit


@api_handler
def handler(event, context):
    ctx = contexto(event)
    query = event.get("queryStringParameters") or {}

    estado = leer_estado_listado(query)
    if estado != "activo":
        requiere_admin(ctx)

    items, siguiente = db.listar_servicios(
        ctx["tenant_id"],
        estado=estado,
        limit=leer_limit(query),
        next_token=query.get("next"),
        categoria=leer_categoria(query),
    )
    servicios = [db.serializar_servicio(item) for item in items]
    return ok({"items": servicios, "count": len(servicios), "next": siguiente})
