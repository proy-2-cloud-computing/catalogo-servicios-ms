#!/usr/bin/env python3
"""Carga el catalogo ficticio en itsm-catalogo-<stage>.

Modos:
  minimo    SVC#000001..SVC#000020 por tenant (hito 30%).
  completo  SVC#000001..SVC#010000 por tenant = 30,000 servicios en total.

Ambos modos:
  - Usan batch_write_item en lotes de 25 y reintentan UnprocessedItems.
  - Son deterministas (misma --seed -> mismos datos) e idempotentes.
  - Dejan CONTADOR#SVC en max(valor actual, 10000), para que los servicios
    creados por la API sigan desde SVC#010001 sin chocar con la carga.

Uso:
  python3 scripts/seed_catalogo.py --modo minimo --dry-run
  python3 scripts/seed_catalogo.py --modo minimo
  python3 scripts/seed_catalogo.py --modo completo
"""

import argparse
import itertools
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catalogo_base import (  # noqa: E402
    BASE,
    EXTRA,
    MODALIDADES,
    SEDES,
    SLA_PERMITIDOS,
    TENANTS,
    aprobacion_base,
    sla_base,
)

POR_TENANT_COMPLETO = 10000
CONTADOR_FINAL = 10000
LOTE = 25
PROPORCION_INACTIVOS = 0.15

INICIO_BASE = datetime(2024, 1, 8, 9, 0, tzinfo=timezone.utc)
INICIO_GENERADOS = datetime(2024, 2, 1, 8, 0, tzinfo=timezone.utc)
FIN_GENERADOS = datetime(2026, 10, 31, 20, 0, tzinfo=timezone.utc)
AHORA = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)


def iso(fecha):
    return fecha.strftime("%Y-%m-%dT%H:%M:%SZ")


def item_servicio(tenant, numero, nombre, descripcion, categoria, equipo, costo,
                  sla_horas, requiere, activo, creado, actualizado):
    estado = "activo" if activo else "inactivo"
    return {
        "tenant_id": tenant,
        "sk": f"SVC#{numero:06d}",
        "nombre": nombre,
        "descripcion": descripcion,
        "categoria": categoria,
        "sla_horas": int(sla_horas),
        "requiere_aprobacion": bool(requiere),
        "equipo_responsable": equipo,
        "costo_estimado": Decimal(str(costo)),
        "activo": activo,
        "estado": estado,
        "estado_fecha": f"{estado}#{iso(creado)}",
        "creado_en": iso(creado),
        "actualizado_en": iso(actualizado),
    }


def servicios_base(tenant):
    """Los 20 servicios curados. Todos activos, SLA/aprobacion fijos."""
    for numero, (nombre, descripcion, categoria, equipo, costo) in enumerate(BASE[tenant], start=1):
        creado = INICIO_BASE + timedelta(days=numero - 1)
        yield item_servicio(
            tenant, numero, nombre, descripcion, categoria, equipo, costo,
            sla_base(numero), aprobacion_base(numero), True, creado, creado,
        )


def _plantillas(tenant):
    """Plantillas = 19 base (sin el 'otro') + extras de la industria."""
    plantillas = []
    for numero, (nombre, descripcion, categoria, equipo, costo) in enumerate(BASE[tenant], start=1):
        if categoria == "otro":
            continue
        plantillas.append((nombre, descripcion, categoria, equipo, costo,
                           sla_base(numero), aprobacion_base(numero)))
    for nombre, categoria, equipo, costo, sla, requiere in EXTRA[tenant]:
        plantillas.append((nombre, f"{nombre} para el personal de la organización",
                           categoria, equipo, costo, sla, requiere))
    return plantillas


def _sla_ajustado(sla, factor):
    objetivo = sla * factor
    return min(SLA_PERMITIDOS, key=lambda valor: abs(valor - objetivo))


def servicios_generados(tenant, hasta, semilla):
    """SVC#000021..SVC#<hasta>: combinaciones unicas plantilla x sede x modalidad."""
    rng = random.Random(f"{semilla}-{tenant}")
    combinaciones = list(itertools.product(_plantillas(tenant), SEDES[tenant], MODALIDADES))
    rng.shuffle(combinaciones)
    cantidad = hasta - len(BASE[tenant])
    if cantidad > len(combinaciones):
        raise SystemExit(f"Solo hay {len(combinaciones)} combinaciones para {tenant}")

    duracion = (FIN_GENERADOS - INICIO_GENERADOS).total_seconds()
    for indice, (plantilla, sede, modalidad) in enumerate(combinaciones[:cantidad]):
        numero = len(BASE[tenant]) + 1 + indice
        nombre_base, descripcion, categoria, equipo, costo, sla, requiere = plantilla
        sufijo, factor, fuerza_aprobacion = modalidad

        nombre = f"{nombre_base} - {sede}" + (f" ({sufijo})" if sufijo else "")
        detalle = f"{descripcion}. Sede/área: {sede}." + (f" Modalidad: {sufijo.lower()}." if sufijo else "")
        if fuerza_aprobacion is not None:
            requiere = fuerza_aprobacion
        elif rng.random() < 0.1:
            requiere = not requiere
        costo_final = round(costo * rng.uniform(0.8, 1.3), 2) if costo else 0
        if not costo and categoria == "hardware" and rng.random() < 0.5:
            costo_final = round(rng.uniform(50, 400), 2)

        # Fechas crecientes con el ID (con algo de ruido).
        creado = INICIO_GENERADOS + timedelta(
            seconds=duracion * indice / max(cantidad - 1, 1) + rng.randint(0, 3600 * 8)
        )
        actualizado = min(creado + timedelta(days=rng.randint(0, 120), hours=rng.randint(0, 23)), AHORA)

        yield item_servicio(
            tenant, numero, nombre, detalle, categoria, equipo, costo_final,
            _sla_ajustado(sla, factor), requiere, rng.random() >= PROPORCION_INACTIVOS,
            creado, actualizado,
        )


