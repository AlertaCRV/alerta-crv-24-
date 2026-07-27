import json
import os
import time
from collections import defaultdict
from datetime import datetime, timezone

import requests
from dateutil import parser as dateparser

from historico import leer_historico
from historico_fuentes import leer_texto_fuentes
from verify_ai import (
    GROQ_URL, GROQ_MODEL, ESPERA_ENTRE_LLAMADAS_GROQ,
    MAX_REINTENTOS_GROQ, ESPERA_BASE_REINTENTO_429,
)
from render import TIPO_LABELS

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INFORMES_DIR = os.path.join(BASE_DIR, "docs", "data", "informes")
INDEX_PATH = os.path.join(INFORMES_DIR, "index.json")

MAX_FUENTES_POR_INFORME = 40
MAX_CHARS_POR_FUENTE = 600

GENERAL = "general"

# Un evento con esta severidad tuvo danos materiales, heridos o victimas
# fatales (ver config/keywords.yaml) -- la narrativa nunca debe omitirlo,
# sin importar cuantos otros eventos mas leves haya en el mismo periodo.
# Caso real que origino esto: una tormenta electrica con 9 heridos en el
# aeropuerto de Valencia quedo fuera del informe "general" del mes, porque
# nada en el prompt distinguia ese evento de los demas sin daños.
SEVERIDADES_QUE_DEBEN_MENCIONARSE = {"alto", "critico"}

SYSTEM_PROMPT = (
    "Eres un analista de un sistema de monitoreo de emergencias en "
    "Venezuela (Cruz Roja Venezolana). Se te da un conjunto de fuentes "
    "periodísticas ya verificadas sobre emergencias ocurridas en un "
    "período y categoría específicos, y un dato de comparación numérica "
    "con el período anterior (ya calculado, no debes recalcularlo ni "
    "cuestionarlo). Tu tarea es escribir una narrativa en español, en "
    "prosa, de 3 a 6 párrafos, que resuma lo ocurrido en ese período.\n"
    "\nReglas estrictas:\n"
    "• Cada afirmación concreta (un hecho, cifra, ubicación o daño "
    "reportado) debe ir acompañada de una cita a su fuente entre "
    "paréntesis, con el formato (Nombre del medio). No inventes datos que "
    "no estén en las fuentes dadas.\n"
    "• Si se te da una lista de 'EVENTOS QUE DEBEN MENCIONARSE EXPLÍCITAMENTE' "
    "(tuvieron daños materiales, heridos o víctimas fatales), tu narrativa "
    "DEBE incluir cada uno de esos eventos por su nombre/ubicación y citar "
    "su fuente, sin importar cuántos otros eventos más leves haya — no es "
    "opcional, es el criterio más importante de esta tarea.\n"
    "• Menciona la comparación con el período anterior tal como se te da, "
    "sin modificarla.\n"
    "• No mezcles detalles de un evento con otro: si dos fuentes hablan de "
    "eventos distintos, distínguelos con claridad (ubicación y fecha).\n"
    "• Tono informativo y neutral, sin alarmismo ni especulación.\n"
    "\nDEBES RESPONDER EXCLUSIVAMENTE EN FORMATO JSON, sin texto fuera del "
    "JSON. Estructura: {\"narrativa\": \"...\"}"
)


def _mes(fecha_iso):
    dt = dateparser.isoparse(fecha_iso)
    return f"{dt.year:04d}-{dt.month:02d}"


def _mes_anterior(periodo):
    anio, mes = (int(x) for x in periodo.split("-"))
    if mes == 1:
        return f"{anio - 1:04d}-12"
    return f"{anio:04d}-{mes - 1:02d}"


def _mes_actual():
    ahora = datetime.now(timezone.utc)
    return f"{ahora.year:04d}-{ahora.month:02d}"


def _agrupar_por_periodo_y_tipo(registros_texto):
    grupos = defaultdict(list)
    for r in registros_texto:
        periodo = _mes(r["fecha_evento"])
        grupos[(periodo, r["tipo"])].append(r)
        grupos[(periodo, GENERAL)].append(r)
    return grupos


def _conteos_por_periodo_y_tipo(registros_historico):
    conteos = defaultdict(int)
    for r in registros_historico:
        if not r.get("fecha_evento"):
            continue
        periodo = _mes(r["fecha_evento"])
        conteos[(periodo, r["tipo"])] += 1
        conteos[(periodo, GENERAL)] += 1
    return conteos


