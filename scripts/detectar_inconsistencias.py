"""Auditoria deterministica (sin IA) de dos clases de inconsistencia que ya
se repitieron mas de una vez y que una lectura manual, alerta por alerta,
tiende a pasar por alto:

1. Posibles alertas duplicadas ya publicadas: mismo tipo, dentro de una
   ventana de tiempo corta, que comparten un municipio o una palabra
   distintiva del link de alguna fuente (nombre de centro comercial, via,
   barrio...). Caso real (31-07-2026): el incendio del CCCT y el incendio
   del C.C. Los Cedros en Porlamar se publicaron 2 veces cada uno -- state.py
   ya debia evitarlo, pero un chequeo explicito e independiente sirve de
   segunda red antes de dar la auditoria por terminada.
2. Informes narrativos con fuentes "muertas": un link citado en
   docs/data/informes/*.json que ya no aparece en
   data/historico_fuentes_texto.jsonl -- señal de que el evento que
   describia se retracto (bug corregido) o se fusiono con otro, y el
   informe nunca se regenero para reflejarlo (requiere GROQ, no siempre
   disponible). Caso real (31-07-2026): varios informes de julio citaban
   una nota de protesta diplomatica y una correccion retrospectiva de
   epicentro sismico ya retractadas dias antes.

Este script NO corrige nada -- solo imprime un reporte para revision
humana/de la sesion de auditoria. Se ejecuta a mano (o al inicio de cada
auditoria diaria), no forma parte de validar_configs.py ni bloquea CI: los
falsos positivos son posibles (dos eventos genuinamente distintos pueden
compartir una palabra comun), asi que el resultado siempre requiere
confirmar contra el texto real de las fuentes antes de fusionar o corregir
algo.
"""

import glob
import json
import os
import re
import sys
import unicodedata
from datetime import timedelta
from itertools import combinations

from dateutil import parser as dateparser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config_loader import load_keywords  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTICIAS_PATH = os.path.join(BASE_DIR, "docs", "data", "noticias.json")
HISTORICO_FUENTES_PATH = os.path.join(BASE_DIR, "data", "historico_fuentes_texto.jsonl")
INFORMES_GLOB = os.path.join(BASE_DIR, "docs", "data", "informes", "*.json")

VENTANA_HORAS_POSIBLE_DUPLICADO = 72

# Con la blocklist ya bastante amplia (keywords.yaml + verbos/conectores/
# sustantivos genericos de nota de prensa), 1 token distintivo compartido
# alcanza -- exigir 2 hacia que se perdiera el caso real que motivo este
# script (dos fuentes cortas del mismo hecho, "...en-el-ccct-en-caracas" y
# "ccct", solo comparten "ccct").
MIN_TOKENS_COMPARTIDOS = 1

# Segmentos del path de una URL que son ruido (fecha, dominio generico,
# verbos periodisticos, conectores) y no ayudan a identificar el HECHO
# especifico -- si dos alertas del mismo tipo comparten 2+ tokens FUERA de
# esta lista (p.ej. "ccct", "los-cedros", "porlamar"), es una señal fuerte
# de que describen el mismo evento real, no solo la misma categoria.
# Se completa con todas las palabras de config/keywords.yaml (tipos +
# severidad): son, por definicion, genericas del dominio -- cualquier par
# de alertas del mismo tipo casi seguro comparte alguna.
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _normalizar(texto):
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _tokens_de_keywords():
    tokens = set()
    kw = load_keywords()
    for grupo in ("tipos", "severidad"):
        for lista in kw[grupo].values():
            for frase in lista:
                tokens.update(_TOKEN_RE.findall(_normalizar(frase)))
    return tokens


_TOKENS_RUIDO = _tokens_de_keywords() | {
    "www", "com", "net", "info", "co", "ve", "html", "php", "mail", "google",
    "outlook", "search", "rfc822msgid", "prod", "namprd08",
    "noticias", "sucesos", "regionales", "regiones", "nacionales",
    "nacional", "venezuela", "estado", "estados", "municipio", "parroquia",
    "video", "videos", "fotos", "articulo", "noticia", "prensa",
    "reportan", "reporta", "reportaron", "reportado", "reportada",
    "registra", "registro", "registran", "registraron", "registrado",
    "confirma", "confirman", "confirmado", "informa", "informan",
    "denuncia", "denuncian", "autoridades", "funcionarios", "gobierno",
    "gobernacion", "alcaldia", "bomberos", "rescate", "rescatistas",
    "policia", "policial", "guardia", "nacional", "voceros", "vocero",
    "zona", "zonas", "sector", "sectores", "region", "regionales",
    "varios", "varias", "otro", "otros", "otras", "tras", "luego",
    "despues", "durante", "este", "esta", "estos", "estas", "ese", "esa",
    "esos", "esas", "cuando", "donde", "como", "para", "con", "sin",
    "las", "los", "una", "unos", "unas", "que", "sus", "mas", "menos",
    "segun", "informacion", "difundida", "publicada", "publico",
    "lunes", "martes", "miercoles", "jueves", "viernes", "sabado",
    "domingo", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    "causo", "causaron", "provoco", "provocaron", "dejo", "dejaron",
    "afecto", "afectaron", "afectados", "afectadas", "genero", "generaron",
    "comercial", "comerciales", "local", "locales", "horas", "hora",
    "oposicion", "paso", "controlan", "exito", "tienda", "tiendas",
    "centro", "centros", "edificio", "edificios", "avenida", "avenidas",
    "sitio", "lugar", "lluvia", "lluvias", "intensas", "intenso", "fuerte",
    "fuertes", "torrenciales", "torrencial",
}

