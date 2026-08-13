import calendar
import html
import re
import time
from datetime import datetime, timezone

import feedparser
import requests
from bs4 import BeautifulSoup

from config_loader import load_estados, load_sources

HEADERS_NAVEGADOR = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

_HTML_TAG_RE = re.compile(r"<[^>]+>")
# Pie de pagina que agregan algunos feeds RSS de WordPress ("La entrada X se
# publico primero en NOMBRE DEL MEDIO", o su equivalente en ingles "The post
# X first appeared on NOMBRE DEL MEDIO"). Es puro ruido de plantilla: si el
# nombre del medio incluye un estado (p.ej. "El Periodico de Monagas",
# "Portuguesa Reporta"), el clasificador puede confundirlo con la ubicacion
# real de la noticia -- caso real: un articulo sin ninguna mencion de
# Portuguesa genero una alerta de sismo en ese estado porque el pie de
# pagina en ingles ("...first appeared on Portuguesa Reporta.") no lo
# capturaba el regex, que solo cubria la variante en español.
_BOILERPLATE_RE = re.compile(
    r"la entrada .*?se public(?:o|ó) primero en.*$"
    r"|the post .*?first appeared on.*$",
    re.IGNORECASE | re.DOTALL,
)

# Muchos feeds de WordPress agregan, al final del resumen, una lista de
# titulos de "articulos relacionados" ("Lea tambien:"/"Lee tambien:" seguido
# de varios titulos sin relacion con el articulo real). Esos titulos pueden
# contener palabras clave de tipo/severidad que no describen el hecho real
# -- caso real: un articulo sobre una donacion de utiles a La Guaira
# (ninguna relacion con incendios) se clasifico como tipo=incendio porque
# terminaba con "Lea tambien: ... Tres incendios en menos de un mes
# registra la ciudad de Maturin" -- el titulo de OTRA nota, no del articulo
# en si.
#
# Otras plantillas de WordPress usan variantes distintas para el mismo tipo
# de bloque de "articulos relacionados", con el orden de las palabras
# invertido ("Tambien Puedes Leer:") o precedido de una frase fija ("Si
# quieres conocer otras noticias parecidas a X puedes visitar la categoria
# Y"). Caso real (05-08-2026, notiapure.com.ve): un articulo intrascendente
# sobre un sismo de magnitud 6.3 en la isla de Mindanao, Filipinas -- que el
# propio texto aclara "sin causar victimas" -- genero DOS alertas falsas de
# sismo critico en Venezuela (Apure y Anzoategui) porque el pie de pagina
# de "Tambien Puedes Leer" enlazaba titulos de OTRAS notas locales sin
# relacion ("Policia De Apure Detiene...", "...Ocho Sujetos En Anzoategui",
# "...Biruaca estado Apure") junto con titulos que si mencionaban
# "fallecidos"/"muertos" (de un sismo venezolano real, pero de mas de un
# mes atras), lo que ademas hizo que el filtro de "evidencia fuerte" de
# sismo (ver verify_ai.py) NO descartara el articulo.
#
# El Impulso usa aun otra variante: el infinitivo "Leer tambien:" (en vez
# del imperativo "Lea/Lee tambien:"). Caso real (07-08-2026): un articulo
# sobre una protesta de familiares de presos politicos frente a la
# Cancilleria en Caracas traia embebidos, sin relacion con el hecho, dos
# enlaces "Leer tambien:" que mencionaban "tres muertes" y "51 victimas
# fatales" de un suceso carcelario totalmente distinto (El Marite) -- no
# llego a cambiar la severidad publicada esta vez, pero es el mismo riesgo
# ya documentado arriba (palabras de severidad de OTRA nota contaminando
# el texto real).
_ARTICULOS_RELACIONADOS_RE = re.compile(
    r"\b(lea|lee|leer)\s+tambi[ée]n\s*:.*$"
    r"|\btambi[ée]n\s+puedes\s+leer\s*:.*$"
    r"|\bsi\s+quieres\s+conocer\s+otras\s+noticias\s+parecidas\s+a\b.*$",
    re.IGNORECASE | re.DOTALL,
)

# Otra variante del mismo problema de "articulos relacionados", con una
# plantilla distinta: El Pitazo (y posiblemente otros medios con la misma
# plataforma) tambien inyecta, EN MEDIO del cuerpo del articulo -- no solo
# al final -- tarjetas/widgets de recirculacion con el formato fijo
# "Estado | Titular de otra nota", pegadas directamente al texto real sin
# ningun punto que las separe. Caso real (07-08-2026): un articulo integro
# sobre presos politicos en huelga de hambre en el Fuerte Guaicaipuro (que
# esta en el estado Miranda, nunca mencionado en el texto) genero una
# alerta de orden_publico en Zulia solo porque el texto traia embebido,
# sin relacion alguna, "Zulia | Policia encuentra cuerpo de coronel
# retirado de la GN con rastros de violencia" -- el titular de otra nota
# completamente distinta. La plantilla SI es legitima cuando es el
# titular del propio articulo (siempre al inicio del texto, ej. "Bolivar |
# Hombres armados atacan..."), pero en esos casos el estado real siempre
# se repite explicitamente mas adelante en el cuerpo ("estado Bolivar"),
# asi que quitar la marca en cualquier posicion no pierde informacion real
# -- solo se quita el separador "Estado |", no el resto del titular
# (evitar over-fitting a un formato de titular que varia por nota).
_NOMBRE_ESTADO_SEGUIDO_DE_PLECA_RE = re.compile(
    r"\b(?:" + "|".join(
        sorted(
            (re.escape(alias) for nombre, alias_list in load_estados().items()
             for alias in [nombre, *alias_list]),
            key=len, reverse=True,
        )
    ) + r")\s*\|\s*",
    re.IGNORECASE,
)

