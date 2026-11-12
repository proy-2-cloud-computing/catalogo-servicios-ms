#!/usr/bin/env python3
"""Pruebas de punta a punta contra el API desplegado (evidencia para el informe).

Obtiene ID tokens reales de Cognito (usuarios de itsm-base/scripts/crear_usuarios.py)
y verifica autenticacion, roles, multi-tenancy (404 entre tenants), paginacion,
validacion, desactivacion y CORS.

ATENCION: crea 1 servicio nuevo en empresa-alfa (lo deja activo al final).

Uso:
  python3 scripts/probar_api.py [--stage dev] [--password 'Itsm2026!']
"""

import argparse
import base64
import json
import sys
import urllib.error
import urllib.request
from urllib.parse import quote

RESULTADOS = []


def outputs(cfn, stack):
    salida = cfn.describe_stacks(StackName=stack)["Stacks"][0].get("Outputs", [])
    return {o["OutputKey"]: o["OutputValue"] for o in salida}


def id_token(cognito, client_id, email, password):
    respuesta = cognito.initiate_auth(
        ClientId=client_id,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": email, "PASSWORD": password},
    )
    return respuesta["AuthenticationResult"]["IdToken"]


def llamar(metodo, url, token=None, body=None, headers=None):
    cabeceras = dict(headers or {})
    if token:
        cabeceras["Authorization"] = token
    datos = None
    if body is not None:
        datos = json.dumps(body).encode()
        cabeceras["Content-Type"] = "application/json"
    peticion = urllib.request.Request(url, data=datos, method=metodo, headers=cabeceras)
    try:
        with urllib.request.urlopen(peticion, timeout=20) as respuesta:
            estado, cab, crudo = respuesta.status, respuesta.headers, respuesta.read()
    except urllib.error.HTTPError as error:
        estado, cab, crudo = error.code, error.headers, error.read()
    try:
        cuerpo = json.loads(crudo) if crudo else None
    except ValueError:
        cuerpo = crudo.decode(errors="replace")
    return estado, cab, cuerpo


