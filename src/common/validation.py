"""Validacion de entradas del catalogo."""

import json
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import unquote

from .responses import ApiError

CATEGORIAS = ("acceso", "hardware", "software", "soporte", "otro")
ESTADOS = ("activo", "inactivo")

PREFIJO = "SVC#"
_ID = re.compile(r"^(?:SVC(?:#|-|_)?)?(\d{1,9})$")

LIMIT_POR_DEFECTO = 25
LIMIT_MAXIMO = 100
SLA_MAXIMO = 8760  # un año en horas
COSTO_MAXIMO = Decimal("10000000")

# Campos que un admin puede enviar en POST/PUT. Cualquier otro (tenant_id,
# servicio_id, sk, creado_en, estado_fecha...) se ignora: no son editables.
CAMPOS_EDITABLES = (
    "nombre",
    "descripcion",
    "categoria",
    "sla_horas",
    "requiere_aprobacion",
    "equipo_responsable",
    "costo_estimado",
    "activo",
)


# ---------------------------------------------------------------------------
# IDs
# ---------------------------------------------------------------------------
def formatear_id(numero):
    return f"{PREFIJO}{int(numero):06d}"


def normalizar_servicio_id(valor):
    """Devuelve el ID canonico SVC#000012 o lanza 404.

    API Gateway (REST) entrega pathParameters SIN decodificar, asi que llega
    "SVC%23000012". Tambien se aceptan SVC-000012, svc#12 y 12.
    """
    texto = str(valor or "").strip()
    for _ in range(2):  # tolera doble codificacion (%2523)
        decodificado = unquote(texto)
        if decodificado == texto:
            break
        texto = decodificado
    coincidencia = _ID.match(texto.upper())
    if not coincidencia:
        raise ApiError(404, "NO_ENCONTRADO", "Servicio no encontrado")
    return formatear_id(coincidencia.group(1))


def servicio_id_de_ruta(event):
    return normalizar_servicio_id((event.get("pathParameters") or {}).get("id"))


# ---------------------------------------------------------------------------
# Body
# ---------------------------------------------------------------------------
def leer_body(event):
    crudo = event.get("body")
    if crudo in (None, ""):
        raise ApiError(400, "VALIDACION", "El body es obligatorio")
    if isinstance(crudo, dict):
        datos = crudo
    else:
        try:
            datos = json.loads(crudo)
        except (TypeError, ValueError) as error:
            raise ApiError(400, "VALIDACION", "El body no es JSON valido") from error
    if not isinstance(datos, dict):
        raise ApiError(400, "VALIDACION", "El body debe ser un objeto JSON")
    return datos


def _texto(datos, campo, minimo, maximo, errores, obligatorio):
    if campo not in datos or datos[campo] is None:
        if obligatorio:
            errores.append(f"'{campo}' es obligatorio")
        return None
    valor = datos[campo]
    if not isinstance(valor, str):
        errores.append(f"'{campo}' debe ser texto")
        return None
    valor = " ".join(valor.split())
    if not minimo <= len(valor) <= maximo:
        errores.append(f"'{campo}' debe tener entre {minimo} y {maximo} caracteres")
        return None
    return valor


def _booleano(datos, campo, errores):
    if campo not in datos or datos[campo] is None:
        return None
    if not isinstance(datos[campo], bool):
        errores.append(f"'{campo}' debe ser booleano (true/false)")
        return None
    return datos[campo]


def _entero(datos, campo, minimo, maximo, errores, obligatorio):
    if campo not in datos or datos[campo] is None:
        if obligatorio:
            errores.append(f"'{campo}' es obligatorio")
        return None
    valor = datos[campo]
    # bool es subclase de int: se rechaza explicitamente.
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or int(valor) != valor:
        errores.append(f"'{campo}' debe ser un entero")
        return None
    valor = int(valor)
    if not minimo <= valor <= maximo:
        errores.append(f"'{campo}' debe estar entre {minimo} y {maximo}")
        return None
    return valor


