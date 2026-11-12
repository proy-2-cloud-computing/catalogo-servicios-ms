"""PUT /catalogo/{id}: actualiza o desactiva un servicio (solo rol admin).

Actualizacion parcial: solo se modifican los campos enviados.
Desactivar:  {"activo": false}   (o {"estado": "inactivo"})
Reactivar:   {"activo": true}
"""

import logging

from src.common import db
from src.common.auth import contexto, requiere_admin
from src.common.responses import ApiError, api_handler, ok
from src.common.validation import leer_body, servicio_id_de_ruta, validar_actualizacion

logger = logging.getLogger()


@api_handler
def handler(event, context):
    ctx = contexto(event)
    requiere_admin(ctx)
    servicio_id = servicio_id_de_ruta(event)
    cambios = validar_actualizacion(leer_body(event))

    actual = db.obtener_servicio(ctx["tenant_id"], servicio_id)
    if not actual:
        raise ApiError(404, "NO_ENCONTRADO", "Servicio no encontrado")

    item = db.actualizar_servicio(actual, cambios)
    logger.info(
        "servicio actualizado tenant=%s id=%s campos=%s actor=%s",
        ctx["tenant_id"], servicio_id, sorted(cambios), ctx["usuario_id"],
    )
    return ok(db.serializar_servicio(item))
