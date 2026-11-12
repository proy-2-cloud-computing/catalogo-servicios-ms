"""Datos del catalogo ficticio por tenant (coherentes con la industria).

empresa-alfa  -> retail
empresa-beta  -> entidad financiera
empresa-gamma -> operador de telecomunicaciones

Los 20 primeros servicios (SVC#000001..SVC#000020) son los que ya referencian
las 30,000 solicitudes cargadas en itsm-solicitudes-dev. Por eso respetan su
patron de SLA y aprobacion:
    sla_horas           = [8, 24, 48, 72][(n - 1) % 4]
    requiere_aprobacion = n % 3 == 0
"""

SLA_PATRON = (8, 24, 48, 72)


def sla_base(numero):
    return SLA_PATRON[(numero - 1) % 4]


def aprobacion_base(numero):
    return numero % 3 == 0


# (nombre, descripcion, categoria, equipo_responsable, costo_estimado)
# El orden define el numero: el primero es SVC#000001.
BASE = {
    "empresa-alfa": [
        ("Restablecimiento de contraseña", "Reinicio de contraseña de red y correo corporativo", "acceso", "Mesa de Ayuda", 0),
        ("Instalación de software estándar", "Instalación de aplicaciones de la imagen corporativa", "software", "Soporte en Sitio", 0),
        ("Acceso VPN para personal remoto", "Alta de acceso remoto por VPN para personal de oficina central", "acceso", "Redes", 0),
        ("Reemplazo de terminal POS", "Cambio de terminal punto de venta dañado en tienda", "hardware", "Soporte Tiendas", 850),
        ("Soporte de caja registradora", "Atención de fallas en caja y software POS", "soporte", "Soporte Tiendas", 0),
        ("Alta de usuario en ERP de inventario", "Creacion de usuario y perfil en el ERP de inventario", "acceso", "Aplicaciones", 0),
        ("Configuración de lector de códigos", "Instalación y configuración de lector de códigos de barras", "hardware", "Soporte Tiendas", 120),
        ("Equipo portátil para gerente de tienda", "Asignacion de laptop con perfil de gerente", "hardware", "Soporte en Sitio", 3200),
        ("Acceso al panel de ventas e-commerce", "Permisos sobre el panel administrativo de la tienda online", "acceso", "Comercio Digital", 0),
        ("Configuración de impresora de etiquetas", "Instalación de impresora de etiquetas de precios", "hardware", "Soporte Tiendas", 0),
        ("Instalación de software de planogramas", "Instalación de la herramienta de diseño de planogramas", "software", "Aplicaciones", 450),
        ("Licencia de herramienta de BI", "Asignacion de licencia del tablero de inteligencia comercial", "software", "Analítica", 1800),
        ("Desbloqueo de cuenta de correo", "Desbloqueo de cuenta por intentos fallidos", "acceso", "Mesa de Ayuda", 0),
        ("Soporte de red Wi-Fi en tienda", "Diagnóstico de cobertura y caídas de Wi-Fi en tienda", "soporte", "Redes", 0),
        ("Acceso a carpeta compartida de finanzas", "Permisos de lectura o escritura sobre la carpeta de finanzas", "acceso", "Seguridad TI", 0),
        ("Instalación de cámaras de videovigilancia", "Instalación de cámaras IP en tienda o almacén", "hardware", "Seguridad Física", 2500),
        ("Soporte de app móvil de inventario", "Atención de errores en la app de conteo de inventario", "soporte", "Aplicaciones", 0),
        ("Habilitación en portal de proveedores", "Alta de usuario en el portal de proveedores", "acceso", "Comercio Digital", 0),
        ("Migración de buzón de correo", "Traslado de buzón y archivos de correo a la nueva plataforma", "software", "Mesa de Ayuda", 0),
        ("Evaluación de nueva herramienta para tiendas", "Análisis de viabilidad de una herramienta propuesta por negocio", "otro", "Arquitectura TI", 0),
    ],
    "empresa-beta": [
        ("Restablecimiento de contraseña", "Reinicio de contraseña de dominio y correo", "acceso", "Mesa de Ayuda", 0),
        ("Instalación de software ofimático", "Instalación de la suite ofimática corporativa", "software", "Soporte en Sitio", 0),
        ("Acceso VPN con doble factor", "Alta de VPN con autenticación de doble factor", "acceso", "Redes y Seguridad", 0),
        ("Reemplazo de estación de trabajo", "Cambio de PC de escritorio por falla o renovación", "hardware", "Soporte en Sitio", 2800),
        ("Soporte de token de seguridad", "Sincronización o reposición de token físico o digital", "soporte", "Seguridad TI", 0),
        ("Alta de usuario en core bancario", "Creacion de usuario y perfil transaccional en el core", "acceso", "Aplicaciones Core", 0),
        ("Configuración de impresora de cheques", "Instalación y calibración de impresora de cheques", "hardware", "Operaciones", 0),
        ("Equipo portátil cifrado para analista", "Laptop con disco cifrado y perfil de analista", "hardware", "Soporte en Sitio", 3500),
        ("Acceso a sistema antifraude", "Permisos sobre la consola de prevención de fraude", "acceso", "Riesgos TI", 0),
        ("Soporte de banca por internet", "Atención de incidencias en el canal de banca web", "soporte", "Canales Digitales", 0),
        ("Instalación de software de análisis financiero", "Instalación de herramienta de modelos y análisis financiero", "software", "Aplicaciones", 1200),
        ("Licencia de herramienta de cumplimiento", "Licencia de la herramienta de cumplimiento normativo", "software", "Cumplimiento", 2400),
        ("Desbloqueo de cuenta de dominio", "Desbloqueo de cuenta por intentos fallidos", "acceso", "Mesa de Ayuda", 0),
        ("Soporte de cajero automático", "Atención de fallas de software en cajeros automáticos", "soporte", "Operaciones ATM", 0),
        ("Acceso a reportes regulatorios", "Permisos sobre los reportes enviados al regulador", "acceso", "Cumplimiento", 0),
        ("Instalación de lector biométrico", "Instalación de lector de huella para validación en agencia", "hardware", "Seguridad TI", 600),
        ("Soporte de correo cifrado", "Configuración de certificados para correo cifrado", "soporte", "Mesa de Ayuda", 0),
        ("Habilitación de firma digital", "Emisión y configuración de certificado de firma digital", "acceso", "Seguridad TI", 150),
        ("Restauración de archivos desde respaldo", "Recuperación de archivos borrados desde el respaldo diario", "soporte", "Infraestructura", 0),
        ("Revisión de seguridad de proveedor", "Evaluación de riesgos de un proveedor tecnológico", "otro", "Seguridad TI", 0),
    ],
    "empresa-gamma": [
        ("Restablecimiento de contraseña", "Reinicio de contraseña de red y correo", "acceso", "Mesa de Ayuda", 0),
        ("Instalación de software corporativo", "Instalación de aplicaciones de la imagen corporativa", "software", "Soporte en Sitio", 0),
        ("Acceso VPN a red de gestión", "Alta de VPN hacia la red de gestión de equipos", "acceso", "Redes", 0),
        ("Reemplazo de router de oficina", "Cambio de router en sede administrativa", "hardware", "Redes", 900),
        ("Soporte de CRM de atención al cliente", "Atención de errores en la plataforma CRM", "soporte", "Aplicaciones BSS", 0),
        ("Alta de usuario en sistema de facturación", "Creacion de usuario en el sistema de facturación (BSS)", "acceso", "Aplicaciones BSS", 0),
        ("Configuración de teléfono IP", "Instalación y registro de teléfono IP", "hardware", "Telefonía", 250),
        ("Equipo portátil para técnico de campo", "Laptop robusta con herramientas de diagnostico", "hardware", "Soporte en Sitio", 3000),
        ("Acceso a consola de monitoreo NOC", "Permisos sobre la consola de monitoreo del NOC", "acceso", "NOC", 0),
        ("Soporte de línea móvil corporativa", "Activación, cambio de chip o bloqueo de línea corporativa", "soporte", "Telefonía Móvil", 0),
        ("Instalación de software de planificación de red", "Instalación de herramienta de planificación de cobertura", "software", "Ingeniería de Red", 1500),
        ("Licencia de herramienta OSS de inventario", "Licencia de la herramienta de inventario de red (OSS)", "software", "Ingeniería de Red", 2600),
        ("Desbloqueo de cuenta de correo", "Desbloqueo de cuenta por intentos fallidos", "acceso", "Mesa de Ayuda", 0),
        ("Soporte de enlace de fibra de sede", "Diagnóstico de caídas del enlace de fibra de una sede", "soporte", "NOC", 0),
        ("Acceso a registros de llamadas (CDR)", "Permisos de consulta sobre registros de llamadas", "acceso", "Seguridad TI", 0),
        ("Instalación de equipo de radioenlace", "Instalación de radioenlace punto a punto", "hardware", "Ingeniería de Red", 4800),
        ("Soporte de app de técnicos en campo", "Atención de errores en la app de órdenes de trabajo", "soporte", "Aplicaciones OSS", 0),
        ("Habilitación en portal mayorista", "Alta de usuario en el portal de clientes mayoristas", "acceso", "Ventas Corporativas", 0),
        ("Migración de buzón de voz", "Traslado de buzón de voz a la nueva central", "software", "Telefonía", 0),
        ("Evaluación de solución IoT", "Análisis de viabilidad de una solución IoT propuesta", "otro", "Arquitectura TI", 0),
    ],
}

