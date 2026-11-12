# itsm-catalogo — Catálogo de Servicios

Microservicio de la plataforma ITSM (Grupo 6, CS2032). Define los servicios
que los usuarios pueden solicitar: SLA, aprobación, equipo responsable y costo.
**Solicitudes** lo consulta por API al crear una solicitud.

Stack: Python 3.12 · Serverless Framework v4 · API Gateway (REST) + authorizer
Cognito · Lambda · DynamoDB.

```
Frontend / Solicitudes ──(ID token)──► API Gateway ──► Lambda ──► DynamoDB itsm-catalogo-dev
                                        authorizer Cognito (User Pool de itsm-base)
```

## Endpoints

Base: Output `ApiUrl` del stack `itsm-catalogo-<stage>`
(dev: `https://ypm1u1vp05.execute-api.us-east-1.amazonaws.com/dev`).
Header obligatorio: `Authorization: <ID token>` (no el access token, sin `Bearer`).

| Método | Ruta | Rol | Acción |
|---|---|---|---|
| POST | `/catalogo` | admin | Crear servicio |
| GET | `/catalogo` | cualquiera | Listar activos (`limit`, `next`, `categoria`; `estado=inactivo\|todos` solo admin) |
| GET | `/catalogo/{id}` | cualquiera | Detalle (contrato que consume Solicitudes) |
| PUT | `/catalogo/{id}` | admin | Actualizar parcialmente / desactivar (`{"activo": false}`) |

`{id}` va URL-encoded: `SVC%23000012`. También se acepta `SVC-000012`.

Contrato completo: [`docs/openapi.yaml`](docs/openapi.yaml). Colección Postman:
[`docs/postman_collection.json`](docs/postman_collection.json). Diseño de BD:
[`docs/modelo_datos.md`](docs/modelo_datos.md).

### Respuestas

```json
// GET /catalogo/SVC%23000003
{
  "servicio_id": "SVC#000003", "tenant_id": "empresa-alfa",
  "nombre": "Acceso VPN para personal remoto", "descripcion": "...",
  "categoria": "acceso", "sla_horas": 48, "requiere_aprobacion": true,
  "equipo_responsable": "Redes", "costo_estimado": 0,
  "activo": true, "estado": "activo",
  "creado_en": "2024-01-10T09:00:00Z", "actualizado_en": "2024-01-10T09:00:00Z"
}

// GET /catalogo?limit=2
{ "items": [ { ... }, { ... } ], "count": 2, "next": "eyJ0ZW5hbnRfaWQi..." }

// Errores (siempre con CORS)
{ "error": { "code": "NO_ENCONTRADO", "message": "Servicio no encontrado" } }
```

| HTTP | `code` | Cuándo |
|---|---|---|
| 400 | `VALIDACION` | Body/query inválido o `next` manipulado (trae `detalle`) |
| 401 | — | Sin token o token inválido (lo responde API Gateway) |
| 403 | `SIN_PERMISO` | Rol distinto de admin en POST/PUT o en `estado=inactivo\|todos` |
| 404 | `NO_ENCONTRADO` | El ID no existe **o pertenece a otro tenant** |
| 409 | `CONFLICTO` | No se pudo generar un ID libre (reintentar) |

## Seguridad y multi-tenancy

- `tenant_id` sale **solo** de `custom:tenant_id` del token. Si el body trae
  `tenant_id`, se ignora.
- Roles con `cognito:groups`, validados dentro de la Lambda.
- Toda lectura/escritura usa `tenant_id` como partition key → un ID de otro
  tenant devuelve 404. El PUT es condicional (`attribute_exists(sk)`): nunca
  crea ítems en otro tenant.
- El token `next` se valida contra el tenant del usuario.
- CORS en todas las respuestas de la Lambda y en los errores de API Gateway
  (`GatewayResponse` DEFAULT_4XX/5XX).

## Desplegar

Requisitos: Node 20+, Serverless v4 (`npm i -g serverless` + `serverless login`),
credenciales AWS y el stack `itsm-base-<stage>` ya desplegado en la misma
cuenta/región.

```bash
serverless deploy --stage dev
serverless info --stage dev --verbose   # Output ApiUrl
```

Orden del proyecto: `itsm-base` → **`itsm-catalogo`** → `itsm-solicitudes`
(usa `${cf:itsm-catalogo-<stage>.ApiUrl}` como `CATALOGO_URL`).

## Datos

```bash
pip install -r requirements.txt
python3 scripts/seed_catalogo.py --modo minimo --dry-run   # vista previa
python3 scripts/seed_catalogo.py --modo minimo             # 20 por tenant (hito)
python3 scripts/seed_catalogo.py --modo completo           # 10,000 por tenant
python3 scripts/verificar_conteos.py --esperado 10000
```

- `batch_write_item` en lotes de 25, con reintento de `UnprocessedItems`.
- Determinista e idempotente; IDs `SVC#000001`…`SVC#010000` por tenant.
- `SVC#000001`…`SVC#000020` respetan el SLA/aprobación que ya usan las
  solicitudes cargadas (`sla = [8,24,48,72][(n-1)%4]`, `aprobación = n%3==0`).
- Deja `CONTADOR#SVC` en `max(actual, 10000)`: la API sigue en `SVC#010001`.

## Pruebas

```bash
pip install -r requirements-dev.txt
python3 -m unittest discover -s tests -t . -v   # unitarias + moto (sin AWS)
python3 scripts/probar_api.py --stage dev       # contra AWS con ID tokens reales
```

`probar_api.py` verifica 401 con CORS, paginación, roles, validación, la
**prueba de aislamiento** (un ID de alfa pedido por beta → 404), desactivación y
token `next` manipulado. Crea un servicio de prueba en `empresa-alfa`.

Para obtener un ID token a mano (Postman):

```bash
python3 ../itsm-base/scripts/obtener_token.py --email admin.alfa@example.com --password 'Itsm2026!' --claims
```

## Estructura

```
serverless.yml          stack itsm-catalogo (tabla, 4 Lambdas, CORS, Outputs)
src/handlers/           crear, listar, obtener, actualizar
src/common/             auth (claims/roles), db (DynamoDB), validation, responses (CORS)
scripts/                seed_catalogo, catalogo_base (datos), verificar_conteos, probar_api
tests/                  validación, seed y API completa con moto
docs/                   modelo_datos.md, openapi.yaml, postman_collection.json
```
