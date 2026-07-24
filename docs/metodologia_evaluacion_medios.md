# Metodología de evaluación para nuevos medios

Este documento define el proceso a seguir antes de agregar un nuevo medio a
`config/sources.yaml`, y cómo determinar su `peso` (score de confiabilidad).

## Prompt de evaluación

Cuando se evalúe un medio nuevo para posible inclusión, usar el siguiente
prompt (con un modelo de IA, o como checklist manual) para asignarle un
Índice de Confiabilidad estricto en una escala de 0.5 a 0.9:

> **Rol**: Actúa como un auditor experto en metodologías de la comunicación
> e integridad periodística. Tu objetivo es evaluar un catálogo de medios
> digitales y asignar a cada uno un Índice de Confiabilidad estricto en una
> escala del 0.5 al 0.9.
>
> **Metodología de Baremación**: Cada medio inicia con una Base Mínima de
> 0.5. Se sumarán o restarán puntajes parciales según las siguientes
> dimensiones:
>
> - **Gobernanza Institucional** (hasta +0.15): +0.15 si es un organismo
>   oficial técnico/humanitario; +0.10 si es un medio de comunicación
>   consolidado con comité editorial explícito; +0.05 si es un portal
>   independiente o blog regional con autoría identificable.
> - **Verificabilidad y Citas** (hasta +0.10): +0.10 si fundamenta sus
>   notas en informes, documentos técnicos o citas directas; +0.05 si la
>   información es mayoritariamente de redacción propia sin enlaces de
>   contraste.
> - **Historial de Precisión** (hasta +0.10): +0.10 si carece de
>   antecedentes de alarmismo, difusión de bulos o desmentidos públicos.
> - **Rigor Geográfico/Temporal** (hasta +0.05): +0.05 si la muestra de
>   notas delimita con precisión cronológica y toponímica el origen de los
>   hechos.
> - **Penalización por Densidad Publicitaria** (detractor de hasta -0.10):
>   se resta el valor exacto indicado en el reporte de evidencia debido al
>   exceso de bloques publicitarios (ad-arbitrage).

## Verificación técnica obligatoria (además del prompt anterior)

Antes de confiar en cualquier evaluación (propia o de un tercero/otra IA)
sobre la accesibilidad de un feed, **se debe reverificar en vivo con
`curl` u otra herramienta real** — no basta con el juicio de un modelo de
lenguaje sobre si un sitio "está caído" o "es de otro país". El 24 de julio
de 2026 se detectaron varios casos donde una evaluación externa reportó
como "bloqueados" o "inestables" medios que en realidad funcionaban
correctamente (El Pitazo, La Patilla, Reporte Confidencial, entre otros),
y al revés, no detectó un caso real de contenido reemplazado por spam de
apuestas (Última Hora Digital, Portuguesa). La verificación técnica mínima
antes de excluir o incluir un medio por accesibilidad:

1. `curl -L` al feed, siguiendo redirecciones, con un User-Agent de
   navegador real.
2. Confirmar código HTTP 200 y estructura XML válida (`<rss>`/`<item>` o
   `<feed>`/`<entry>`).
3. Confirmar que el feed tiene artículos reales (no solo la estructura
   vacía) y que el contenido corresponde genuinamente a Venezuela.
4. Si el sitio devuelve una página de challenge (Cloudflare, CloudFront,
   CAPTCHA), no forzar el acceso — se documenta como bloqueado y se
   excluye, sin inventar una causa alternativa no verificada.

## Reglas de inclusión/exclusión vigentes (definidas 2026-07-24)

1. Excluir medios con score inferior a 0.6 — **solo cuando la falla
   también se confirma en la verificación técnica en vivo** (ver sección
   anterior). Un score bajo por sí solo, sin evidencia técnica
   corroborada de mal funcionamiento, no es motivo suficiente de exclusión.
2. Excluir medios que no sea posible consultar por RSS/feed o similar
   (confirmado en vivo).
3. Excluir medios de otros países o con contenido no pertinente a
   Venezuela, **excepto** agencias de Naciones Unidas o agencias
   humanitarias internacionales (ej. ReliefWeb).