# Plantillas adicionales para la carga completa (10,000 por tenant).
# (nombre, categoria, equipo_responsable, costo_base, sla_horas, requiere_aprobacion)
EXTRA = {
    "empresa-alfa": [
        ("Alta de cajero en sistema POS", "acceso", "Soporte Tiendas", 0, 8, False),
        ("Reparación de balanza electrónica", "hardware", "Soporte Tiendas", 300, 48, False),
        ("Actualización de precios en POS", "software", "Aplicaciones", 0, 8, False),
        ("Soporte de pasarela de pagos", "soporte", "Comercio Digital", 0, 8, False),
        ("Acceso a sistema de recursos humanos", "acceso", "Aplicaciones", 0, 24, True),
        ("Instalación de pantalla de señalización digital", "hardware", "Soporte Tiendas", 1400, 72, False),
        ("Soporte de sistema de almacén (WMS)", "soporte", "Logística TI", 0, 24, False),
        ("Configuración de terminal de mano", "hardware", "Logística TI", 650, 48, False),
    ],
    "empresa-beta": [
        ("Alta de usuario en banca empresas", "acceso", "Canales Digitales", 0, 24, True),
        ("Soporte de app de banca móvil", "soporte", "Canales Digitales", 0, 8, False),
        ("Reposición de tarjeta de acceso", "hardware", "Seguridad Física", 40, 24, False),
        ("Acceso a datawarehouse de riesgos", "acceso", "Riesgos TI", 0, 48, True),
        ("Instalación de software de tesorería", "software", "Aplicaciones", 900, 48, True),
        ("Soporte de plataforma de pagos SWIFT", "soporte", "Operaciones", 0, 8, False),
        ("Instalación de contador de billetes", "hardware", "Operaciones", 1100, 72, False),
        ("Configuración de escritorio virtual", "software", "Infraestructura", 0, 24, False),
    ],
    "empresa-gamma": [
        ("Alta de usuario en sistema de aprovisionamiento", "acceso", "Aplicaciones OSS", 0, 24, True),
        ("Soporte de portabilidad numérica", "soporte", "Aplicaciones BSS", 0, 8, False),
        ("Reemplazo de módem de prueba", "hardware", "Soporte en Sitio", 180, 48, False),
        ("Acceso a sistema de gestión de red", "acceso", "NOC", 0, 48, True),
        ("Instalación de analizador de espectro", "software", "Ingeniería de Red", 2200, 72, True),
        ("Soporte de central telefónica", "soporte", "Telefonía", 0, 8, False),
        ("Configuración de equipo de medición de fibra", "hardware", "Ingeniería de Red", 1600, 72, False),
        ("Soporte de portal de autogestión", "soporte", "Canales Digitales", 0, 24, False),
    ],
}

