"""POST /catalogo: crea un servicio (solo rol admin).

El tenant sale del token; si el body trae tenant_id, servicio_id o estado_fecha
se ignoran.
"""

import logging

from src.common import db
from src.common.auth import contexto, requiere_admin
from src.common.responses import api_handler, creado
from src.common.validation import leer_body, validar_creacion

logger = logging.getLogger()


@api_handler
def handler(event, context):
    ctx = contexto(event)
    requiere_admin(ctx)
    datos = validar_creacion(leer_body(event))

    item = db.crear_servicio(ctx["tenant_id"], datos)
    logger.info(
        "servicio creado tenant=%s id=%s actor=%s",
        ctx["tenant_id"], item["sk"], ctx["usuario_id"],
    )
    return creado(db.serializar_servicio(item))
