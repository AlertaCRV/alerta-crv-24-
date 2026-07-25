import json
import os
import re
import time
import unicodedata
from datetime import datetime, timezone

import requests
from dateutil import parser as dateparser

from config_loader import load_settings, load_estados
from verify import extraer_magnitud

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

# Filtro determinista de respaldo: si el texto de una fuente contiene una
# marca temporal explícita de retrospectiva/aniversario, se descarta sin
# depender del juicio del modelo (que en la practica ha fallado en casos
# como "a un mes del terremoto en Vargas...").
_NUMEROS = r"(un|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|\d+)"
_PATRON_RETROSPECTIVA = re.compile(
    rf"\b(a|al cumplirse)\s+{_NUMEROS}\s+"
    r"(dia|dias|semana|semanas|mes|meses|ano|anos)\s+(del|de|despues)\b"
    r"|\baniversario\b"
    rf"|\b{_NUMEROS}\s+(mes|meses|ano|anos)\s+despues\b"
    # "doble sismo" es el nombre fijo con el que los medios venezolanos se
    # refieren al sismo doble de La Guaira/Vargas de hace un mes -- ninguna
    # cobertura de un sismo genuinamente nuevo usaria ese termino exacto.
    r"|\bdoble\s+sismo\b",
    re.IGNORECASE,
)


def _quitar_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _normalizar(texto):
    return _quitar_tildes(texto.lower())


def _es_retrospectiva_obvia(texto):
    return _PATRON_RETROSPECTIVA.search(_normalizar(texto)) is not None


def _estados_mencionados_extra(texto_combinado, ubicacion_propia):
    """Devuelve la lista de estados (distintos de ubicacion_propia) que el
    texto combinado de las fuentes menciona explicitamente -- se usa
    exclusivamente para tipo=sismo, para saber si un mismo sismo fue
    reportado sintiendose en varios estados a la vez (p.ej. "se sintio en
    La Guaira, Distrito Capital y Miranda"), y asi poder correlacionar esa
    alerta con la que ya se publico bajo otra de esas ubicaciones el mismo
    dia (ver state.py)."""
    texto_norm = _normalizar(texto_combinado)
    encontrados = []
    for nombre_estado, alias in load_estados().items():
        if nombre_estado == ubicacion_propia:
            continue
        candidatos = set(alias) | {_normalizar(nombre_estado)}
        for candidato in candidatos:
            candidato_norm = _normalizar(candidato)
            if re.search(r"\b" + re.escape(candidato_norm) + r"\b", texto_norm):
                encontrados.append(nombre_estado)
                break
    return encontrados

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
    "\nDEBES RESPONDER EXCLUSIVAMENTE EN FORMATO JSON, sin explicaciones ni "
    "texto adicional. La estructura debe ser un objeto con una clave "
    "'veredictos' que contenga una lista de exactamente {n} strings ('SI' o "
    "'NO'), en el mismo orden en que se dan las fuentes.\n"
    "Ejemplo con 3 fuentes: {{\"veredictos\": [\"SI\", \"NO\", \"SI\"]}}"
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


def _parsear_veredictos_json(respuesta_texto, n):
    """Parsea la respuesta JSON de Groq, aceptando tanto un objeto con clave
    'veredictos' como una lista suelta. Normaliza tildes ('SÍ' -> 'SI') antes
    de comparar, y valida que haya exactamente n valores SI/NO -- cualquier
    otro caso devuelve None para que el llamador trate esto como fallo
    tecnico (fail-open auditado), no como una lista corrupta silenciosa."""
    try:
        datos = json.loads(respuesta_texto)
        if isinstance(datos, dict):
            valores = datos.get("veredictos", [])
        elif isinstance(datos, list):
            valores = datos
        else:
            return None

        valores_norm = [_quitar_tildes(str(v).strip()).upper() for v in valores]
        valores_validos = [v for v in valores_norm if v in ("SI", "NO")]

        if len(valores_validos) != n:
            return None
        return valores_validos
    except (json.JSONDecodeError, TypeError, ValueError, AttributeError):
        return None


