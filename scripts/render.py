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
    """Genera el texto final de la noticia a partir de un evento verificado, usando plantillas fijas."""
    tipo_label = TIPO_LABELS.get(evento["tipo"], evento["tipo"].capitalize())
    severidad_label = SEVERIDAD_EMOJI.get(evento["severidad"], evento["severidad"])
    estado_confirmacion = "✅ CONFIRMADO" if evento["confirmado"] else "⚠️ SIN CONFIRMAR"

    fuentes_texto = "\n".join(
        f"  • {f['nombre']}: {f['link']}" for f in evento["fuentes"]
    )

    titulo = f"{tipo_label} en {evento['ubicacion']}"

    texto = (
        f"{estado_confirmacion} | {severidad_label}\n"
        f"📌 {titulo}\n\n"
        f"📍 Ubicación: {evento['ubicacion']}\n"
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
