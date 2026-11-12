"""Acceso a DynamoDB del catalogo.

Tabla itsm-catalogo-{stage}: PK tenant_id, SK sk.
  - Servicio: sk = SVC#000123 (lleva estado_fecha -> entra al GSI1)
  - Contador: sk = CONTADOR#SVC, atributo ultimo_id (no entra al GSI1)

Patrones de acceso (nunca Scan):
  - Obtener:          GetItem(PK=tenant, SK=SVC#...)
  - Listar activos:   Query(GSI1, tenant, begins_with(estado_fecha, "activo#"))
  - Listar inactivos: Query(GSI1, tenant, begins_with(estado_fecha, "inactivo#"))
  - Listar todos:     Query(tabla, tenant, begins_with(sk, "SVC#"))
  - Nuevo ID:         UpdateItem ADD ultimo_id :1 sobre CONTADOR#SVC
"""

import base64
import json
import logging
import os
from decimal import Decimal

from .responses import ApiError
from .timeutils import ahora_utc
from .validation import PREFIJO, formatear_id

logger = logging.getLogger()

CONTADOR_SK = "CONTADOR#SVC"
INTENTOS_ID = 3

_recurso = None


def _recurso_dynamo():
    global _recurso
    if _recurso is None:
        import boto3

        _recurso = boto3.resource("dynamodb")
    return _recurso


def tabla():
    return _recurso_dynamo().Table(os.environ["TABLE"])


def _codigo_error(error):
    return getattr(error, "response", {}).get("Error", {}).get("Code", "")


def estado_de(activo):
    return "activo" if activo else "inactivo"


# ---------------------------------------------------------------------------
# Crear
# ---------------------------------------------------------------------------
def nuevo_numero(tenant_id):
    """Incrementa el contador atomico del tenant y devuelve el siguiente entero."""
    respuesta = tabla().update_item(
        Key={"tenant_id": tenant_id, "sk": CONTADOR_SK},
        UpdateExpression="ADD ultimo_id :uno SET actualizado_en = :ahora",
        ExpressionAttributeValues={":uno": 1, ":ahora": ahora_utc()},
        ReturnValues="UPDATED_NEW",
    )
    return int(respuesta["Attributes"]["ultimo_id"])


def crear_servicio(tenant_id, datos):
    """Genera el ID con el contador y escribe el servicio sin pisar otro."""
    ahora = ahora_utc()
    estado = estado_de(datos["activo"])
    for _ in range(INTENTOS_ID):
        servicio_id = formatear_id(nuevo_numero(tenant_id))
        item = {
            "tenant_id": tenant_id,
            "sk": servicio_id,
            **datos,
            "estado": estado,
            "estado_fecha": f"{estado}#{ahora}",
            "creado_en": ahora,
            "actualizado_en": ahora,
        }
        try:
            tabla().put_item(
                Item=item, ConditionExpression="attribute_not_exists(sk)"
            )
            return item
        except Exception as error:
            if _codigo_error(error) != "ConditionalCheckFailedException":
                raise
            # El ID ya existia (contador atrasado): se pide el siguiente.
            logger.warning("ID %s ocupado en %s; se reintenta", servicio_id, tenant_id)
    raise ApiError(409, "CONFLICTO", "No se pudo generar un ID libre; reintenta")


# ---------------------------------------------------------------------------
# Leer
# ---------------------------------------------------------------------------
def obtener_servicio(tenant_id, servicio_id):
    respuesta = tabla().get_item(Key={"tenant_id": tenant_id, "sk": servicio_id})
    item = respuesta.get("Item")
    if not item or not str(item.get("sk", "")).startswith(PREFIJO):
        return None
    return item


def listar_servicios(tenant_id, estado="activo", limit=25, next_token=None, categoria=None):
    """Query paginada. estado: activo | inactivo | todos."""
    if estado == "todos":
        kwargs = {
            "KeyConditionExpression": "tenant_id = :tenant AND begins_with(sk, :prefijo)",
            "ExpressionAttributeValues": {":tenant": tenant_id, ":prefijo": PREFIJO},
        }
    else:
        kwargs = {
            "IndexName": "GSI1",
            "KeyConditionExpression": (
                "tenant_id = :tenant AND begins_with(estado_fecha, :prefijo)"
            ),
            "ExpressionAttributeValues": {":tenant": tenant_id, ":prefijo": f"{estado}#"},
        }
    kwargs["Limit"] = int(limit)

    if categoria:
        # FilterExpression se aplica despues del Limit: una pagina puede traer
        # menos items; el cliente sigue con `next` hasta que sea null.
        kwargs["FilterExpression"] = "categoria = :categoria"
        kwargs["ExpressionAttributeValues"][":categoria"] = categoria

    if next_token:
        kwargs["ExclusiveStartKey"] = decodificar_token(next_token, tenant_id)

    respuesta = tabla().query(**kwargs)
    return respuesta.get("Items", []), codificar_token(respuesta.get("LastEvaluatedKey"))


