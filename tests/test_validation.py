"""Pruebas unitarias de validacion y autorizacion (sin AWS)."""

import unittest
from decimal import Decimal

from src.common.auth import _normalizar_grupos, contexto
from src.common.responses import ApiError
from src.common.validation import (
    leer_estado_listado,
    leer_limit,
    normalizar_servicio_id,
    validar_actualizacion,
    validar_creacion,
)
from tests.helpers import evento

VALIDO = {
    "nombre": "Acceso VPN",
    "categoria": "acceso",
    "sla_horas": 48,
    "equipo_responsable": "Redes",
}


class IdTest(unittest.TestCase):
    def test_formatos_aceptados(self):
        for entrada in ("SVC#000012", "SVC%23000012", "svc%23000012", "SVC%2523000012",
                        "SVC-000012", "svc#12", "12", " SVC#000012 "):
            self.assertEqual(normalizar_servicio_id(entrada), "SVC#000012", entrada)

    def test_ids_invalidos_dan_404(self):
        for entrada in ("", None, "CONTADOR#SVC", "REQ#000001", "SVC#", "SVC#abc", "SVC#1234567890"):
            with self.assertRaises(ApiError) as ctx:
                normalizar_servicio_id(entrada)
            self.assertEqual(ctx.exception.status, 404)


class CreacionTest(unittest.TestCase):
    def test_valores_por_defecto(self):
        datos = validar_creacion(dict(VALIDO))
        self.assertEqual(datos["descripcion"], "")
        self.assertFalse(datos["requiere_aprobacion"])
        self.assertTrue(datos["activo"])
        self.assertEqual(datos["costo_estimado"], Decimal("0"))

    def test_ignora_campos_no_editables(self):
        datos = validar_creacion({**VALIDO, "tenant_id": "empresa-beta", "sk": "SVC#000001"})
        self.assertNotIn("tenant_id", datos)
        self.assertNotIn("sk", datos)

    def test_obligatorios(self):
        with self.assertRaises(ApiError) as ctx:
            validar_creacion({})
        self.assertEqual(ctx.exception.status, 400)
        self.assertEqual(len(ctx.exception.detalle), 4)

    def test_tipos_invalidos(self):
        casos = [
            {"categoria": "red"},
            {"sla_horas": 0},
            {"sla_horas": True},
            {"sla_horas": 1.5},
            {"sla_horas": "48"},
            {"requiere_aprobacion": "si"},
            {"costo_estimado": -1},
            {"costo_estimado": "abc"},
            {"nombre": "ab"},
            {"estado": "borrado"},
            {"activo": True, "estado": "inactivo"},
        ]
        for extra in casos:
            with self.assertRaises(ApiError, msg=extra) as ctx:
                validar_creacion({**VALIDO, **extra})
            self.assertEqual(ctx.exception.status, 400)

    def test_costo_decimal_y_estado_alias(self):
        datos = validar_creacion({**VALIDO, "costo_estimado": 99.999, "estado": "inactivo"})
        self.assertEqual(datos["costo_estimado"], Decimal("100.00"))
        self.assertFalse(datos["activo"])

    def test_normaliza_texto_y_categoria(self):
        datos = validar_creacion({**VALIDO, "nombre": "  Acceso   VPN ", "categoria": "ACCESO"})
        self.assertEqual(datos["nombre"], "Acceso VPN")
        self.assertEqual(datos["categoria"], "acceso")


class ActualizacionTest(unittest.TestCase):
    def test_parcial(self):
        self.assertEqual(validar_actualizacion({"activo": False}), {"activo": False})

    def test_sin_campos_editables(self):
        with self.assertRaises(ApiError) as ctx:
            validar_actualizacion({"tenant_id": "empresa-beta"})
        self.assertEqual(ctx.exception.status, 400)


class QueryTest(unittest.TestCase):
    def test_limit(self):
        self.assertEqual(leer_limit(None), 25)
        self.assertEqual(leer_limit({"limit": "100"}), 100)
        for malo in ("0", "101", "x"):
            with self.assertRaises(ApiError):
                leer_limit({"limit": malo})

    def test_estado(self):
        self.assertEqual(leer_estado_listado({}), "activo")
        self.assertEqual(leer_estado_listado({"estado": "TODOS"}), "todos")
        with self.assertRaises(ApiError):
            leer_estado_listado({"estado": "borrado"})


class AuthTest(unittest.TestCase):
    def test_grupos_en_varios_formatos(self):
        self.assertEqual(_normalizar_grupos(["admin"]), {"admin"})
        self.assertEqual(_normalizar_grupos("admin"), {"admin"})
        self.assertEqual(_normalizar_grupos("agente,admin"), {"agente", "admin"})
        self.assertEqual(_normalizar_grupos("[agente admin]"), {"agente", "admin"})
        self.assertEqual(_normalizar_grupos(None), set())

    def test_sin_tenant_es_401(self):
        with self.assertRaises(ApiError) as ctx:
            contexto(evento(tenant=None))
        self.assertEqual(ctx.exception.status, 401)


if __name__ == "__main__":
    unittest.main()
