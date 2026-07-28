import calendar
import html
import re
import time
from datetime import datetime, timezone

import feedparser
import requests
from bs4 import BeautifulSoup

from config_loader import load_sources

HEADERS_NAVEGADOR = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

_HTML_TAG_RE = re.compile(r"<[^>]+>")
# Pie de pagina que agregan algunos feeds RSS de WordPress ("La entrada X se
# publico primero en NOMBRE DEL MEDIO"). Es puro ruido de plantilla: si el
# nombre del medio incluye un estado (p.ej. "El Periodico de Monagas"), el
# clasificador puede confundirlo con la ubicacion real de la noticia.
_BOILERPLATE_RE = re.compile(r"la entrada .*?se public(?:o|ó) primero en.*$", re.IGNORECASE | re.DOTALL)

# Muchos feeds RSS truncan el resumen del articulo y marcan el corte con
# puntos suspensivos (a veces como caracter unico "…", a veces como
# "[...]"). Cuando el resumen esta truncado, detalles clave (ubicacion
# exacta, muertes, heridos) pueden quedar fuera del texto que ve el
# clasificador -- de ahi que se intente traer el texto completo del
# articulo desde su pagina en esos casos.
_TRUNCADO_RE = re.compile(r"(…|\[\s*\.\.\.\s*\]|\.\.\.\s*$)\s*$")

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
            if link and _TRUNCADO_RE.search(texto):
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
