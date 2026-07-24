import os

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT = (
    "Eres un filtro de un sistema de monitoreo de emergencias en Venezuela. "
    "Se te da un TIPO de emergencia que un clasificador automático le asignó a un grupo "
    "de reportes, y los textos de UNA O VARIAS fuentes independientes que el sistema "
    "agrupó por describir el mismo evento. Tu única tarea es responder 'SI' o 'NO' a si, "
    "en conjunto, esas fuentes describen, como tema PRINCIPAL, un EVENTO EMERGENTE de ESE "
    "tipo específico (una situación aguda de ese tipo que está ocurriendo AHORA o en las "
    "últimas horas).\n"
    "\nResponde 'NO' si CUALQUIERA de las fuentes indica que se trata de:\n"
    "• Una retrospectiva, aniversario, o cobertura semanas/meses después del evento "
    "original (e.g., 'a un mes de la tragedia', 'al cumplirse 30 días', 'un mes después', "
    "'meses después del devastador...') — aunque otra de las fuentes esté redactada de "
    "forma ambigua o parezca describir algo reciente\n"
    "• El texto NO describe realmente un evento del tipo indicado, aunque lo mencione de "
    "pasada (e.g., tipo=sismo pero el texto es sobre un robo a víctimas de un sismo pasado, "
    "una nota policial, política o social que solo hace referencia a una emergencia anterior)\n"
    "• Si tipo=vialidad: un accidente de tránsito individual y rutinario (un choque entre 1-2 "
    "vehículos, un motorizado herido, un volcamiento aislado) sin víctimas múltiples ni "
    "colapso de una vía completa — son casos que atiende tránsito/ambulancia local, no algo "
    "que requiera respuesta de la Cruz Roja\n"
    "• Reportajes/denuncias sobre problemas crónicos (e.g., 'los apagones tienen en jaque a los comerciantes')\n"
    "• Análisis de impacto comercial o socioeconómico de una crisis pasada\n"
    "• Asuntos organizacionales o administrativos (e.g., 'personal dejó la institución')\n"
    "• Retrospectivas, estudios, estadísticas, homenajes o menciones de emergencias históricas\n"
    "• Cualquier texto que describe problemas durables, no un evento súbito/agudo\n"
    "\nResponde 'SI' solo si TODAS o la gran mayoría de las fuentes reportan, como tema "
    "principal:\n"
    "• Un evento del tipo indicado que está sucediendo AHORA o en horas recientes (últimas 24h)\n"
    "• Algo que requiere respuesta inmediata de emergencias\n"
    "• Si tipo=vialidad: solo cuando hay colapso de una vía completa, un accidente masivo con "
    "múltiples heridos o fallecidos, o afectación significativa de infraestructura vial\n"
    "\nResponde solo con 'SI' o 'NO', nada más."
)


def parece_emergencia_actual(evento):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("[WARN] GROQ_API_KEY no configurada, se omite verificación de plausibilidad")
        return True

    textos_fuentes = evento.get("textos_fuentes") or [
        {"fuente": None, "texto": evento.get("texto_muestra", "")}
    ]
    bloque_fuentes = "\n\n".join(
        f"--- Fuente: {t['fuente'] or 'desconocida'} ---\n{t['texto']}"
        for t in textos_fuentes
    )[:4000]
    contenido_usuario = (
        f"TIPO ASIGNADO POR EL CLASIFICADOR: {evento.get('tipo')}\n\n{bloque_fuentes}"
    )

    try:
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": GROQ_MODEL,
                "temperature": 0,
                "max_tokens": 5,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": contenido_usuario},
                ],
            },
            timeout=15,
        )
        resp.raise_for_status()
        respuesta = resp.json()["choices"][0]["message"]["content"].strip().upper()
        resultado = respuesta.startswith("SI")
        resumen_texto = textos_fuentes[0]["texto"][:150].replace("\n", " ")
        print(
            f"[DEBUG] Groq verificación [{evento.get('tipo')}/{evento.get('ubicacion')}] "
            f"({len(textos_fuentes)} fuente(s)): primera='{resumen_texto}...' "
            f"→ respuesta='{respuesta[:10]}' → {resultado}"
        )
        return resultado
    except Exception as e:
        print(f"[WARN] Fallo la verificación con Groq, se deja pasar el evento: {e}")
        return True