def comprobar(nombre, condicion, detalle=""):
    RESULTADOS.append((nombre, bool(condicion)))
    marca = "PASS" if condicion else "FAIL"
    print(f"[{marca}] {nombre}" + (f"  -> {detalle}" if detalle else ""))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stage", default="dev")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--password", default="Itsm2026!")
    args = parser.parse_args()

    import boto3

    sesion = boto3.session.Session(region_name=args.region)
    cfn = sesion.client("cloudformation")
    base = outputs(cfn, f"itsm-base-{args.stage}")
    api = outputs(cfn, f"itsm-catalogo-{args.stage}")["ApiUrl"].rstrip("/")
    cognito = sesion.client("cognito-idp")
    tok = {
        nombre: id_token(cognito, base["UserPoolClientId"], email, args.password)
        for nombre, email in {
            "admin_alfa": "admin.alfa@example.com",
            "solic_alfa": "solicitante.alfa@example.com",
            "admin_beta": "admin.beta@example.com",
            "solic_beta": "solicitante.beta@example.com",
        }.items()
    }
    print(f"API: {api}\n")

    # 1. Autenticacion y CORS en errores del authorizer
    estado, cab, cuerpo = llamar("GET", f"{api}/catalogo")
    comprobar("GET sin token -> 401 con CORS",
              estado == 401 and cab.get("Access-Control-Allow-Origin") == "*", f"{estado} {cuerpo}")
    estado, cab, _ = llamar("OPTIONS", f"{api}/catalogo", headers={
        "Origin": "https://ejemplo.amplifyapp.com", "Access-Control-Request-Method": "GET"})
    comprobar("OPTIONS (preflight) -> CORS", estado in (200, 204) and cab.get("Access-Control-Allow-Origin"),
              f"{estado} allow-origin={cab.get('Access-Control-Allow-Origin')}")

    # 2. Listado paginado (solo activos, solo del tenant del token)
    estado, _, pagina = llamar("GET", f"{api}/catalogo?limit=5", tok["solic_alfa"])
    comprobar("GET /catalogo?limit=5 (solicitante) -> 200, 5 items y next",
              estado == 200 and pagina["count"] == 5 and pagina["next"], f"{estado} count={pagina.get('count')}")
    vistos, siguiente = [], None
    while True:
        url = f"{api}/catalogo?limit=7" + (f"&next={quote(siguiente)}" if siguiente else "")
        _, _, pagina = llamar("GET", url, tok["solic_alfa"])
        vistos += pagina["items"]
        siguiente = pagina["next"]
        if not siguiente:
            break
    comprobar("Paginacion completa con next (activos de alfa)",
              len(vistos) >= 20 and all(s["tenant_id"] == "empresa-alfa" and s["activo"] for s in vistos),
              f"{len(vistos)} servicios")

    # 3. Mismo ID en dos tenants: cada uno ve el suyo
    _, _, alfa1 = llamar("GET", f"{api}/catalogo/SVC%23000003", tok["solic_alfa"])
    _, _, beta1 = llamar("GET", f"{api}/catalogo/SVC%23000003", tok["solic_beta"])
    comprobar("SVC#000003: alfa y beta ven datos distintos (PK = tenant del token)",
              alfa1["tenant_id"] == "empresa-alfa" and beta1["tenant_id"] == "empresa-beta"
              and alfa1["nombre"] != beta1["nombre"], f"alfa='{alfa1['nombre']}' | beta='{beta1['nombre']}'")
    comprobar("Contrato para Solicitudes (nombre, sla_horas int, requiere_aprobacion bool, activo)",
              isinstance(alfa1["sla_horas"], int) and isinstance(alfa1["requiere_aprobacion"], bool)
              and alfa1["activo"] is True, json.dumps({k: alfa1[k] for k in ("servicio_id", "sla_horas", "requiere_aprobacion")}))
    estado, _, otro = llamar("GET", f"{api}/catalogo/SVC-000003", tok["solic_alfa"])
    comprobar("Formato de ID alternativo SVC-000003 -> 200", estado == 200 and otro["servicio_id"] == "SVC#000003")

    # 4. Roles
    nuevo = {
        "nombre": "Acceso a red Wi-Fi de invitados", "descripcion": "Credenciales temporales para visitantes en tienda",
        "categoria": "acceso", "sla_horas": 4, "requiere_aprobacion": False,
        "equipo_responsable": "Redes", "costo_estimado": 0,
        "tenant_id": "empresa-beta",  # intento de suplantar tenant: debe ignorarse
    }
    estado, _, cuerpo = llamar("POST", f"{api}/catalogo", tok["solic_alfa"], nuevo)
    comprobar("POST como solicitante -> 403 SIN_PERMISO", estado == 403, f"{estado} {cuerpo}")
    estado, _, cuerpo = llamar("POST", f"{api}/catalogo", tok["admin_alfa"], {"nombre": "x", "sla_horas": -1})
    comprobar("POST body invalido -> 400 VALIDACION", estado == 400 and cuerpo["error"]["code"] == "VALIDACION",
              json.dumps(cuerpo["error"].get("detalle"), ensure_ascii=False))

    # 5. Crear como admin (tenant del token, no del body)
    estado, _, creado = llamar("POST", f"{api}/catalogo", tok["admin_alfa"], nuevo)
    comprobar("POST como admin alfa con tenant_id=beta en el body -> 201 en alfa",
              estado == 201 and creado["tenant_id"] == "empresa-alfa", f"{estado} {creado.get('servicio_id')}")
    sid = quote(creado["servicio_id"], safe="")

    # 6. Aislamiento
    estado, cab, cuerpo = llamar("GET", f"{api}/catalogo/{sid}", tok["admin_beta"])
    comprobar(f"AISLAMIENTO: beta pide {creado['servicio_id']} (solo existe en alfa) -> 404",
              estado == 404 and cab.get("Access-Control-Allow-Origin") == "*", f"{estado} {cuerpo}")
    estado, _, _ = llamar("PUT", f"{api}/catalogo/{sid}", tok["admin_beta"], {"activo": False})
    estado2, _, _ = llamar("GET", f"{api}/catalogo/{sid}", tok["admin_beta"])
    _, _, sigue = llamar("GET", f"{api}/catalogo/{sid}", tok["admin_alfa"])
    comprobar("AISLAMIENTO: PUT de beta sobre ID de alfa -> 404 y no crea ni modifica nada",
              estado == 404 and estado2 == 404 and sigue["activo"] is True, f"put={estado} get_beta={estado2}")

    # 7. Desactivar / filtros / reactivar
    estado, _, cuerpo = llamar("PUT", f"{api}/catalogo/{sid}", tok["admin_alfa"], {"activo": False, "sla_horas": 8})
    comprobar("PUT desactivar (admin) -> 200 estado=inactivo",
              estado == 200 and cuerpo["estado"] == "inactivo" and cuerpo["sla_horas"] == 8, f"{estado}")
    _, _, por_id = llamar("GET", f"{api}/catalogo/{sid}", tok["solic_alfa"])
    comprobar("GET por ID de un inactivo -> 200 con activo=false", por_id["activo"] is False)
    estado, _, _ = llamar("GET", f"{api}/catalogo?estado=inactivo", tok["solic_alfa"])
    comprobar("GET ?estado=inactivo como solicitante -> 403", estado == 403)
    _, _, inactivos = llamar("GET", f"{api}/catalogo?estado=inactivo", tok["admin_alfa"])
    comprobar("GET ?estado=inactivo como admin -> incluye el desactivado",
              any(s["servicio_id"] == creado["servicio_id"] for s in inactivos["items"]))
    estado, _, cuerpo = llamar("PUT", f"{api}/catalogo/{sid}", tok["admin_alfa"], {"activo": True})
    comprobar("PUT reactivar -> 200 estado=activo", estado == 200 and cuerpo["estado"] == "activo")

    # 8. Token de paginacion manipulado
    falso = base64.urlsafe_b64encode(json.dumps(
        {"tenant_id": "empresa-beta", "sk": "SVC#000001", "estado_fecha": "activo#2024"}).encode()).decode()
    estado, _, _ = llamar("GET", f"{api}/catalogo?next={quote(falso)}", tok["solic_alfa"])
    comprobar("next con tenant ajeno -> 400", estado == 400)

    total = len(RESULTADOS)
    aprobadas = sum(1 for _, ok in RESULTADOS if ok)
    print(f"\n{aprobadas}/{total} pruebas OK")
    sys.exit(0 if aprobadas == total else 1)


if __name__ == "__main__":
    main()