# Hashtags de fecha frecuentes en titulares/urls (#26Jul, #29jul...): un dia
# del mes + abreviatura de mes de 3 letras no identifica un hecho, solo una
# fecha -- dos eventos de lluvia genuinamente distintos, publicados un par
# de dias aparte, pueden terminar compartiendo uno por coincidencia de
# calendario.
_TOKEN_FECHA_RE = re.compile(
    r"^\d{1,2}(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)$"
)


def _tokens_distintivos_de_link(link):
    """Tokens del path de la URL (sin dominio) de 5+ caracteres, sin
    numeros sueltos (fechas) ni palabras genericas de _TOKENS_RUIDO.
    Los links de correo institucional (mail.google.com) son una busqueda
    por id de mensaje, no una URL descriptiva del hecho -- no aportan
    ninguna señal util aqui."""
    if "mail.google.com" in link:
        return set()
    partes = link.split("/", 3)
    path = partes[3] if len(partes) > 3 else link
    tokens = _TOKEN_RE.findall(_normalizar(path))
    return {
        t for t in tokens
        # 4+ para no perder siglas cortas pero reales de un hecho especifico
        # (CCCT); el resto del filtro (blocklist + 2+ tokens compartidos)
        # se encarga del ruido de palabras cortas genericas.
        if len(t) >= 4 and t not in _TOKENS_RUIDO and not t.isdigit()
        and not _TOKEN_FECHA_RE.match(t)
    }


def _cargar_noticias():
    if not os.path.exists(NOTICIAS_PATH):
        return []
    with open(NOTICIAS_PATH, encoding="utf-8") as f:
        return json.load(f)


def detectar_posibles_duplicados(noticias, ventana_horas=VENTANA_HORAS_POSIBLE_DUPLICADO):
    """Devuelve una lista de (alerta_a, alerta_b, razon) para pares de
    alertas YA PUBLICADAS que podrian describir el mismo hecho real."""
    limite = timedelta(hours=ventana_horas)
    sospechosos = []

    for a, b in combinations(noticias, 2):
        if a.get("tipo") != b.get("tipo"):
            continue
        try:
            fecha_a = dateparser.isoparse(a.get("fecha_evento_temprana", a["fecha_evento"]))
            fecha_b = dateparser.isoparse(b.get("fecha_evento_temprana", b["fecha_evento"]))
        except (KeyError, ValueError):
            continue
        if abs(fecha_a - fecha_b) > limite:
            continue

        razones = []

        municipio_a, municipio_b = a.get("municipio"), b.get("municipio")
        if municipio_a and municipio_b and municipio_a == municipio_b:
            razones.append(f"mismo municipio ({municipio_a})")

        tokens_a = {t for f in a.get("fuentes", []) for t in _tokens_distintivos_de_link(f["link"])}
        tokens_b = {t for f in b.get("fuentes", []) for t in _tokens_distintivos_de_link(f["link"])}
        compartidos = tokens_a & tokens_b
        if len(compartidos) >= MIN_TOKENS_COMPARTIDOS:
            razones.append(f"palabras compartidas en el link: {sorted(compartidos)}")

        if razones:
            sospechosos.append((a, b, "; ".join(razones)))

    return sospechosos


def _links_citados_en_historico():
    if not os.path.exists(HISTORICO_FUENTES_PATH):
        return set()
    links = set()
    with open(HISTORICO_FUENTES_PATH, encoding="utf-8") as f:
        for linea in f:
            evento = json.loads(linea)
            for fuente in evento.get("fuentes", []):
                links.add(fuente["link"])
    return links


def detectar_fuentes_muertas_en_informes():
    """Devuelve {ruta_informe: [fuentes_muertas]} -- fuentes citadas en un
    informe narrativo que ya no existen en el registro historico (el
    evento se retracto o se fusiono con otro despues de que el informe se
    generara, y nunca se regenero -- requiere GROQ, ver build_informes.py)."""
    links_vivos = _links_citados_en_historico()
    resultado = {}
    for ruta in sorted(glob.glob(INFORMES_GLOB)):
        if ruta.endswith("index.json"):
            continue
        with open(ruta, encoding="utf-8") as f:
            informe = json.load(f)
        muertas = [f for f in informe.get("fuentes", []) if f["link"] not in links_vivos]
        if muertas:
            resultado[os.path.relpath(ruta, BASE_DIR)] = muertas
    return resultado


def main():
    noticias = _cargar_noticias()
    duplicados = detectar_posibles_duplicados(noticias)
    fuentes_muertas = detectar_fuentes_muertas_en_informes()

    if not duplicados and not fuentes_muertas:
        print("Sin inconsistencias detectadas.")
        return 0

    if duplicados:
        print(f"=== {len(duplicados)} posible(s) par(es) de alertas duplicadas ===")
        for a, b, razon in duplicados:
            print(f"- [{a['clave_dedup']}] vs [{b['clave_dedup']}]")
            print(f"    {a['titulo']!r} ({a.get('fecha_evento_temprana', a.get('fecha_evento'))})")
            print(f"    {b['titulo']!r} ({b.get('fecha_evento_temprana', b.get('fecha_evento'))})")
            print(f"    razon: {razon}")
        print()

    if fuentes_muertas:
        total = sum(len(v) for v in fuentes_muertas.values())
        print(f"=== {total} fuente(s) muerta(s) en {len(fuentes_muertas)} informe(s) narrativo(s) ===")
        for ruta, fuentes in fuentes_muertas.items():
            print(f"- {ruta}:")
            for f in fuentes:
                print(f"    {f['nombre']}: {f['link']}")
        print()

    print(
        "Nada de esto se corrigio automaticamente -- revisa cada caso contra "
        "el texto real de las fuentes (data/historico_fuentes_texto.jsonl) "
        "antes de fusionar alertas o editar un informe."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
