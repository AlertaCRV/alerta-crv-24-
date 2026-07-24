import os
from datetime import datetime, timezone

import requests
from dateutil import parser as dateparser

from config_loader import load_settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT_TEMPLATE = (
    "Eres un analista de un sistema de monitoreo de emergencias en Venezuela. "
    "Se te da la FECHA ACTUAL del sistema, un TIPO de emergencia que un "
    "clasificador automático le asignó a un grupo de reportes, y una lista "
    "numerada de fuentes periodísticas independientes sobre ese grupo. Tu "
    "tarea es clasificar CADA fuente por separado: para cada una, responde "
    "'SI' si esa fuente específica describe, como tema PRINCIPAL, un EVENTO "
    "EMERGENTE del tipo indicado que está ocurriendo AHORA o en las últimas "
    "24 horas contadas desde la fecha actual del sistema; responde 'NO' en "
    "caso contrario.\n"
    "\nUsa la fecha actual del sistema para evaluar expresiones temporales "
    "relativas de forma absoluta, no solo por el tono del texto (e.g., 'a un "
    "mes de la tragedia', 'al cumplirse 30 días', 'un mes después', 'la "
    "semana pasada').\n"
    "\nResponde 'NO' para una fuente si:\n"
    "• Es una retrospectiva, aniversario, homenaje, o cobertura semanas/meses "
    "después del evento original\n"
    "• No describe realmente un evento del tipo indicado, aunque lo mencione "
    "de pasada (e.g., tipo=sismo pero el texto es sobre un robo a víctimas de "
    "un sismo pasado, una nota policial, política o social que solo hace "
    "referencia a una emergencia anterior)\n"
    "• Si tipo=vialidad: es un accidente de tránsito individual y rutinario "
    "(un choque entre 1-2 vehículos, un motorizado herido, un volcamiento "
    "aislado) sin víctimas múltiples ni colapso de una vía completa — son "
    "casos que atiende tránsito/ambulancia local, no algo que requiera "
    "respuesta de la Cruz Roja\n"
    "• Es un reportaje/denuncia sobre un problema crónico (e.g., 'los "
    "apagones tienen en jaque a los comerciantes'), un análisis de impacto "
    "comercial o socioeconómico de una crisis pasada, o un asunto "
    "organizacional/administrativo (e.g., 'personal dejó la institución')\n"
    "• Describe un problema durable, no un evento súbito/agudo\n"
    "\nResponde 'SI' para una fuente solo si reporta, como tema principal, un "
    "evento del tipo indicado sucediendo ahora o en horas recientes, que "
    "requiere respuesta inmediata de emergencias (si tipo=vialidad, solo "
    "cuando hay colapso de una vía completa, un accidente masivo con "
    "múltiples heridos o fallecidos, o afectación significativa de "
    "infraestructura vial).\n"
    "\nFECHA ACTUAL DEL SISTEMA: {fecha_actual}\n"
    "\nFORMATO DE SALIDA OBLIGATORIO: responde únicamente una lista de "
    "exactamente {n} valores 'SI' o 'NO' separados por comas, en el mismo "
    "orden en que se dan las fuentes. No incluyas números, explicaciones, "
    "preámbulos ni ningún otro texto.\n"
    "Ejemplo con 3 fuentes: SI, NO, SI"
)


def _construir_prompt_fuentes(grupos_fuentes):
    bloques = []
    for i, grupo in enumerate(grupos_fuentes, start=1):
        representante = max(grupo, key=lambda m: m["peso"])
        bloques.append(
            f"--- Fuente {i} ({representante['fuente_nombre']}) ---\n"
            f"{representante['texto'][:500]}"
        )
    return "\n\n".join(bloques)[:6000]


def _parsear_veredictos(respuesta, n):
    valores = [v.strip().upper() for v in respuesta.split(",")]
    valores = [v for v in valores if v in ("SI", "NO")]
    if len(valores) != n:
        return None
    return valores


