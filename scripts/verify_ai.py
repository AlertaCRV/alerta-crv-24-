import os

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT = (
    "Eres un filtro de un sistema de monitoreo de emergencias en Venezuela. "
    "Tu única tarea es responder 'SI' o 'NO' a si el texto describe un EVENTO EMERGENTE "
    "(una situación aguda que está ocurriendo AHORA o en las últimas horas). "
    "\n\nResponde 'NO' en estos casos:\n"
    "• Reportajes/denuncias sobre problemas crónicos (e.g., 'los apagones tienen en jaque a los comerciantes')\n"
    "• Análisis de impacto comercial o socioeconómico de una crisis pasada\n"
    "• Asuntos organizacionales o administrativos (e.g., 'personal dejó la institución')\n"
    "• Retrospectivas, estudios, estadísticas o menciones de emergencias históricas\n"
    "• Cualquier texto que describe problemas durables, no un evento súbito/agudo\n"
    "\nResponde 'SI' solo si el texto reporta:\n"
    "• Un evento que está sucediendo AHORA o en horas recientes (últimas 24h)\n"
    "• Algo que requiere respuesta inmediata de emergencias\n"
    "\nResponde solo con 'SI' o 'NO', nada más."
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
        resultado = respuesta.startswith("SI")
        print(f"[DEBUG] Groq verificación: '{respuesta[:30]}...' → {resultado}")
        return resultado
    except Exception as e:
        print(f"[WARN] Fallo la verificación con Groq, se deja pasar el evento: {e}")
        return True