def _construir_prompt_fuentes(registros):
    """Ordena las fuentes priorizando los eventos con danos/heridos/
    fallecidos (SEVERIDADES_QUE_DEBEN_MENCIONARSE) primero -- si hay mas de
    MAX_FUENTES_POR_INFORME fuentes en el periodo, un evento grave no debe
    quedar fuera del corte solo por el orden alfabetico."""
    fuentes_prioritarias = [
        f for r in registros if r.get("severidad") in SEVERIDADES_QUE_DEBEN_MENCIONARSE
        for f in r["fuentes"]
    ]
    fuentes_resto = [
        f for r in registros if r.get("severidad") not in SEVERIDADES_QUE_DEBEN_MENCIONARSE
        for f in r["fuentes"]
    ]
    fuentes_ordenadas = (
        sorted(fuentes_prioritarias, key=lambda f: f.get("nombre", ""))
        + sorted(fuentes_resto, key=lambda f: f.get("nombre", ""))
    )[:MAX_FUENTES_POR_INFORME]

    bloques = [
        f"--- {f['nombre']} ({f['link']}) ---\n{f['texto'][:MAX_CHARS_POR_FUENTE]}"
        for f in fuentes_ordenadas
    ]
    return bloques, fuentes_ordenadas


def _construir_bloque_eventos_obligatorios(registros):
    """Lista explicita de eventos que la narrativa debe mencionar si o si
    (ver SEVERIDADES_QUE_DEBEN_MENCIONARSE) -- no depende de que la IA los
    note por su cuenta entre el resto de fuentes."""
    obligatorios = [r for r in registros if r.get("severidad") in SEVERIDADES_QUE_DEBEN_MENCIONARSE]
    if not obligatorios:
        return "", []
    lineas = []
    for r in obligatorios:
        representante = r["fuentes"][0] if r["fuentes"] else None
        fuente_nombre = representante["nombre"] if representante else "fuente desconocida"
        lineas.append(
            f"- {TIPO_LABELS.get(r['tipo'], r['tipo'])} en {r['ubicacion']} "
            f"(severidad {r['severidad']}, fuente: {fuente_nombre})"
        )
    bloque = (
        "\nEVENTOS QUE DEBEN MENCIONARSE EXPLÍCITAMENTE (tuvieron daños "
        "materiales, heridos o víctimas fatales):\n" + "\n".join(lineas) + "\n"
    )
    return bloque, obligatorios


def _generar_narrativa(tipo_label, periodo, registros, comparacion):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("[WARN] GROQ_API_KEY no configurada, se omite generación de informes narrativos")
        return None

    bloques, fuentes_usadas = _construir_prompt_fuentes(registros)
    if not bloques:
        return None

    texto_comparacion = (
        f"Comparación con el período anterior ({comparacion['periodo_anterior']}): "
        f"{comparacion['anterior']} evento(s) registrados entonces vs. "
        f"{comparacion['actual']} en este período."
    )

    bloque_obligatorios, eventos_obligatorios = _construir_bloque_eventos_obligatorios(registros)

    contenido_usuario = (
        f"CATEGORÍA: {tipo_label}\n"
        f"PERÍODO: {periodo}\n"
        f"{texto_comparacion}\n"
        f"{bloque_obligatorios}\n"
        + "\n\n".join(bloques)
    )[:8000]

    try:
        resp = None
        for intento in range(MAX_REINTENTOS_GROQ):
            # Mismo patron de reintento que verify_ai.py: en una corrida con
            # muchos eventos, verify_ai.py ya hace varias llamadas a Groq
            # antes de llegar aqui, y la cuota puede seguir agotada -- se
            # reintenta hasta MAX_REINTENTOS_GROQ veces con espera creciente.
            time.sleep(ESPERA_ENTRE_LLAMADAS_GROQ)
            resp = requests.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": GROQ_MODEL,
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"},
                    "max_tokens": 1200,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": contenido_usuario},
                    ],
                },
                timeout=40,
            )
            if resp.status_code == 429 and intento < MAX_REINTENTOS_GROQ - 1:
                espera = ESPERA_BASE_REINTENTO_429 * (2 ** intento)
                print(f"[WARN] Informe {periodo}/{tipo_label}: Groq devolvió 429 (rate limit), reintentando en {espera}s... (intento {intento + 2}/{MAX_REINTENTOS_GROQ})")
                time.sleep(espera)
                continue
            break

        resp.raise_for_status()
        respuesta = resp.json()["choices"][0]["message"]["content"].strip()
        datos = json.loads(respuesta)
        narrativa = datos.get("narrativa")
        if not narrativa or not isinstance(narrativa, str):
            print(f"[WARN] Informe {periodo}/{tipo_label}: respuesta sin 'narrativa' válida")
            return None

        # Chequeo de auditoria, no bloqueante: si la IA no siguio la regla
        # de mencionar cada evento obligatorio, se deja constancia en el
        # log en vez de fallar en silencio -- reintentar no garantiza mejor
        # resultado, y el informe (con el resto del contenido) sigue siendo
        # mejor que no tener ninguno.
        omitidos = [
            r for r in eventos_obligatorios
            if r["fuentes"] and r["fuentes"][0]["nombre"] not in narrativa
        ]
        if omitidos:
            detalle = ", ".join(f"{r['tipo']}/{r['ubicacion']}" for r in omitidos)
            print(f"[WARN] Informe {periodo}/{tipo_label}: la narrativa no mencionó estos eventos con daños/heridos/fallecidos: {detalle}")

        return narrativa, fuentes_usadas
    except Exception as e:
        print(f"[WARN] Fallo la generación del informe {periodo}/{tipo_label}: {e}")
        return None


