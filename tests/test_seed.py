"""Pruebas de los datos generados por el seed (sin AWS)."""

import unittest
from collections import Counter

from scripts import seed_catalogo as seed
from src.common.validation import CATEGORIAS, validar_creacion


def a_payload(item):
    return {
        campo: item[campo]
        for campo in ("nombre", "descripcion", "categoria", "sla_horas", "requiere_aprobacion",
                      "equipo_responsable", "activo")
    } | {"costo_estimado": float(item["costo_estimado"])}


class SeedTest(unittest.TestCase):
    def test_base_coincide_con_solicitudes_cargadas(self):
        # Patron usado por las 30,000 solicitudes ya cargadas en itsm-solicitudes-dev.
        for tenant in seed.TENANTS:
            items = list(seed.generar(tenant, "minimo", "2026"))
            self.assertEqual(len(items), 20)
            for numero, item in enumerate(items, start=1):
                self.assertEqual(item["sk"], f"SVC#{numero:06d}")
                self.assertEqual(item["sla_horas"], [8, 24, 48, 72][(numero - 1) % 4])
                self.assertEqual(item["requiere_aprobacion"], numero % 3 == 0)
                self.assertTrue(item["activo"])

    def test_completo_10000_por_tenant_validos_y_unicos(self):
        for tenant in seed.TENANTS:
            items = list(seed.generar(tenant, "completo", "2026"))
            self.assertEqual(len(items), 10000)
            self.assertEqual(len({item["sk"] for item in items}), 10000)
            self.assertEqual(items[-1]["sk"], "SVC#010000")
            self.assertEqual(len({item["nombre"] for item in items}), 10000, tenant)

            categorias = Counter(item["categoria"] for item in items)
            self.assertTrue(set(categorias) <= set(CATEGORIAS))
            inactivos = sum(1 for item in items if not item["activo"])
            self.assertTrue(1000 < inactivos < 2000, inactivos)

            for item in items:
                self.assertEqual(item["estado_fecha"], f"{item['estado']}#{item['creado_en']}")
                self.assertLessEqual(item["creado_en"], item["actualizado_en"])
            # Mismas reglas que la API (POST /catalogo) en una muestra.
            for item in items[::250]:
                validar_creacion(a_payload(item))

    def test_determinista(self):
        uno = list(seed.generar("empresa-beta", "completo", "2026"))[100:105]
        dos = list(seed.generar("empresa-beta", "completo", "2026"))[100:105]
        self.assertEqual(uno, dos)


if __name__ == "__main__":
    unittest.main()
