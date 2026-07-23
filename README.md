# Alerta CRV 24/7

Sistema de monitoreo automático de emergencias en Venezuela. Revisa fuentes RSS y canales de Telegram cada 10 minutos, detecta reportes de emergencias por palabras clave, corrobora entre múltiples fuentes, y publica noticias verificadas en un canal de Telegram y en un sitio web estático (GitHub Pages).

100% gratuito: corre sobre GitHub Actions (repo público) y GitHub Pages, sin usar ninguna API de pago.

## Cómo funciona

1. `fetch_rss.py` y `fetch_telegram.py` recolectan texto reciente de las fuentes configuradas en `config/sources.yaml`.
2. `classify.py` detecta tipo de emergencia y severidad por palabras clave (`config/keywords.yaml`), y ubicación solo si el texto trae un hashtag de estado (ej. `#Zulia`).
3. `verify.py` agrupa reportes del mismo tipo+ubicación y suma el "peso" de confiabilidad de cada fuente. Si supera el umbral (`config/settings.yaml`), se marca como **confirmado**; si no, se publica igual pero marcado como **sin confirmar**.
4. `render.py` redacta el texto final con una plantilla fija (sin IA).
5. `publish_telegram.py` publica en el canal de Telegram vía el bot.
6. `build_site.py` actualiza `docs/data/noticias.json`, que alimenta el sitio estático en `docs/index.html`.
7. `state.py` evita republicar el mismo evento en cada corrida, salvo que cambie de severidad o de estado de confirmación.

## Configuración (una sola vez)

### 1. Secrets del repositorio

Ve a **Settings → Secrets and variables → Actions → New repository secret** y crea:

| Secret | De dónde sale |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token del bot dado por @BotFather |
| `TELEGRAM_CHAT_ID` | Chat ID del canal (obtenido reenviando un mensaje a @RawDataBot) |
| `TELEGRAM_API_ID` | api_id de https://my.telegram.org |
| `TELEGRAM_API_HASH` | api_hash de https://my.telegram.org |
| `TELEGRAM_SESSION_STRING` | Generado con `generar_sesion.py` (ver más abajo) |

### 2. Activar GitHub Pages

**Settings → Pages → Build and deployment → Source: "Deploy from a branch" → Branch: main, carpeta `/docs`.**

El sitio quedará en `https://alertacrv.github.io/alerta-crv-24-7/` (o el usuario/repo que corresponda).

### 3. Activar el workflow

El archivo `.github/workflows/monitor.yml` corre automáticamente cada 10 minutos. También se puede disparar manualmente desde la pestaña **Actions → Monitoreo de Emergencias → Run workflow**.

## Agregar o quitar fuentes

Edita `config/sources.yaml` (RSS o canales de Telegram) sin tocar el código Python. Para Telegram, usa el username exacto (sin @) tal como aparece en `t.me/<username>`.

## Regenerar la session string de Telethon

Si cambias de cuenta de Telegram (ej. migrar de cuenta personal a institucional):

```bash
pip install telethon
python generar_sesion.py
```

Sigue las instrucciones en pantalla y actualiza el secret `TELEGRAM_SESSION_STRING` con el nuevo valor.

## Limitaciones actuales (v1)

- La ubicación solo se detecta si la fuente usa hashtags de estado (`#Zulia`, `#Miranda`, etc.) — reportes sin ese formato no se procesan.
- Sin IA: la clasificación es por palabras clave, puede tener falsos positivos/negativos.
- Cobertura de X/Twitter no incluida (sin API gratuita viable).
