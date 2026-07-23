import time
from datetime import datetime, timezone

import feedparser
import requests

from config_loader import load_sources

HEADERS_NAVEGADOR = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


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

        for entry in parsed.entries:
            published_struct = entry.get("published_parsed") or entry.get("updated_parsed")
            if published_struct:
                published_ts = time.mktime(published_struct)
            else:
                published_ts = time.time()

            if published_ts < limite:
                continue

            texto = " ".join(filter(None, [entry.get("title", ""), entry.get("summary", "")]))

            items.append({
                "fuente_nombre": fuente["nombre"],
                "fuente_tipo": "rss",
                "peso": fuente.get("peso", 0.5),
                "texto": texto,
                "link": entry.get("link", ""),
                "fecha": datetime.fromtimestamp(published_ts, tz=timezone.utc).isoformat(),
            })

    return items


if __name__ == "__main__":
    for i in fetch_rss_items():
        print(i["fuente_nombre"], "-", i["texto"][:80])