def _finalizar_evento(evento, grupos_aprobados):
    settings = load_settings()["verificacion"]
    umbral = settings["umbral_confirmado"]

    representantes = sorted(
        (max(g, key=lambda m: m["peso"]) for g in grupos_aprobados),
        key=lambda m: m["peso"], reverse=True,
    )
    miembros_aprobados = [m for g in grupos_aprobados for m in g]

    score = sum(r["peso"] for r in representantes)
    severidades = [m["severidad"] for m in miembros_aprobados if m["severidad"] != "sin_clasificar"]
    orden_severidad = ["critico", "alto", "medio", "bajo"]
    severidad_final = next((s for s in orden_severidad if s in severidades), "sin_clasificar")
    fecha_mas_reciente = max(miembros_aprobados, key=lambda m: dateparser.isoparse(m["fecha"]))["fecha"]

    return {
        "tipo": evento["tipo"],
        "ubicacion": evento["ubicacion"],
        "municipio": evento["municipio"],
        "parroquia": evento["parroquia"],
        "severidad": severidad_final,
        "score": round(score, 2),
        "confirmado": score >= umbral,
        "num_fuentes": len(representantes),
        "fuentes": [
            {"nombre": m["fuente_nombre"], "link": m["link"], "fecha": m["fecha"]}
            for m in miembros_aprobados
        ],
        "fecha_evento": fecha_mas_reciente,
        "fecha_deteccion": datetime.now(timezone.utc).isoformat(),
    }


def verificar_evento_con_ia(evento):
    """Clasifica con IA cada fuente independiente del evento por separado
    (no un veredicto agregado unico), y recalcula score/severidad/confirmado
    usando solo las fuentes que la IA considero vigentes. Devuelve el evento
    final listo para publicar, o None si ninguna fuente fue aprobada.

    Publicar (evento no-None) solo requiere que AL MENOS UNA fuente sea
    aprobada -- igual que el criterio de publicacion anterior a este cambio.
    El umbral de score (`confirmado`) sigue siendo un criterio aparte, usado
    unicamente para la etiqueta CONFIRMADO/SIN CONFIRMAR, no para decidir si
    se publica."""
    api_key = os.environ.get("GROQ_API_KEY")
    grupos_fuentes = evento["grupos_fuentes"]
    n = len(grupos_fuentes)

    if not api_key:
        print("[WARN] GROQ_API_KEY no configurada, se omite verificación de plausibilidad")
        return _finalizar_evento(evento, grupos_fuentes)

    fecha_actual = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(fecha_actual=fecha_actual, n=n)
    contenido_usuario = (
        f"TIPO ASIGNADO POR EL CLASIFICADOR: {evento['tipo']}\n\n"
        f"{_construir_prompt_fuentes(grupos_fuentes)}"
    )

    try:
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": GROQ_MODEL,
                "temperature": 0,
                "max_tokens": max(10, n * 4 + 5),
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": contenido_usuario},
                ],
            },
            timeout=20,
        )
        resp.raise_for_status()
        respuesta = resp.json()["choices"][0]["message"]["content"].strip()
        veredictos = _parsear_veredictos(respuesta, n)

        if veredictos is None:
            print(
                f"[WARN] Groq devolvió una lista de veredictos inválida o de "
                f"tamaño distinto al esperado ({n} fuentes): '{respuesta[:200]}'. "
                f"Se deja pasar el evento por seguridad."
            )
            return _finalizar_evento(evento, grupos_fuentes)

        representantes = [max(g, key=lambda m: m["peso"]) for g in grupos_fuentes]
        detalle = ", ".join(
            f"{r['fuente_nombre']}={v}" for r, v in zip(representantes, veredictos)
        )
        grupos_aprobados = [g for g, v in zip(grupos_fuentes, veredictos) if v == "SI"]
        print(
            f"[DEBUG] Groq verificación [{evento['tipo']}/{evento['ubicacion']}]: "
            f"{detalle} → {len(grupos_aprobados)}/{n} fuentes aprobadas"
        )

        if not grupos_aprobados:
            return None

        return _finalizar_evento(evento, grupos_aprobados)

    except Exception as e:
        print(f"[WARN] Fallo la verificación con Groq, se deja pasar el evento: {e}")
        return _finalizar_evento(evento, grupos_fuentes)
