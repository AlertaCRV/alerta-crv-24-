from zoneinfo import ZoneInfo

from dateutil import parser as dateparser

ZONA_VENEZUELA = ZoneInfo("America/Caracas")

TIPO_LABELS = {
    "sismo": "Sismo",
    "incendio": "Incendio",
    "inundacion": "Inundación",
    "deslizamiento": "Deslizamiento/Derrumbe",
    "infraestructura_electrica": "Falla eléctrica",
    "infraestructura_agua": "Falla de agua",
    "vialidad": "Incidente vial",
    "orden_publico": "Orden público",
    "salud_publica": "Salud pública",
    "tsunami": "Tsunami",
    "tormenta_electrica": "Tormenta eléctrica",
    "derrame_petrolero": "Derrame petrolero",
    "explosion": "Explosión",
    "sequia": "Sequía",
    "colapso_estructural": "Colapso estructural",
    "crisis_migratoria": "Crisis migratoria",
    "escasez_combustible": "Escasez de combustible",
    "motin_carcelario": "Motín carcelario",
    "accidente_transporte": "Accidente de transporte",
    "ataque_armado": "Ataque armado",
    "emergencia_metro": "Emergencia en el Metro/Metrocable/Teleférico",
}

SEVERIDAD_EMOJI = {
    "critico": "🔴 SEVERIDAD CRÍTICA",
    "alto": "🟠 SEVERIDAD ALTA",
    "medio": "🟡 SEVERIDAD MEDIA",
    "bajo": "🟢 SEVERIDAD BAJA",
    "sin_clasificar": "⚪ SEVERIDAD SIN CLASIFICAR",
}

SEVERIDAD_EXPLICACION = {
    "critico": "Se reportan víctimas fatales o una emergencia de gran magnitud.",
    "alto": "Se reportan heridos, evacuaciones, o daños severos.",
    "medio": "Se reportan daños materiales, sin heridos mencionados.",
    "bajo": "Situación de precaución, sin daños significativos reportados.",
    "sin_clasificar": "El texto de las fuentes no menciona detalles suficientes para determinar la gravedad.",
}

CONFIRMACION_EXPLICACION = {
    True: "Corroborado por 2 o más fuentes independientes (o una fuente oficial de alta confiabilidad).",
    False: "Reportado hasta ahora por una sola fuente; aún no alcanza el nivel de corroboración cruzada del sistema.",
}

# Titulo fijo para reportes de filiales:
# a diferencia de una alerta armada a partir de un titular de prensa, aqui
# el "titular" real es el proposito administrativo del reporte de la
# filial, no el tipo de emergencia detectado -- para crisis_migratoria eso
# es siempre "reporte de personas desplazadas", nunca un titulo genérico
# tipo "Crisis migratoria en X".
REPORTE_FILIAL_TITULOS = {
    "crisis_migratoria": "Reporte de personas desplazadas",
}


def _formatear_fecha(fecha_iso):
    """Convierte una fecha ISO (guardada internamente en UTC) a hora local
    de Venezuela, en formato día/mes/año, hora en formato 12h a.m./p.m."""
    dt = dateparser.isoparse(fecha_iso).astimezone(ZONA_VENEZUELA)
    fecha_str = dt.strftime("%d/%m/%Y")
    hora_str = dt.strftime("%I:%M %p").lstrip("0").replace("AM", "a.m.").replace("PM", "p.m.")
    return f"{fecha_str}, {hora_str}"


def redactar_noticia(evento):
    """Genera el texto final de la noticia a partir de un evento verificado, usando plantillas fijas."""
    tipo_label = TIPO_LABELS.get(evento["tipo"], evento["tipo"].capitalize())
    severidad_label = SEVERIDAD_EMOJI.get(evento["severidad"], evento["severidad"])
    severidad_explicacion = SEVERIDAD_EXPLICACION.get(evento["severidad"], "")
    estado_confirmacion = "✅ CONFIRMADO" if evento["confirmado"] else "⚠️ SIN CONFIRMAR"
    confirmacion_explicacion = CONFIRMACION_EXPLICACION[evento["confirmado"]]

    fuentes_texto = "\n".join(
        f"  • {f['nombre']}: {f['link']}" for f in evento["fuentes"]
    )

    partes_ubicacion = [evento["ubicacion"]]
    if evento.get("municipio"):
        partes_ubicacion.insert(0, f"Municipio {evento['municipio']}")
    if evento.get("parroquia"):
        partes_ubicacion.insert(0, f"Parroquia {evento['parroquia']}")
    ubicacion_detallada = ", ".join(partes_ubicacion)

    es_reporte_filial = bool(evento.get("es_reporte_filial"))
    if es_reporte_filial:
        titulo = REPORTE_FILIAL_TITULOS.get(evento["tipo"], f"{tipo_label} en {ubicacion_detallada}")
    else:
        titulo = f"{tipo_label} en {ubicacion_detallada}"

    nota_falla_tecnica = ""
    if evento.get("estado_verificacion") == "PASADO_POR_FALLA_TECNICA":
        nota_falla_tecnica = (
            "ℹ️ ⚙️ Este evento se publicó sin verificación de IA por una "
            "falla técnica temporal (ej. límite de la API). Verificar con "
            "mayor cautela.\n"
        )

    # Los reportes de filiales no tienen un enlace publico util (el "link"
    # depende del canal de captura del reporte, ej. una busqueda privada),
    # pero si traen cifras consolidadas ya
    # verificadas por el propio criterio de seguridad de datos -- se
    # muestran directamente en la tarjeta en vez de la lista de fuentes con
    # enlaces, que aqui nadie mas puede abrir.
    distintivo_filial = "🏢 REPORTE DE FILIAL\n\n" if es_reporte_filial else ""
    if es_reporte_filial and evento.get("resumen_consolidado"):
        bloque_fuentes = f"📋 Resumen consolidado:\n{evento['resumen_consolidado']}"
    else:
        bloque_fuentes = f"Fuentes:\n{fuentes_texto}"

    texto = (
        f"{distintivo_filial}"
        f"📌 {titulo}\n\n"
        f"{estado_confirmacion} | {severidad_label}\n\n"
        f"📍 Ubicación: {ubicacion_detallada}\n"
        f"🕒 Hecho reportado: {_formatear_fecha(evento['fecha_evento'])}\n"
        f"🔎 Detectado por el sistema: {_formatear_fecha(evento['fecha_deteccion'])}\n"
        f"📊 Fuentes independientes: {evento['num_fuentes']} (score {evento['score']})\n\n"
        f"ℹ️ {estado_confirmacion}: {confirmacion_explicacion}\n"
        f"ℹ️ {severidad_label}: {severidad_explicacion}\n"
        f"{nota_falla_tecnica}\n"
        f"{bloque_fuentes}"
    )

    # El orden importa: si `evento` ya trae sus propias claves "titulo"/
    # "texto" (el caso al reusar esta funcion para regenerar el texto de una
    # alerta YA publicada tras una correccion retroactiva, en vez de una
    # alerta nueva sin redactar todavia), un **evento puesto despues de esas
    # claves las sobreescribiria de vuelta con el texto viejo -- silencioso,
    # sin error, dejando la correccion sin efecto en el texto visible pese a
    # que los datos subyacentes (severidad/ubicacion/etc.) si se corrigieron.
    return {
        **evento,
        "titulo": titulo,
        "texto": texto,
    }