# Sedes, tiendas o areas por tenant (variante del nombre).
SEDES = {
    "empresa-alfa": [
        "Tienda Miraflores", "Tienda San Isidro", "Tienda Surco", "Tienda La Molina", "Tienda Los Olivos",
        "Tienda Callao", "Tienda Arequipa Centro", "Tienda Trujillo", "Tienda Chiclayo", "Tienda Piura",
        "Tienda Cusco", "Tienda Ica", "Tienda Huancayo", "Centro de Distribución Lurín", "Almacén Ate",
        "Oficina Central", "Área Comercial", "Área de Marketing", "Área de Logística", "Área de Finanzas",
        "Tienda Tacna", "Tienda Cajamarca",
    ],
    "empresa-beta": [
        "Agencia Miraflores", "Agencia San Isidro", "Agencia Surco", "Agencia San Borja", "Agencia Jesús María",
        "Agencia Arequipa", "Agencia Trujillo", "Agencia Chiclayo", "Agencia Piura", "Agencia Cusco",
        "Sede Principal", "Área de Riesgos", "Área de Tesorería", "Área de Créditos", "Área de Cumplimiento",
        "Área de Operaciones", "Banca Empresas", "Banca Personas", "Centro de Contacto", "Auditoría Interna",
        "Agencia Tacna", "Agencia Huancayo",
    ],
    "empresa-gamma": [
        "Sede Central", "NOC Lima", "NOC Arequipa", "Nodo Trujillo", "Nodo Chiclayo",
        "Nodo Piura", "Nodo Cusco", "Nodo Huancayo", "Centro de Datos Surquillo", "Tienda Jockey Plaza",
        "Tienda Mega Plaza", "Tienda Arequipa", "Área de Ingeniería", "Área Comercial", "Área de Facturacion",
        "Atención al Cliente", "Operaciones de Campo", "Ventas Corporativas", "Mayoristas", "Regulatorio",
        "Nodo Tacna", "Nodo Iquitos",
    ],
}

# Modalidad: (sufijo, factor_sla, fuerza_aprobacion)
MODALIDADES = [
    ("", 1.0, None),
    ("Estándar", 1.0, None),
    ("Urgente", 0.5, None),
    ("Masivo", 2.0, True),
    ("Nuevo ingreso", 1.0, None),
    ("Temporal", 1.0, True),
    ("Fuera de horario", 1.0, None),
    ("Nivel 2", 1.5, None),
    ("Gerencia", 0.5, True),
    ("Contratistas", 1.0, True),
    ("Renovación", 1.5, None),
    ("Baja", 1.0, None),
    ("Cambio", 1.0, None),
    ("Prioritario", 0.5, None),
    ("Programado", 2.0, None),
    ("Remoto", 1.0, None),
    ("Presencial", 1.0, None),
    ("Auditoría", 1.0, True),
]

SLA_PERMITIDOS = (4, 8, 12, 24, 48, 72, 96, 120, 168)

TENANTS = tuple(BASE)
