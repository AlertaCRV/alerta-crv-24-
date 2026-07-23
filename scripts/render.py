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


def redactar_noticia(evento):
    tipo_label = TIPO_LABELS.get(evento["tipo"], evento["tipo"].capitalize())
    severidad_label = SEVERIDAD_EMOJI.get(evento["severidad"], evento["severidad"])
    estado_confirmacion = "✅ CONFIRMADO" if evento["confirmado"] else "⚠️ SIN CONFIRMAR"

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
        f"🕒 Hecho reportado: {evento['fecha_evento']}\n"
        f"🔎 Detectado por el sistema: {evento['fecha_deteccion']}\n"
        f"📊 Fuentes independientes: {evento['num_fuentes']} (score {evento['score']})\n\n"
        f"Fuentes:\n{fuentes_texto}"
    )

    return {
        "titulo": titulo,
        "texto": texto,
        **evento,
    }
