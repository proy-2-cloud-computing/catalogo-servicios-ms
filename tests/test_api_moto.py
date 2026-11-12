"""Pruebas de punta a punta de los 4 handlers contra DynamoDB simulado (moto).

    pip install -r requirements-dev.txt
    python3 -m unittest discover -s tests -v

Si moto no esta instalado, estas pruebas se omiten.
"""

import base64
import importlib
import json
import os
import unittest

try:
    import boto3
    from moto import mock_aws
except ImportError:  # pragma: no cover
    mock_aws = None

from tests.helpers import cuerpo, evento

REGION = "us-east-1"
TABLA = "itsm-catalogo-test"

SERVICIO = {
    "nombre": "Acceso VPN",
    "descripcion": "Alta de acceso remoto por VPN",
    "categoria": "acceso",
    "sla_horas": 48,
    "requiere_aprobacion": True,
    "equipo_responsable": "Redes",
    "costo_estimado": 0,
}


@unittest.skipIf(mock_aws is None, "moto no esta instalado")
class CatalogoApiTest(unittest.TestCase):
    def setUp(self):
        os.environ.update({
            "AWS_DEFAULT_REGION": REGION,
            "AWS_ACCESS_KEY_ID": "test",
            "AWS_SECRET_ACCESS_KEY": "test",
            "TABLE": TABLA,
        })
        self.mock = mock_aws()
        self.mock.start()

        from src.common import db
        db._recurso = None

        boto3.client("dynamodb", region_name=REGION).create_table(
            TableName=TABLA,
            BillingMode="PAY_PER_REQUEST",
            AttributeDefinitions=[
                {"AttributeName": "tenant_id", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
                {"AttributeName": "estado_fecha", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "tenant_id", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            GlobalSecondaryIndexes=[{
                "IndexName": "GSI1",
                "KeySchema": [
                    {"AttributeName": "tenant_id", "KeyType": "HASH"},
                    {"AttributeName": "estado_fecha", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }],
        )
        self.tabla = boto3.resource("dynamodb", region_name=REGION).Table(TABLA)
        # Igual que el seed: contador en 10000 para cada tenant.
        for tenant in ("empresa-alfa", "empresa-beta"):
            self.tabla.put_item(Item={"tenant_id": tenant, "sk": "CONTADOR#SVC", "ultimo_id": 10000})

    def tearDown(self):
        self.mock.stop()

    def llamar(self, modulo, **kwargs):
        return importlib.import_module(f"src.handlers.{modulo}").handler(evento(**kwargs), None)

    def crear(self, tenant="empresa-alfa", **extra):
        respuesta = self.llamar("crear", body={**SERVICIO, **extra}, tenant=tenant)
        self.assertEqual(respuesta["statusCode"], 201, respuesta["body"])
        return cuerpo(respuesta)

    # ----------------------------------------------------------------- POST
    def test_crear_genera_id_consecutivo_y_estado(self):
        primero = self.crear()
        segundo = self.crear(nombre="Instalacion de software", categoria="software")
        self.assertEqual(primero["servicio_id"], "SVC#010001")
        self.assertEqual(segundo["servicio_id"], "SVC#010002")
        self.assertEqual(primero["estado"], "activo")
        self.assertTrue(primero["activo"])
        self.assertEqual(primero["sla_horas"], 48)

        item = self.tabla.get_item(Key={"tenant_id": "empresa-alfa", "sk": "SVC#010001"})["Item"]
        self.assertTrue(item["estado_fecha"].startswith("activo#"))
        contador = self.tabla.get_item(Key={"tenant_id": "empresa-alfa", "sk": "CONTADOR#SVC"})["Item"]
        self.assertEqual(int(contador["ultimo_id"]), 10002)

    def test_crear_ignora_tenant_del_body(self):
        creado = self.crear(tenant="empresa-alfa", tenant_id="empresa-beta")
        self.assertEqual(creado["tenant_id"], "empresa-alfa")
        self.assertNotIn(
            "Item", self.tabla.get_item(Key={"tenant_id": "empresa-beta", "sk": creado["servicio_id"]})
        )

    def test_crear_sin_contador_empieza_en_1(self):
        respuesta = self.llamar("crear", body=SERVICIO, tenant="empresa-gamma")
        self.assertEqual(cuerpo(respuesta)["servicio_id"], "SVC#000001")

    def test_crear_salta_ids_ocupados(self):
        self.tabla.put_item(Item={"tenant_id": "empresa-alfa", "sk": "SVC#010001", "nombre": "x"})
        self.assertEqual(self.crear()["servicio_id"], "SVC#010002")

    def test_crear_requiere_admin(self):
        for grupos in (("solicitante",), ("agente", "aprobador"), ()):
            respuesta = self.llamar("crear", body=SERVICIO, grupos=grupos)
            self.assertEqual(respuesta["statusCode"], 403)
            self.assertEqual(cuerpo(respuesta)["error"]["code"], "SIN_PERMISO")

    def test_crear_body_invalido(self):
        respuesta = self.llamar("crear", body={"nombre": "x"})
        self.assertEqual(respuesta["statusCode"], 400)
        self.assertEqual(cuerpo(respuesta)["error"]["code"], "VALIDACION")
        self.assertIn("Access-Control-Allow-Origin", respuesta["headers"])

    # ------------------------------------------------------------ GET /{id}
    def test_obtener_contrato_para_solicitudes(self):
        creado = self.crear()
        respuesta = self.llamar("obtener", servicio_id="SVC%23010001", grupos=("solicitante",))
        self.assertEqual(respuesta["statusCode"], 200)
        datos = cuerpo(respuesta)
        self.assertEqual(datos, creado)
        for campo in ("servicio_id", "tenant_id", "nombre", "sla_horas", "requiere_aprobacion", "activo"):
            self.assertIn(campo, datos)
        self.assertIsInstance(datos["sla_horas"], int)
        self.assertIsInstance(datos["requiere_aprobacion"], bool)
        self.assertNotIn("sk", datos)
        self.assertNotIn("estado_fecha", datos)

    def test_aislamiento_otro_tenant_da_404(self):
        self.crear(tenant="empresa-alfa")
        respuesta = self.llamar("obtener", servicio_id="SVC%23010001", tenant="empresa-beta")
        self.assertEqual(respuesta["statusCode"], 404)
        self.assertEqual(cuerpo(respuesta)["error"]["code"], "NO_ENCONTRADO")
        self.assertEqual(respuesta["headers"]["Access-Control-Allow-Origin"], "*")

    def test_obtener_no_expone_el_contador(self):
        respuesta = self.llamar("obtener", servicio_id="CONTADOR%23SVC")
        self.assertEqual(respuesta["statusCode"], 404)

    def test_obtener_inactivo_devuelve_activo_false(self):
        self.crear(activo=False)
        datos = cuerpo(self.llamar("obtener", servicio_id="SVC-010001"))
        self.assertFalse(datos["activo"])
        self.assertEqual(datos["estado"], "inactivo")

    # --------------------------------------------------------------- GET /
    def test_listar_solo_activos_y_paginado(self):
        for numero in range(5):
            self.crear(nombre=f"Servicio activo {numero}")
        self.crear(nombre="Servicio retirado", activo=False)
        self.crear(tenant="empresa-beta", nombre="Servicio de beta")

        vistos = []
        siguiente = None
        paginas = 0
        while True:
            query = {"limit": "2"}
            if siguiente:
                query["next"] = siguiente
            datos = cuerpo(self.llamar("listar", query=query, grupos=("solicitante",)))
            vistos += [item["nombre"] for item in datos["items"]]
            self.assertTrue(all(item["tenant_id"] == "empresa-alfa" for item in datos["items"]))
            siguiente = datos["next"]
            paginas += 1
            if not siguiente:
                break
        self.assertEqual(sorted(vistos), [f"Servicio activo {n}" for n in range(5)])
        self.assertGreaterEqual(paginas, 3)

    def test_listar_inactivos_y_todos_solo_admin(self):
        self.crear()
        self.crear(nombre="Servicio retirado", activo=False)
        self.assertEqual(
            self.llamar("listar", query={"estado": "inactivo"}, grupos=("agente",))["statusCode"], 403
        )
        inactivos = cuerpo(self.llamar("listar", query={"estado": "inactivo"}))
        self.assertEqual([i["nombre"] for i in inactivos["items"]], ["Servicio retirado"])
        todos = cuerpo(self.llamar("listar", query={"estado": "todos"}))
        self.assertEqual(todos["count"], 2)

    def test_listar_por_categoria(self):
        self.crear()
        self.crear(nombre="Laptop", categoria="hardware")
        datos = cuerpo(self.llamar("listar", query={"categoria": "hardware"}))
        self.assertEqual([i["nombre"] for i in datos["items"]], ["Laptop"])

    def test_next_de_otro_tenant_es_rechazado(self):
        falso = {"tenant_id": "empresa-beta", "sk": "SVC#000001", "estado_fecha": "activo#2026"}
        token = base64.urlsafe_b64encode(json.dumps(falso).encode()).decode()
        respuesta = self.llamar("listar", query={"next": token})
        self.assertEqual(respuesta["statusCode"], 400)
        self.assertEqual(self.llamar("listar", query={"next": "%%%"})["statusCode"], 400)

    # ------------------------------------------------------------------ PUT
    def test_desactivar_y_reactivar(self):
        creado = self.crear()
        respuesta = self.llamar("actualizar", servicio_id="SVC%23010001", body={"activo": False})
        self.assertEqual(respuesta["statusCode"], 200)
        datos = cuerpo(respuesta)
        self.assertEqual(datos["estado"], "inactivo")
        self.assertEqual(datos["creado_en"], creado["creado_en"])

        item = self.tabla.get_item(Key={"tenant_id": "empresa-alfa", "sk": "SVC#010001"})["Item"]
        self.assertEqual(item["estado_fecha"], f"inactivo#{creado['creado_en']}")
        self.assertEqual(cuerpo(self.llamar("listar"))["count"], 0)

        self.llamar("actualizar", servicio_id="SVC%23010001", body={"estado": "activo"})
        self.assertEqual(cuerpo(self.llamar("listar"))["count"], 1)

    def test_actualizar_parcial(self):
        self.crear()
        datos = cuerpo(self.llamar(
            "actualizar", servicio_id="SVC%23010001",
            body={"sla_horas": 24, "costo_estimado": 15.5, "tenant_id": "empresa-beta"},
        ))
        self.assertEqual(datos["sla_horas"], 24)
        self.assertEqual(datos["costo_estimado"], 15.5)
        self.assertEqual(datos["nombre"], "Acceso VPN")
        self.assertEqual(datos["tenant_id"], "empresa-alfa")

    def test_actualizar_otro_tenant_da_404_y_no_crea_nada(self):
        self.crear(tenant="empresa-alfa")
        respuesta = self.llamar(
            "actualizar", servicio_id="SVC%23010001", tenant="empresa-beta", body={"activo": False}
        )
        self.assertEqual(respuesta["statusCode"], 404)
        self.assertNotIn("Item", self.tabla.get_item(Key={"tenant_id": "empresa-beta", "sk": "SVC#010001"}))
        alfa = self.tabla.get_item(Key={"tenant_id": "empresa-alfa", "sk": "SVC#010001"})["Item"]
        self.assertTrue(alfa["activo"])

    def test_actualizar_requiere_admin(self):
        self.crear()
        respuesta = self.llamar(
            "actualizar", servicio_id="SVC%23010001", body={"activo": False}, grupos=("aprobador",)
        )
        self.assertEqual(respuesta["statusCode"], 403)


if __name__ == "__main__":
    unittest.main()