def generar(tenant, modo, semilla):
    yield from servicios_base(tenant)
    if modo == "completo":
        yield from servicios_generados(tenant, POR_TENANT_COMPLETO, semilla)


def escribir_lote(cliente, tabla, lote, serializador):
    """batch_write_item de hasta 25 items, reintentando UnprocessedItems."""
    pendientes = {
        tabla: [
            {"PutRequest": {"Item": {k: serializador.serialize(v) for k, v in item.items()}}}
            for item in lote
        ]
    }
    espera = 0.1
    for _ in range(8):
        respuesta = cliente.batch_write_item(RequestItems=pendientes)
        pendientes = respuesta.get("UnprocessedItems") or {}
        if not pendientes:
            return
        time.sleep(espera)
        espera = min(espera * 2, 5)
    raise RuntimeError(f"Quedaron items sin procesar: {len(pendientes.get(tabla, []))}")


def fijar_contador(tabla_recurso, tenant, valor):
    """Sube CONTADOR#SVC a `valor` solo si esta por debajo (nunca retrocede)."""
    from botocore.exceptions import ClientError

    try:
        tabla_recurso.update_item(
            Key={"tenant_id": tenant, "sk": "CONTADOR#SVC"},
            UpdateExpression="SET ultimo_id = :n, actualizado_en = :ahora",
            ConditionExpression="attribute_not_exists(ultimo_id) OR ultimo_id < :n",
            ExpressionAttributeValues={
                ":n": valor,
                ":ahora": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )
        return valor
    except ClientError as error:
        if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        actual = tabla_recurso.get_item(Key={"tenant_id": tenant, "sk": "CONTADOR#SVC"})["Item"]
        return int(actual["ultimo_id"])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--modo", choices=("minimo", "completo"), default="minimo")
    parser.add_argument("--stage", default="dev")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--table", help="Nombre de la tabla (default: itsm-catalogo-<stage>)")
    parser.add_argument("--tenants", nargs="+", default=list(TENANTS), choices=TENANTS)
    parser.add_argument("--seed", default="2026")
    parser.add_argument("--dry-run", action="store_true", help="Solo muestra lo que se cargaria")
    args = parser.parse_args()

    tabla_nombre = args.table or f"itsm-catalogo-{args.stage}"
    print(f"Tabla:   {tabla_nombre} ({args.region})")
    print(f"Modo:    {args.modo}")
    print(f"Tenants: {', '.join(args.tenants)}")

    if args.dry_run:
        for tenant in args.tenants:
            items = list(generar(tenant, args.modo, args.seed))
            activos = sum(1 for item in items if item["activo"])
            print(f"\n{tenant}: {len(items)} servicios ({activos} activos, {len(items) - activos} inactivos)")
            for item in items[:3] + items[-2:]:
                print(f"  {item['sk']} | {item['nombre']} | {item['categoria']} | "
                      f"sla={item['sla_horas']} | aprob={item['requiere_aprobacion']} | {item['estado']}")
        print("\n--dry-run: no se escribio nada.")
        return

    import boto3
    from boto3.dynamodb.types import TypeSerializer

    sesion = boto3.session.Session(region_name=args.region)
    cliente = sesion.client("dynamodb")
    tabla_recurso = sesion.resource("dynamodb").Table(tabla_nombre)
    serializador = TypeSerializer()

    inicio = time.time()
    for tenant in args.tenants:
        escritos = 0
        lote = []
        for item in generar(tenant, args.modo, args.seed):
            lote.append(item)
            if len(lote) == LOTE:
                escribir_lote(cliente, tabla_nombre, lote, serializador)
                escritos += len(lote)
                lote = []
                if escritos % 1000 == 0:
                    print(f"  {tenant}: {escritos} servicios...")
        if lote:
            escribir_lote(cliente, tabla_nombre, lote, serializador)
            escritos += len(lote)
        contador = fijar_contador(tabla_recurso, tenant, CONTADOR_FINAL)
        print(f"{tenant}: {escritos} servicios escritos; CONTADOR#SVC = {contador}")

    print(f"Listo en {time.time() - inicio:.1f} s. Verifica con: python3 scripts/verificar_conteos.py")


if __name__ == "__main__":
    main()