# El pie de pagina/menu de sitio de algunos medios incluye el nombre legal
# de la empresa editora seguido de su RIF ("Editorial Torbes CA
# J-070059680 Miniavisos Edicion Impresa Mapa del sitio..."), que
# BeautifulSoup arrastra como parrafos normales cuando el articulo no esta
# dentro de un <article>/div.content reconocible (ver _obtener_texto_
# completo, que en ese caso cae al documento completo). Caso real (12-08-
# 2026, lanacionweb.com/Diario La Nacion Tachira): "Editorial Torbes CA"
# es el nombre legal del medio -- Torbes tambien es, por coincidencia, un
# municipio real de Tachira -- y esa unica mencion (ajena al articulo, sin
# relacion con ningun hecho) bastaba para que detectar_municipio_parroquia()
# le atribuyera "Municipio Torbes" a un articulo sobre una crisis electrica
# que en realidad nunca nombra ese municipio (el pronunciamiento se emitio
# "en San Cristobal" y afecta, segun el propio texto, "los 29 municipios"
# del estado por igual). Se recorta desde la mencion del pie legal hasta el
# final del texto, igual que el pie de pagina de WordPress.
_PIE_LEGAL_EDITORIAL_RE = re.compile(
    r"\beditorial\s+[\wÀ-ÿ]+(?:\s+[\wÀ-ÿ]+)?\s+c\.?a\.?\s+j-\d+.*$",
    re.IGNORECASE | re.DOTALL,
)

# Muchos feeds RSS truncan el resumen del articulo y marcan el corte con
# puntos suspensivos (a veces como caracter unico "…", a veces como
# "[...]", a veces como el caracter unico envuelto en corchetes "[…]" --
# esta ultima variante, muy comun en plantillas de WordPress, no coincidia
# con NINGUna de las dos alternativas ya cubiertas ("…" sola exige que no
# haya nada mas despues, y "\[\s*\.\.\.\s*\]" exige tres puntos literales
# dentro de los corchetes, no el caracter de elipsis). Caso real (11-08-
# 2026, Runrun.es): un resumen truncado en "...que sufrio el vecino pais
# la manana de este lunes, […]" nunca disparaba _obtener_texto_completo(),
# dejando fuera del texto que ve el clasificador la frase clave que
# identificaba el hecho como una cobertura retrospectiva de un sismo de
# hace casi dos meses ("a casi dos meses del doble terremoto, siguen
# buscando a sus familiares"), no un derrumbe nuevo -- eso, sumado a que
# el propio articulo solo menciona La Guaira para contrastarla con un
# sismo real ocurrido en Colombia, genero una alerta de deslizamiento
# completamente falsa. Se verifico contra las 118 fuentes de data/
# historico_fuentes_texto.jsonl que 33 (28%) terminan en este patron
# "[…]" sin haber obtenido nunca su texto completo -- el mismo problema
# potencial (aunque sin evidencia de haber cambiado el resultado en esos
# otros 32 casos) para una porcion sustancial del corpus.
_TRUNCADO_RE = re.compile(r"(…|\[\s*(?:\.\.\.|…)\s*\]|\.\.\.\s*$)\s*$")

# "Caracas" es alias de Distrito Capital, pero tambien se usa a diario en
# sentido coloquial del area metropolitana, que incluye municipios reales
# de Miranda (Chacao/Baruta/El Hatillo, ver LISTA_NEGRA_POR_ESTADO en
# classify.py). Un resumen de RSS puede mencionar "Caracas" sin venir
# truncado (frase completa, sin puntos suspensivos) y aun asi omitir el
# municipio real, que solo aparece mas adelante en el cuerpo del articulo
# -- caso real (02-08-2026): "Un incendio en un edificio de Las Mercedes
# deja dos personas lesionadas. Efectivos de los Bomberos de Caracas
# sofocaron las llamas..." es una oracion completa (no truncada), pero
# el municipio real ("Baruta") solo aparece en el cuerpo completo de la
# pagina, nunca en el resumen del feed. Se trae el texto completo tambien
# en estos casos para que el clasificador tenga la oportunidad de ver ese
# municipio.
_CARACAS_RE = re.compile(r"\bcaracas\b", re.IGNORECASE)
_MUNICIPIOS_CARACAS_CONOCIDOS_RE = re.compile(
    r"\b(libertador|chacao|baruta|el hatillo)\b", re.IGNORECASE
)