def _costo(datos, errores):
    if "costo_estimado" not in datos or datos["costo_estimado"] is None:
        return None
    valor = datos["costo_estimado"]
    if isinstance(valor, bool) or not isinstance(valor, (int, float, str)):
        errores.append("'costo_estimado' debe ser numerico")
        return None
    try:
        numero = Decimal(str(valor)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        errores.append("'costo_estimado' debe ser numerico")
        return None
    if not Decimal("0") <= numero <= COSTO_MAXIMO:
        errores.append("'costo_estimado' debe estar entre 0 y 10000000")
        return None
    if numero == numero.to_integral_value():
        numero = numero.quantize(Decimal("1"))
    return numero


def _activo(datos, errores):
    """Acepta 'activo' (bool) o, por comodidad, 'estado' (activo|inactivo)."""
    activo = _booleano(datos, "activo", errores)
    estado = datos.get("estado")
    if estado is None:
        return activo
    if estado not in ESTADOS:
        errores.append(f"'estado' debe ser uno de: {', '.join(ESTADOS)}")
        return activo
    desde_estado = estado == "activo"
    if activo is not None and activo != desde_estado:
        errores.append("'activo' y 'estado' se contradicen")
        return activo
    return desde_estado


def _validar(datos, parcial):
    errores = []
    limpio = {
        "nombre": _texto(datos, "nombre", 3, 120, errores, obligatorio=not parcial),
        "descripcion": _texto(datos, "descripcion", 0, 1000, errores, obligatorio=False),
        "categoria": None,
        "sla_horas": _entero(datos, "sla_horas", 1, SLA_MAXIMO, errores, obligatorio=not parcial),
        "requiere_aprobacion": _booleano(datos, "requiere_aprobacion", errores),
        "equipo_responsable": _texto(
            datos, "equipo_responsable", 2, 80, errores, obligatorio=not parcial
        ),
        "costo_estimado": _costo(datos, errores),
        "activo": _activo(datos, errores),
    }

    categoria = datos.get("categoria")
    if categoria is None:
        if not parcial:
            errores.append("'categoria' es obligatoria")
    elif not isinstance(categoria, str) or categoria.strip().lower() not in CATEGORIAS:
        errores.append(f"'categoria' debe ser una de: {', '.join(CATEGORIAS)}")
    else:
        limpio["categoria"] = categoria.strip().lower()

    if errores:
        raise ApiError(400, "VALIDACION", "Datos invalidos", detalle=errores)
    return {campo: valor for campo, valor in limpio.items() if valor is not None}


def validar_creacion(datos):
    limpio = _validar(datos, parcial=False)
    limpio.setdefault("descripcion", "")
    limpio.setdefault("requiere_aprobacion", False)
    limpio.setdefault("costo_estimado", Decimal("0"))
    limpio.setdefault("activo", True)
    return limpio


def validar_actualizacion(datos):
    limpio = _validar(datos, parcial=True)
    if not limpio:
        raise ApiError(
            400,
            "VALIDACION",
            "Envia al menos un campo editable",
            detalle=list(CAMPOS_EDITABLES),
        )
    return limpio


# ---------------------------------------------------------------------------
# Query params
# ---------------------------------------------------------------------------
def leer_limit(query):
    crudo = (query or {}).get("limit")
    if crudo in (None, ""):
        return LIMIT_POR_DEFECTO
    try:
        valor = int(crudo)
    except (TypeError, ValueError) as error:
        raise ApiError(400, "VALIDACION", "'limit' debe ser un entero") from error
    if not 1 <= valor <= LIMIT_MAXIMO:
        raise ApiError(400, "VALIDACION", f"'limit' debe estar entre 1 y {LIMIT_MAXIMO}")
    return valor


def leer_estado_listado(query):
    """activo (por defecto), inactivo o todos."""
    estado = ((query or {}).get("estado") or "activo").strip().lower()
    if estado not in ("activo", "inactivo", "todos"):
        raise ApiError(400, "VALIDACION", "'estado' debe ser activo, inactivo o todos")
    return estado


def leer_categoria(query):
    categoria = (query or {}).get("categoria")
    if categoria in (None, ""):
        return None
    categoria = categoria.strip().lower()
    if categoria not in CATEGORIAS:
        raise ApiError(
            400, "VALIDACION", f"'categoria' debe ser una de: {', '.join(CATEGORIAS)}"
        )
    return categoria
