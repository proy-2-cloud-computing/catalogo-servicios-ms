# Diseño de base de datos: microservicio Catálogo de Servicios (NoSQL / DynamoDB)

Tabla: **`itsm-catalogo-{stage}`** (`itsm-catalogo-dev`), modo `PAY_PER_REQUEST`,
una sola tabla para el servicio. Multi-tenancy en modelo **pool**: los tenants
comparten la tabla y quedan aislados lógicamente por la partition key
`tenant_id`, que **siempre** se toma del claim `custom:tenant_id` del ID token
de Cognito (nunca del body, de la ruta ni de los query params).

## Claves e índices

| Elemento | Atributo | Ejemplo | Uso |
|---|---|---|---|
| Partition key | `tenant_id` | `empresa-beta` | Aislamiento por tenant |
| Sort key | `sk` | `SVC#000012` | Un servicio; listar todos los del tenant |
| GSI1 PK | `tenant_id` | `empresa-beta` | |
| GSI1 SK | `estado_fecha` | `activo#2024-01-19T09:00:00Z` | Listar activos (o inactivos) ordenados por fecha de creación |
| Billing | — | `PAY_PER_REQUEST` | Sin dimensionar capacidad |

El **GSI1 es disperso**: solo los ítems de servicio llevan `estado_fecha`; el
contador no entra al índice.

## Tipos de ítem en la tabla

| Ítem | `sk` | Lo escribe | Contenido |
|---|---|---|---|
| Servicio | `SVC#000001` … `SVC#010000` (+ los creados por la API) | API / seed | Datos de negocio (abajo) |
| Contador | `CONTADOR#SVC` | API (`UpdateItem ADD` atómico) / seed | `ultimo_id` (el seed lo deja en `10000`) |

## Estructura JSON del servicio

| Atributo | Tipo | Descripción |
|---|---|---|
| `tenant_id` | String (PK) | Tenant, tomado del token |
| `sk` (`servicio_id` en la API) | String (SK) | `SVC#000001` |
| `nombre` / `descripcion` | String | Qué ofrece el servicio |
| `categoria` | String | `acceso` \| `hardware` \| `software` \| `soporte` \| `otro` |
| `sla_horas` | Number | Tiempo objetivo de atención (Solicitudes lo copia al crear) |
| `requiere_aprobacion` | Boolean | Si la solicitud pasa por aprobación (Solicitudes lo copia) |
| `equipo_responsable` | String | Grupo que lo atiende |
| `costo_estimado` | Number | Costo referencial (PEN) |
| `activo` | Boolean | Disponible para solicitar (campo canónico) |
| `estado` | String | `activo` \| `inactivo` (derivado de `activo`) |
| `estado_fecha` | String (GSI1 SK) | `estado#creado_en` |
| `creado_en` / `actualizado_en` | String (ISO 8601 UTC) | Auditoría de fechas |

### Ejemplo de servicio (dato real de `itsm-catalogo-dev`)

```json
{
  "tenant_id": "empresa-beta",
  "sk": "SVC#000003",
  "nombre": "Acceso VPN con doble factor",
  "descripcion": "Alta de VPN con autenticación de doble factor",
  "categoria": "acceso",
  "sla_horas": 48,
  "requiere_aprobacion": true,
  "equipo_responsable": "Redes y Seguridad",
  "costo_estimado": 0,
  "activo": true,
  "estado": "activo",
  "estado_fecha": "activo#2024-01-10T09:00:00Z",
  "creado_en": "2024-01-10T09:00:00Z",
  "actualizado_en": "2024-01-10T09:00:00Z"
}
```

### Ejemplo de contador

```json
{ "tenant_id": "empresa-beta", "sk": "CONTADOR#SVC", "ultimo_id": 10000, "actualizado_en": "2026-11-13T00:10:00Z" }
```

## Patrones de acceso (nunca `Scan`)

| Operación | Endpoint | Índice | Expresión |
|---|---|---|---|
| Crear | `POST /catalogo` | tabla | `UpdateItem ADD ultimo_id` en `CONTADOR#SVC` + `PutItem` con `attribute_not_exists(sk)` |
| Obtener por ID | `GET /catalogo/{id}` | tabla | `GetItem(tenant_id, sk)` |
| Listar activos | `GET /catalogo` | GSI1 | `Query(tenant_id = :t AND begins_with(estado_fecha, "activo#"))`, `Limit` + `LastEvaluatedKey` |
| Listar inactivos (admin) | `GET /catalogo?estado=inactivo` | GSI1 | `begins_with(estado_fecha, "inactivo#")` |
| Listar todos (admin) | `GET /catalogo?estado=todos` | tabla | `Query(tenant_id = :t AND begins_with(sk, "SVC#"))` |
| Filtrar por categoría | `GET /catalogo?categoria=hardware` | GSI1 | Query anterior + `FilterExpression categoria = :c` |
| Actualizar / desactivar | `PUT /catalogo/{id}` | tabla | `UpdateItem` con `ConditionExpression attribute_exists(sk)` (si no existe en el tenant → 404, nunca crea) |
| Conteos por tenant | script | tabla / GSI1 | `Query` con `Select=COUNT`, sumando todas las páginas |

## Relación con otros servicios

- **Solicitudes** consulta `GET /catalogo/{servicio_id}` reenviando el ID token
  del usuario y **copia** `nombre`, `sla_horas` y `requiere_aprobacion` en la
  solicitud: si el Catálogo falla después, la solicitud sigue siendo válida.
- Las 30,000 solicitudes de `itsm-solicitudes-dev` referencian
  `SVC#000001`…`SVC#000020` de su mismo tenant.
- El Catálogo no consulta a ningún otro servicio.

## Volumen

| Tenant | Industria | Servicios |
|---|---|---|
| `empresa-alfa` | Retail | 10,000 |
| `empresa-beta` | Entidad financiera | 10,000 |
| `empresa-gamma` | Telecomunicaciones | 10,000 |
| **Total** | | **30,000** |

Generados con `scripts/seed_catalogo.py --modo completo` (`batch_write_item`
en lotes de 25, ~15 % inactivos, nombres únicos por tenant) y verificados con
`scripts/verificar_conteos.py --esperado 10000`.