def _ruta_informe(periodo, tipo):
    return os.path.join(INFORMES_DIR, f"{periodo}_{tipo}.json")


def _necesita_generarse(periodo, tipo, cerrado):
    ruta = _ruta_informe(periodo, tipo)
    if not os.path.exists(ruta):
        return True
    if cerrado:
        return False  # un periodo cerrado se genera una sola vez y queda fijo
    with open(ruta, "r", encoding="utf-8") as f:
        existente = json.load(f)
    hoy = datetime.now(timezone.utc).date().isoformat()
    generado_el = dateparser.isoparse(existente["generado"]).date().isoformat()
    return generado_el != hoy  # el periodo en curso se regenera como mucho 1 vez al dia


def actualizar_informes():
    registros_historico = leer_historico()
    registros_texto = leer_texto_fuentes()
    if not registros_texto:
        return

    conteos = _conteos_por_periodo_y_tipo(registros_historico)
    grupos = _agrupar_por_periodo_y_tipo(registros_texto)
    mes_actual = _mes_actual()

    os.makedirs(INFORMES_DIR, exist_ok=True)
    indice = []

    for (periodo, tipo), registros in sorted(grupos.items()):
        cerrado = periodo < mes_actual
        if _necesita_generarse(periodo, tipo, cerrado):
            tipo_label = "Todas las categorías" if tipo == GENERAL else TIPO_LABELS.get(tipo, tipo.capitalize())
            comparacion = {
                "periodo_anterior": _mes_anterior(periodo),
                "anterior": conteos.get((_mes_anterior(periodo), tipo), 0),
                "actual": conteos.get((periodo, tipo), 0),
            }
            resultado = _generar_narrativa(tipo_label, periodo, registros, comparacion)
            if resultado is not None:
                narrativa, fuentes_usadas = resultado
                fuentes_unicas = list({(f["nombre"], f["link"]): f for f in fuentes_usadas}.values())
                fecha_mas_reciente = max(r["fecha_deteccion"] for r in registros)
                informe = {
                    "periodo": periodo,
                    "tipo": tipo,
                    "tipo_label": tipo_label,
                    "cerrado": cerrado,
                    "generado": datetime.now(timezone.utc).isoformat(),
                    "actualizado_hasta": fecha_mas_reciente,
                    "total_eventos": comparacion["actual"],
                    "comparacion_mes_anterior": comparacion,
                    "narrativa": narrativa,
                    "fuentes": [{"nombre": f["nombre"], "link": f["link"]} for f in fuentes_unicas],
                }
                with open(_ruta_informe(periodo, tipo), "w", encoding="utf-8") as f:
                    json.dump(informe, f, ensure_ascii=False, indent=2)

        ruta = _ruta_informe(periodo, tipo)
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8") as f:
                existente = json.load(f)
            indice.append({
                "periodo": existente["periodo"],
                "tipo": existente["tipo"],
                "tipo_label": existente["tipo_label"],
                "cerrado": existente["cerrado"],
                "generado": existente["generado"],
                "total_eventos": existente["total_eventos"],
            })

    indice.sort(key=lambda r: (r["periodo"], r["tipo"]), reverse=True)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(indice, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    actualizar_informes()
