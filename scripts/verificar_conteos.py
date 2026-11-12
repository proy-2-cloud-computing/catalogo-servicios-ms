#!/usr/bin/env python3
"""Verifica los conteos del catalogo por tenant (solo lectura, sin Scan).

Por tenant muestra:
  - total de servicios: Query(PK=tenant, begins_with(sk, "SVC#")) con Select=COUNT
  - activos / inactivos: Query sobre GSI1 con begins_with(estado_fecha, ...)
  - valor de CONTADOR#SVC

Select=COUNT tambien pagina (1 MB por pagina): se suman todas las paginas.

Uso:
  python3 scripts/verificar_conteos.py [--stage dev] [--esperado 10000]
"""

import argparse

TENANTS = ("empresa-alfa", "empresa-beta", "empresa-gamma")


def contar(tabla, **kwargs):
    kwargs["Select"] = "COUNT"
    total = 0
    while True:
        respuesta = tabla.query(**kwargs)
        total += respuesta["Count"]
        if "LastEvaluatedKey" not in respuesta:
            return total
        kwargs["ExclusiveStartKey"] = respuesta["LastEvaluatedKey"]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stage", default="dev")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--table")
    parser.add_argument("--esperado", type=int, help="Total esperado por tenant (ej. 10000)")
    args = parser.parse_args()

    import boto3
    from boto3.dynamodb.conditions import Key

    nombre = args.table or f"itsm-catalogo-{args.stage}"
    tabla = boto3.resource("dynamodb", region_name=args.region).Table(nombre)
    print(f"Tabla: {nombre}\n")
    print(f"{'tenant':<15}{'total':>8}{'activos':>9}{'inactivos':>11}{'contador':>10}")

    ok = True
    gran_total = 0
    for tenant in TENANTS:
        total = contar(tabla, KeyConditionExpression=Key("tenant_id").eq(tenant) & Key("sk").begins_with("SVC#"))
        activos = contar(tabla, IndexName="GSI1",
                         KeyConditionExpression=Key("tenant_id").eq(tenant) & Key("estado_fecha").begins_with("activo#"))
        inactivos = contar(tabla, IndexName="GSI1",
                           KeyConditionExpression=Key("tenant_id").eq(tenant) & Key("estado_fecha").begins_with("inactivo#"))
        item = tabla.get_item(Key={"tenant_id": tenant, "sk": "CONTADOR#SVC"}).get("Item")
        contador = int(item["ultimo_id"]) if item else "-"
        gran_total += total
        print(f"{tenant:<15}{total:>8}{activos:>9}{inactivos:>11}{contador:>10}")
        if activos + inactivos != total:
            ok = False
            print(f"  ! {tenant}: activos + inactivos ({activos + inactivos}) != total ({total})")
        if args.esperado is not None and total != args.esperado:
            ok = False
            print(f"  ! {tenant}: se esperaban {args.esperado}")

    print(f"\nTotal: {gran_total} servicios")
    print("OK" if ok else "HAY DIFERENCIAS")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