def _finalizar_evento(evento, grupos_aprobados, error_sistema=False):
    """error_sistema=True marca que las fuentes no pasaron por un veredicto
    real de la IA (sin API key, respuesta no parseable, o fallo de red/rate
    limit tras agotar reintentos) y se dejaron pasar por seguridad -- queda
    registrado en 'estado_verificacion' para auditoria, y nunca se etiqueta
    como CONFIRMADO sin verificacion real, sin importar el score."""
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

    resultado = {
        "tipo": evento["tipo"],
        "ubicacion": evento["ubicacion"],
        "municipio": evento["municipio"],
        "parroquia": evento["parroquia"],
        "severidad": severidad_final,
        "score": round(score, 2),
        "confirmado": (score >= umbral) and not error_sistema,
        "num_fuentes": len(representantes),
        "fuentes": [
            {"nombre": m["fuente_nombre"], "link": m["link"], "fecha": m["fecha"]}
            for m in miembros_aprobados
        ],
        "fecha_evento": fecha_mas_reciente,
        "fecha_deteccion": datetime.now(timezone.utc).isoformat(),
        "estado_verificacion": "PASADO_POR_FALLA_TECNICA" if error_sistema else "APROBADO_IA",
    }

    # Solo para sismos: la magnitud y las menciones a otros estados sirven
    # para correlacionar (state.py) el mismo sismo sentido en varias
    # ubicaciones, sin depender de una ventana de tiempo estrecha entre
    # publicaciones (ver conversacion del 2026-07-25).
    if evento["tipo"] == "sismo":
        texto_combinado = " ".join(m["texto"] for m in miembros_aprobados)
        resultado["magnitud"] = extraer_magnitud(texto_combinado)
        resultado["tambien_mencionado_en"] = _estados_mencionados_extra(
            texto_combinado, evento["ubicacion"]
        )

    return resultado


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

    if not api_key:
        print("[WARN] GROQ_API_KEY no configurada, se omite verificación de plausibilidad")
        return _finalizar_evento(evento, grupos_fuentes, error_sistema=True)

    # Filtro determinista primero: descarta de una vez las fuentes cuyo texto
    # marca explicitamente una retrospectiva/aniversario (independiente del
    # juicio del modelo, que en produccion ha fallado con frases como "a un
    # mes del terremoto en Vargas..." pese a estar cubiertas en el prompt).
    obvios_rechazados = []
    candidatos = []
    for grupo in grupos_fuentes:
        representante = max(grupo, key=lambda m: m["peso"])
        if _es_retrospectiva_obvia(representante["texto"]):
            obvios_rechazados.append(representante)
        else:
            candidatos.append(grupo)

    if obvios_rechazados:
        detalle_rechazados = ", ".join(
            f"{r['fuente_nombre']} ({r['link']})" for r in obvios_rechazados
        )
        print(
            f"[DEBUG] Filtro retrospectiva [{evento['tipo']}/{evento['ubicacion']}]: "
            f"rechazadas sin IA por marca temporal explicita: {detalle_rechazados}"
        )

    if not candidatos:
        return None

    n = len(candidatos)
    fecha_actual = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(fecha_actual=fecha_actual, n=n)
    contenido_usuario = (
        f"TIPO ASIGNADO POR EL CLASIFICADOR: {evento['tipo']}\n\n"
        f"{_construir_prompt_fuentes(candidatos)}"
    )

    try:
        resp = None
        for intento in range(2):
            # Pequena pausa entre llamadas sucesivas a Groq: en un mismo
            # ciclo se llama una vez por evento agrupado, y sin espaciarlas
            # se alcanzaba el limite de tasa (429) y el evento se dejaba
            # pasar sin verificar (fail-open).
            time.sleep(1.5)
            resp = requests.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": GROQ_MODEL,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "max_tokens": max(30, n * 6 + 20),
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": contenido_usuario},
                    ],
                },
                timeout=20,
            )
            if resp.status_code == 429 and intento == 0:
                print("[WARN] Groq devolvió 429 (rate limit), reintentando en 5s...")
                time.sleep(5)
                continue
            break

        resp.raise_for_status()
        respuesta = resp.json()["choices"][0]["message"]["content"].strip()
        veredictos = _parsear_veredictos_json(respuesta, n)

        if veredictos is None:
            print(
                f"[WARN] Groq devolvió un JSON de veredictos inválido o de "
                f"tamaño distinto al esperado ({n} fuentes): '{respuesta[:200]}'. "
                f"Se deja pasar el evento por seguridad (sin marcar CONFIRMADO)."
            )
            return _finalizar_evento(evento, candidatos, error_sistema=True)

        representantes = [max(g, key=lambda m: m["peso"]) for g in candidatos]
        detalle = ", ".join(
            f"{r['fuente_nombre']} ({r['link']})={v}" for r, v in zip(representantes, veredictos)
        )
        grupos_aprobados = [g for g, v in zip(candidatos, veredictos) if v == "SI"]
        print(
            f"[DEBUG] Groq verificación [{evento['tipo']}/{evento['ubicacion']}]: "
            f"{detalle} → {len(grupos_aprobados)}/{n} fuentes aprobadas"
        )

        if not grupos_aprobados:
            return None

        return _finalizar_evento(evento, grupos_aprobados)

    except Exception as e:
        print(f"[WARN] Fallo la verificación con Groq, se deja pasar el evento (sin marcar CONFIRMADO): {e}")
        return _finalizar_evento(evento, candidatos, error_sistema=True)