LONGITUD_MAXIMA_TEXTO_COMPLETO = 4000


def _limpiar_texto(texto):
    # Algunos feeds entregan sus entidades HTML doblemente escapadas (el feed
    # crudo trae "&amp;#8230;", que tras un solo unescape -- el que ya hace
    # feedparser/BeautifulSoup -- queda como el texto literal "&#8230;" en
    # vez del caracter real "…"). Sin este segundo unescape, "&#8230;"/
    # "&hellip;" no coinciden con _TRUNCADO_RE (que busca el caracter real),
    # asi que el resumen truncado nunca dispara la descarga del texto
    # completo -- y detalles clave (ubicacion, muertes, heridos) quedan
    # fuera del texto que ve el clasificador sin que nada lo avise. Caso
    # real: un resumen que terminaba en "...colapsara, como&#8230;",
    # truncado justo antes de la ubicacion y la palabra "murio".
    texto = html.unescape(texto)
    texto = _BOILERPLATE_RE.sub("", texto)
    texto = _ARTICULOS_RELACIONADOS_RE.sub("", texto)
    texto = _PIE_LEGAL_EDITORIAL_RE.sub("", texto)
    texto = _NOMBRE_ESTADO_SEGUIDO_DE_PLECA_RE.sub("", texto)
    texto = _HTML_TAG_RE.sub(" ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _obtener_texto_completo(link):
    """Descarga la pagina del articulo y extrae el texto de sus parrafos,
    para los casos en que el resumen del RSS viene truncado. Si falla por
    cualquier razon (red, parsing, sitio caido), devuelve None y el
    llamador sigue usando el resumen truncado en vez de fallar la corrida
    completa por un solo articulo."""
    try:
        resp = requests.get(link, headers=HEADERS_NAVEGADOR, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "lxml")
        contenedor = soup.find("article") or soup.find(
            "div", class_=lambda c: c and "content" in c.lower()
        )
        parrafos = (contenedor or soup).find_all("p")
        texto = " ".join(p.get_text(" ", strip=True) for p in parrafos)
        texto = re.sub(r"\s+", " ", texto).strip()
        return texto[:LONGITUD_MAXIMA_TEXTO_COMPLETO] if texto else None
    except Exception as e:
        print(f"[WARN] No se pudo obtener el texto completo de {link}: {e}")
        return None


def fetch_rss_items(ventana_horas=12):
    """Devuelve una lista de items crudos desde todos los feeds RSS configurados."""
    items = []
    limite = time.time() - ventana_horas * 3600

    for fuente in load_sources().get("rss", []):
        try:
            resp = requests.get(fuente["url"], headers=HEADERS_NAVEGADOR, timeout=15)
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
        except Exception as e:
            print(f"[WARN] No se pudo leer el RSS de {fuente['nombre']}: {e}")
            continue

        sin_fecha = 0
        for entry in parsed.entries:
            published_struct = entry.get("published_parsed") or entry.get("updated_parsed")
            if not published_struct:
                # Sin fecha real en el feed no hay forma de saber si el item
                # es reciente o de hace semanas -- se descarta en vez de
                # asumir "ahora". Asumir "ahora" fue un bug real: hacia que
                # articulos viejos de medios sin fecha en su RSS (ej.
                # Notitarde, ninguno de sus 50 items trae pubDate) parecieran
                # siempre recien publicados en cada corrida.
                sin_fecha += 1
                continue

            # feedparser entrega este struct_time ya normalizado a UTC.
            # calendar.timegm() lo interpreta como UTC sin importar la zona
            # horaria del sistema (a diferencia de time.mktime(), que asume
            # que el struct esta en hora local del proceso).
            published_ts = calendar.timegm(published_struct)

            if published_ts < limite:
                continue

            texto = " ".join(filter(None, [entry.get("title", ""), entry.get("summary", "")]))
            texto = _limpiar_texto(texto)

            link = entry.get("link", "")
            necesita_texto_completo = bool(link and _TRUNCADO_RE.search(texto))
            if (
                not necesita_texto_completo
                and link
                and _CARACAS_RE.search(texto)
                and not _MUNICIPIOS_CARACAS_CONOCIDOS_RE.search(texto)
            ):
                necesita_texto_completo = True
            if necesita_texto_completo:
                texto_completo = _obtener_texto_completo(link)
                if texto_completo:
                    texto = _limpiar_texto(
                        " ".join(filter(None, [entry.get("title", ""), texto_completo]))
                    )

            items.append({
                "fuente_nombre": fuente["nombre"],
                "fuente_tipo": "rss",
                "peso": fuente.get("peso", 0.5),
                "region": fuente.get("region"),
                "texto": texto,
                "link": entry.get("link", ""),
                "fecha": datetime.fromtimestamp(published_ts, tz=timezone.utc).isoformat(),
            })

        if sin_fecha:
            print(f"[WARN] {fuente['nombre']}: {sin_fecha} item(s) sin fecha en el RSS, descartados")

    return items


if __name__ == "__main__":
    for i in fetch_rss_items():
        print(i["fuente_nombre"], "-", i["texto"][:80])
