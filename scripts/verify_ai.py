import os

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT = (
    "Eres un filtro de un sistema de monitoreo de emergencias en Venezuela. "
    "Tu única tarea es responder 'SI' o 'NO' a si el texto describe una emergencia "
    "OCURRIENDO ACTUALMENTE o MUY RECIENTE (últimas horas/dias). "
    "Responde 'NO' si el texto es: un informe, análisis, estudio, estadística, "
    "aniversario, recuento histórico, o cualquier mención de una emergencia PASADA "
    "que ya no está en curso. Responde solo con la palabra SI o NO, nada más."
)


def parece_emergencia_actual(evento):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("[WARN] GROQ_API_KEY no configurada, se omite verificación de plausibilidad")
        return True

    texto = evento.get("texto_muestra", "")[:1500]

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
                    {"role": "user", "content": texto},
                ],
            },
            timeout=15,
        )
        resp.raise_for_status()
        respuesta = resp.json()["choices"][0]["message"]["content"].strip().upper()
        return respuesta.startswith("SI")
    except Exception as e:
        print(f"[WARN] Fallo la verificación con Groq, se deja pasar el evento: {e}")
        return True
