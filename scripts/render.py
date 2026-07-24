from dateutil import parser as dateparser

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
}

SEVERIDAD_EMOJI = {
    "critico": "🔴 CRÍTICO",
    "alto": "🟠 ALTO",
    "medio": "🟡 MEDIO",
    "bajo": "🟢 BAJO",
    "sin_clasificar": "⚪ SIN CLASIFICAR",
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


def _formatear_fecha(fecha_iso):
    """Convierte una fecha ISO a formato día/mes/año, hora en formato 12h a.m./p.m."""
    dt = dateparser.isoparse(fecha_iso)
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

    titulo = f"{tipo_label} en {ubicacion_detallada}"

    texto = (
        f"{estado_confirmacion} | {severidad_label}\n"
        f"📌 {titulo}\n\n"
        f"📍 Ubicación: {ubicacion_detallada}\n"
        f"🕒 Hecho reportado: {_formatear_fecha(evento['fecha_evento'])}\n"
        f"🔎 Detectado por el sistema: {_formatear_fecha(evento['fecha_deteccion'])}\n"
        f"📊 Fuentes independientes: {evento['num_fuentes']} (score {evento['score']})\n\n"
        f"ℹ️ {estado_confirmacion}: {confirmacion_explicacion}\n"
        f"ℹ️ {severidad_label}: {severidad_explicacion}\n\n"
        f"Fuentes:\n{fuentes_texto}"
    )

    return {
        "titulo": titulo,
        "texto": texto,
        **evento,
    }