# ---------------------------------------------------------------------------
# Actualizar / desactivar
# ---------------------------------------------------------------------------
def actualizar_servicio(item_actual, cambios):
    """UpdateItem condicional: nunca crea un item si no existe (-> 404)."""
    tenant_id = item_actual["tenant_id"]
    servicio_id = item_actual["sk"]
    ahora = ahora_utc()

    sets = ["actualizado_en = :ahora"]
    nombres = {}
    valores = {":ahora": ahora, ":creado": item_actual["creado_en"]}

    for indice, (campo, valor) in enumerate(sorted(cambios.items())):
        nombres[f"#c{indice}"] = campo
        valores[f":v{indice}"] = valor
        sets.append(f"#c{indice} = :v{indice}")

    if "activo" in cambios:
        estado = estado_de(cambios["activo"])
        nombres["#estado"] = "estado"
        valores[":estado"] = estado
        # estado_fecha usa creado_en (no la fecha de edicion) para que el
        # orden del listado sea estable.
        valores[":ef"] = f"{estado}#{item_actual['creado_en']}"
        sets += ["#estado = :estado", "estado_fecha = :ef"]

    try:
        respuesta = tabla().update_item(
            Key={"tenant_id": tenant_id, "sk": servicio_id},
            UpdateExpression="SET " + ", ".join(sets),
            ConditionExpression="attribute_exists(sk) AND creado_en = :creado",
            ExpressionAttributeNames=nombres,
            ExpressionAttributeValues=valores,
            ReturnValues="ALL_NEW",
        )
    except Exception as error:
        if _codigo_error(error) == "ConditionalCheckFailedException":
            raise ApiError(404, "NO_ENCONTRADO", "Servicio no encontrado") from error
        raise
    return respuesta["Attributes"]


# ---------------------------------------------------------------------------
# Serializacion para la API (contrato estable que consume Solicitudes)
# ---------------------------------------------------------------------------
def serializar_servicio(item):
    salida = {
        "servicio_id": item.get("sk"),
        "tenant_id": item.get("tenant_id"),
        "nombre": item.get("nombre"),
        "descripcion": item.get("descripcion", ""),
        "categoria": item.get("categoria"),
        "sla_horas": item.get("sla_horas"),
        "requiere_aprobacion": bool(item.get("requiere_aprobacion", False)),
        "equipo_responsable": item.get("equipo_responsable"),
        "costo_estimado": item.get("costo_estimado", 0),
        "activo": bool(item.get("activo", False)),
        "estado": item.get("estado") or estado_de(item.get("activo")),
        "creado_en": item.get("creado_en"),
        "actualizado_en": item.get("actualizado_en"),
    }
    return _normalizar_decimales(salida)


def _normalizar_decimales(valor):
    if isinstance(valor, Decimal):
        if valor == valor.to_integral_value():
            return int(valor)
        return float(valor)
    if isinstance(valor, dict):
        return {clave: _normalizar_decimales(v) for clave, v in valor.items()}
    if isinstance(valor, list):
        return [_normalizar_decimales(v) for v in valor]
    return valor


# ---------------------------------------------------------------------------
# Paginacion: `next` es el LastEvaluatedKey en base64 (token opaco)
# ---------------------------------------------------------------------------
def codificar_token(last_key):
    if not last_key:
        return None
    crudo = json.dumps(last_key, default=str, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(crudo).decode().rstrip("=")


def decodificar_token(token, tenant_id):
    """Decodifica `next` y verifica que pertenezca al tenant del token."""
    try:
        texto = str(token).strip().rstrip("=")
        datos = json.loads(base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4)))
    except (ValueError, TypeError) as error:
        raise ApiError(400, "VALIDACION", "El token de paginacion no es valido") from error
    if (
        not isinstance(datos, dict)
        or datos.get("tenant_id") != tenant_id
        or not str(datos.get("sk", "")).startswith(PREFIJO)
        or not all(isinstance(v, str) for v in datos.values())
    ):
        raise ApiError(400, "VALIDACION", "El token de paginacion no es valido")
    return datos
