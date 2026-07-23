import json
import os
from datetime import datetime, timedelta, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(BASE_DIR, "docs")
DATA_PATH = os.path.join(DOCS_DIR, "data", "noticias.json")
DIAS_RETENCION_SITIO = 14


def actualizar_datos_sitio(noticias_nuevas):
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            noticias = json.load(f)
    else:
        noticias = []

    noticias = noticias_nuevas + noticias

    limite = datetime.now(timezone.utc) - timedelta(days=DIAS_RETENCION_SITIO)
    noticias = [
        n for n in noticias
        if datetime.fromisoformat(n["fecha_deteccion"]).replace(tzinfo=timezone.utc) > limite
    ]

    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(noticias, f, ensure_ascii=False, indent=2)

    _generar_html()


def _generar_html():
    os.makedirs(DOCS_DIR, exist_ok=True)
    index_path = os.path.join(DOCS_DIR, "index.html")
    if os.path.exists(index_path):
        return  # el HTML es estático y fijo, solo se genera una vez; lee data/noticias.json en vivo
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(_HTML_TEMPLATE)


_HTML_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Alerta CRV 24/7</title>
<style>
  body { font-family: system-ui, sans-serif; background:#0b0f14; color:#e6e6e6; margin:0; padding:1rem; }
  h1 { font-size:1.4rem; }
  .noticia { border:1px solid #2a2f36; border-radius:8px; padding:1rem; margin-bottom:1rem; background:#131820; }
  .confirmado { border-left:4px solid #2ecc71; }
  .sin-confirmar { border-left:4px solid #f39c12; }
  .meta { font-size:0.85rem; color:#9aa4b2; }
  a { color:#6cb6ff; }
  pre { white-space:pre-wrap; word-wrap:break-word; font-family:inherit; }
</style>
</head>
<body>
<h1>🛰️ Alerta CRV 24/7 — Monitoreo de Emergencias en Venezuela</h1>
<div id="lista">Cargando...</div>
<script>
fetch('data/noticias.json').then(r => r.json()).then(noticias => {
  const cont = document.getElementById('lista');
  if (!noticias.length) { cont.textContent = 'Sin reportes recientes.'; return; }
  cont.innerHTML = noticias.map(n => `
    <div class="noticia ${n.confirmado ? 'confirmado' : 'sin-confirmar'}">
      <pre>${n.texto.replace(/</g,'&lt;')}</pre>
    </div>
  `).join('');
});
</script>
</body>
</html>
"""
