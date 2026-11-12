"""GET /catalogo/{id}: detalle de un servicio.

Es el contrato que consume Solicitudes (servicio_id, nombre, sla_horas,
requiere_aprobacion, activo, tenant_id). Un servicio inactivo se devuelve con
activo=false; Solicitudes decide no aceptarlo.
"""

from src.common import db
from src.common.auth import contexto
from src.common.responses import ApiError, api_handler, ok
from src.common.validation import servicio_id_de_ruta


@api_handler
def handler(event, context):
    ctx = contexto(event)
    servicio_id = servicio_id_de_ruta(event)

    item = db.obtener_servicio(ctx["tenant_id"], servicio_id)
    if not item:
        # Mismo 404 si no existe o si pertenece a otro tenant.
        raise ApiError(404, "NO_ENCONTRADO", "Servicio no encontrado")
    return ok(db.serializar_servicio(item))
