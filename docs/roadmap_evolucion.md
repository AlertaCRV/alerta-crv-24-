# Roadmap de evolución de AlertaCRV

Este documento recoge la conversación del 26/07/2026 sobre hacia dónde
podría evolucionar el sistema más allá de su función actual (agregar,
verificar y publicar alertas en tiempo real). Los cuatro objetivos están
ordenados por impacto/esfuerzo estimado, no por dependencia estricta entre
ellos — el #1 es el que menos depende de resolver problemas difíciles
(moderación, integración institucional) y más aprovecha el trabajo de
clasificación que el sistema ya hace hoy.

## 1. Capa de analítica histórica pública

**Qué es**: un panel público (no solo el feed en vivo de últimas alertas)
con tendencias por estado y tipo de emergencia a lo largo del tiempo:
cuántas fallas eléctricas confirmadas tuvo un estado en un mes, cuántos
sismos, cómo evolucionó la severidad de un tipo de evento en el tiempo.

**Por qué importa**: en un país donde las estadísticas oficiales de
infraestructura, salud o seguridad son opacas o inexistentes, este dato no
lo está produciendo hoy nadie más de forma sistemática y auditable. Es el
salto de mayor valor: convierte la herramienta de "alerta reactiva" a
"fuente de referencia citable" para prensa, ONGs e investigadores.

**Por qué es el más alcanzable**: los datos ya se generan en cada corrida
(tipo, ubicación, severidad, confirmación, fechas); hoy simplemente se
descartan a los 3 días porque `data/publicados.json` es una caché de
deduplicación, no un registro histórico. No depende de resolver moderación
de contenido de terceros ni de una integración institucional externa.

*(Ver la sección "Cómo alcanzar el objetivo #1" más abajo para el plan
concreto.)*

## 2. Canal de reporte ciudadano como fuente adicional

**Qué es**: un bot de Telegram/WhatsApp donde cualquier persona pueda
reportar una emergencia directamente, tratado como una fuente más dentro
del mismo pipeline de verificación (no publicado a ciegas: pasa por el
mismo cruce de independencia de fuentes y verificación de plausibilidad
con IA que hoy aplica a los medios).

**Por qué importa**: ataca el techo estructural del sistema actual — si un
evento ocurre en una zona sin cobertura mediática (el vacío de Amazonas
detectado al evaluar medios), el sistema no lo ve, sin importar cuán bien
clasifique lo que sí le llega. Un canal ciudadano es la única forma de
extender la cobertura geográfica más allá de donde ya publica la prensa.

**Principal reto**: moderación y verificación de reportes anónimos sin
"peso" de fuente conocido (spam, mala fe, error honesto) — probablemente
requiere un peso inicial bajo y exigir corroboración cruzada más estricta
que la de un medio establecido antes de publicar.

## 3. Ampliar tipos de emergencia cubiertos

**Qué es**: agregar tipos hoy no reconocidos por `config/keywords.yaml`
— tsunami (gap ya señalado: hoy ni siquiera es un tipo detectable), brotes
de salud pública con mayor granularidad, escasez de combustible, motines
carcelarios, entre otros que puedan surgir del uso real del sistema.

**Por qué importa**: cobertura más completa del espectro de emergencias
que le compete a la Cruz Roja, con el mismo estándar de verificación ya
construido (filtros de contexto conflictivo, evidencia fuerte por tipo,
etc.) aplicado a cada tipo nuevo.

**Principal reto**: cada tipo nuevo requiere su propio ajuste fino de
palabras clave y, probablemente, sus propios falsos positivos por resolver
— el patrón ya visto con sismos (retrospectivas, contexto conflictivo)
seguramente se repite con matices distintos en cada tipo nuevo.

## 4. Integración operativa directa

**Qué es**: en vez de (o además de) publicar en Telegram/web para consumo
público, alimentar un flujo de despacho interno de Cruz Roja Venezolana u
otro organismo humanitario/de coordinación.

**Por qué importa**: es el salto de "herramienta informativa" a
"herramienta operativa" — de mayor impacto potencial, pero también de
mayor responsabilidad.

**Principal reto**: un uso operativo (decisiones de despacho de recursos)
exige una tasa de falsos positivos/negativos mucho más baja que la
aceptable para informar al público general; probablemente requiere
madurar más el pipeline de verificación actual (el trabajo de esta semana
con sismos y severidad es un paso en esa dirección) antes de que tenga
sentido conectarlo a decisiones operativas reales.

---

## Cómo alcanzar el objetivo #1: analítica histórica pública

### El problema actual

`data/publicados.json` (`scripts/state.py`) es una caché de deduplicación
con retención de solo 3 días (`DIAS_RETENCION = 3`) — existe únicamente
para no repetir la misma alerta en corridas sucesivas. No es, ni debe
convertirse en, un registro histórico: mezclar ambas funciones haría el
archivo de deduplicación más pesado en cada corrida y complicaría su
lógica sin necesidad.

### Plan propuesto

1. **Registro histórico independiente y de solo-append.**
   Nuevo archivo `data/historico_eventos.jsonl` (JSON Lines: un evento
   publicado por línea, fácil de append sin reescribir el archivo
   completo). Cada vez que `main.py` publica una noticia nueva
   (`eventos_nuevos` en el ciclo actual), además de pasar por
   `marcar_publicados`, se le agrega una línea con los campos ya
   disponibles: `tipo`, `ubicacion`, `municipio`, `parroquia`,
   `severidad`, `confirmado`, `num_fuentes`, `score`, `fecha_evento`,
   `fecha_deteccion`. Sin fecha de expiración — o, si el archivo crece
   demasiado con los años, con rotación anual (`historico_2026.jsonl`,
   `historico_2027.jsonl`, ...), no con purga como la caché de 3 días.

2. **Script de agregación.** Nuevo `scripts/build_dashboard.py` que lee
   `historico_eventos.jsonl` completo y calcula los rollups que alimentan
   el panel: conteos por `(estado, tipo, mes)`, distribución de severidad,
   serie temporal mensual por tipo. Escribe el resultado en un archivo
   *agregado y liviano* (`docs/data/estadisticas.json`) — el panel público
   nunca debe leer el histórico crudo completo en el navegador, solo el
   resumen ya calculado, para que la página cargue rápido sin importar
   cuántos años de datos se acumulen.

3. **Página del panel.** Nuevo `docs/dashboard.html` (o una pestaña dentro
   de `docs/index.html`) que consume `docs/data/estadisticas.json` y
   grafica tendencias — barras por estado/tipo, serie mensual. Se sirve
   igual que el resto del sitio (GitHub Pages, estático), sin backend
   adicional.

4. **Integración al ciclo existente.** En `.github/workflows/monitor.yml`,
   el paso "Guardar cambios" ya hace `git add data/publicados.json
   docs/data/noticias.json` — se añaden `data/historico_eventos.jsonl` y
   `docs/data/estadisticas.json` a ese mismo `git add`, y `main.py` llama
   a `build_dashboard.py` (o su lógica equivalente) antes de guardar,
   igual que hoy llama a `build_site.py`. No se necesita infraestructura
   nueva: el mismo flujo de PR + check `validar` + auto-merge que ya
   existe para los datos del sitio cubre también estos dos archivos
   nuevos.

### Por qué este orden

Separar "caché de deduplicación" (efímera, 3 días) de "registro histórico"
(permanente) evita que un cambio en la lógica de retención de una rompa la
otra, y permite que el histórico crezca sin afectar el rendimiento del
ciclo de verificación en vivo — la agregación para el panel es un paso
aparte, no algo que compita por tiempo con la publicación de alertas.

---

## Alcance de la v1 del dashboard (definido el 26/07/2026)

Antes de implementar el objetivo #1, se discutió qué indicadores incluir y
cómo se vería el panel. Esta sección documenta esa conversación y la
decisión tomada — **sin implementar nada todavía**.

### Indicadores candidatos considerados

Con los campos que ya captura cada evento (`tipo`, `ubicacion`,
`severidad`, `confirmado`, `num_fuentes`, `score`, `fecha_evento`,
`fecha_deteccion`) se pueden construir, sin tocar el pipeline de
verificación:

- Conteo total y tendencia por **tipo** de evento (sismo, incendio, orden
  público, etc.)
- Ranking de **estados** con más alertas — separando total vs. solo
  confirmadas, porque un estado con muchas alertas sin confirmar puede
  reflejar un medio poco fiable, no necesariamente más emergencias reales.
- Cruce **estado × tipo** (qué estados concentran qué tipos de evento).
- **Distribución de severidad** (crítico/alto/medio/bajo/sin_clasificar)
  en el tiempo — también sirve como métrica de la calidad del propio
  sistema: si el % de "sin clasificar" baja con los meses, es evidencia de
  que las heurísticas están mejorando.
- **Latencia de detección**: tiempo promedio entre `fecha_evento` y
  `fecha_deteccion` — el indicador más honesto de qué tan "en tiempo real"
  es el sistema en la práctica, y se conecta directo con el problema del
  cron todavía pendiente de resolver.
- **Confirmado vs. sin confirmar** en el tiempo: qué proporción de
  alertas termina corroborada por múltiples fuentes.
- **Racha de días** sin eventos críticos/altos por estado.

Se descartó explícitamente un ranking público de "qué medio publica más" o
"qué medio es más rápido/confiable": el dato técnicamente existe (el
`peso` de cada fuente), pero convertirlo en un ranking público de medios
es territorio sensible ajeno al propósito humanitario del sistema — queda
como métrica interna, no como panel público.

**Limitación conocida**: el sistema solo registra la *detección* de un
evento, no su *resolución* — no existe una señal de "esta falla eléctrica
ya se resolvió". Por lo tanto, un indicador de "duración promedio de una
falla" no se puede calcular de forma confiable con los datos actuales, y
queda fuera de alcance hasta que exista esa señal.

### ¿Dashboard "estilo bolsa de valores" en la misma página que las alertas?

Conclusión: la idea es parcialmente factible y parcialmente expectativa a
ajustar.

- **Factible**: integrar el panel en la misma página que el feed de
  alertas en vivo (franja de indicadores arriba, feed debajo) — es un
  patrón común de "sala de situación", no requiere backend nuevo, es
  HTML/CSS/JS estático igual que el resto del sitio.
- **No factible tal cual se imaginó**: números cambiando cada segundo. El
  sitio solo se actualiza cuando `monitor.yml` corre y comitea datos
  nuevos (hoy, en el mejor caso cada ~10 min; con el problema de cron
  pendiente, a veces cada 2-4 horas), y los medios venezolanos tampoco
  publican con cadencia de segundos. Un ticker que se mueve cada segundo
  sin dato nuevo detrás sería animación cosmética — precisamente el tipo
  de apariencia-de-certeza que este sistema evita en su diseño.
- **Alternativa honesta**: la página hace `fetch` periódico (cada 30-60s)
  del JSON de estadísticas, sin backend adicional, y anima la transición
  del número viejo al nuevo únicamente cuando detecta un cambio real. Se
  siente "vivo" sin fingir una cadencia de datos que no existe. Como
  beneficio colateral, resolver el problema del cron pendiente hará que
  este panel se sienta más "vivo" de verdad, no solo en apariencia.

### Decisión: empezar angosto, complejizar con el tiempo

El sistema lleva apenas días con las heurísticas actuales en su forma
estable (los ajustes de sismos, severidad y deduplicación de esta misma
semana). Se decidió **no** construir un dashboard ambicioso ahora:

1. Un indicador elaborado hoy mezclaría datos de "antes" y "después" de
   estos cambios recientes sin que se note.
2. Todavía no hay uso real acumulado del sistema para validar qué
   indicadores son realmente útiles vs. decorativos.

**V1 acordada** (los cuatro que menos dependen de suposiciones sin
validar): conteo por tipo, ranking de estados, cruce estado × tipo, y
distribución de severidad.

**Diferidos a versiones posteriores**, a evaluar según lo que se aprenda
con el uso real en las próximas semanas/meses: latencia de detección,
confirmado vs. sin confirmar en el tiempo, racha de días sin eventos
críticos, y duración de fallas prolongadas (bloqueado hasta que exista una
señal de resolución de evento).

Ningún cambio de código se implementó en esta sesión — esta sección es
únicamente la definición de alcance acordada para cuando se decida
empezar la implementación.

**Nota (26/07/2026, tras implementar la v1):** el panel muestra el
histórico completo desde el día 0, sin filtro de rango de fechas, tipo o
estado — cualquier usuario ve siempre todos los eventos acumulados. Se
decidió no agregar un filtro todavía; se evaluará más adelante, según lo
que se aprenda con el uso real, si hace falta (p.ej. selector de
último mes / último año, o por tipo/estado).

---

## Extensión del objetivo 1: informes narrativos por período y tipo

Idea adicional planteada el 26/07/2026: además de los indicadores
numéricos del dashboard, generar informes en prosa — "¿qué pasó con los
incendios en julio de 2026?" — con una narrativa rica en detalles, no solo
conteos y gráficos.

### Por qué no alcanza con lo ya planeado para el objetivo #1

El registro histórico propuesto (`data/historico_eventos.jsonl`) guarda
los campos estructurados de cada evento (tipo, ubicación, severidad,
confirmación, fechas) y el **link** de cada fuente, pero no el texto
completo del artículo. Para tejer una narrativa rica en detalles a partir
de "todos los artículos que informaron sobre incendios en un período", el
sistema necesita el texto completo de esos artículos, no solo un enlace —
y hoy ese texto se usa en memoria durante cada corrida y se descarta
después. Reconstruirlo meses después reabriendo cada link es frágil: los
artículos viejos suelen desaparecer, cambiar de URL o quedar bloqueados.

### Decisiones tomadas (26/07/2026)

**Fuente del texto — se guarda el texto completo al publicar.** Al
extender `historico_eventos.jsonl` (o el registro que lo reemplace), cada
fuente de cada evento publicado guarda también su texto completo, no solo
el link. Esto asegura que un informe de hace meses se pueda reconstruir
con el mismo detalle que si se generara el mismo día, sin depender de que
el artículo original siga en línea. Contrapartida asumida
conscientemente: el registro crece más rápido que si solo guardara
estructura, y guarda contenido de terceros con derechos de autor — uso
aceptable para síntesis **interna** (alimentar una narrativa propia con
citas y enlaces de vuelta a la fuente), pero el sitio público nunca debe
reproducir un artículo completo tal cual, solo la narrativa sintetizada
con sus citas.

**Generación — informes precalculados por el sistema, no en vivo.** El
sistema (en una corrida periódica, p.ej. mensual, o incremental sobre el
mes en curso) genera con IA la narrativa para combinaciones estándar de
período × tipo, usando el texto de fuentes ya guardado, y la guarda como
archivo estático (similar a `docs/data/estadisticas.json`). La página web
solo muestra informes ya generados — la parte "interactiva" es elegir
entre lo ya preparado (qué mes, qué tipo), no una consulta libre en vivo.
Esto mantiene el sitio 100% estático (GitHub Pages, sin backend nuevo), no
expone la clave de la API de IA en el navegador, y no genera costo de IA
por cada visitante. Generación en vivo bajo demanda quedó descartada por
ahora: requeriría construir un servidor/backend nuevo — un cambio de
arquitectura mayor a todo lo hecho hasta ahora — y pagar el costo de IA
por cada consulta de cada visitante.

**Cadencia de regeneración (preliminar, 26/07/2026).** Un período ya
cerrado (p.ej. "incendios de junio" una vez terminó junio) se genera una
sola vez y queda fijo — sus datos no cambian. El período en curso (el mes
actual, mientras sigue corriendo) sí necesita regenerarse, pero no en cada
corrida del monitor (regenerar la narrativa completa con IA cada ~10 min
por cualquier evento nuevo, sin importar el tipo, sería costoso e
innecesario): la decisión preliminar es regenerarlo **una vez al día**.
Aún es pronto para comprometerse a esto en firme — queda sujeto a
revisión cuando se implemente. El informe siempre debe mostrar una marca
de "actualizado hasta: fecha/hora", igual que ya hacen las alertas con
"🔎 Detectado por el sistema", para que quede claro qué rango del período
cubre realmente lo que se está leyendo.

**Comparación sucinta con el período anterior (26/07/2026).** El informe
de un mes puede incluir una mención breve del mes anterior (p.ej. "en
comparación con junio, cuando se registraron 4 incendios, julio cerró con
6") sin necesidad de releer los artículos del mes anterior: basta con
reutilizar los agregados numéricos que ya calculará el dashboard del
objetivo #1 (conteo y severidad por mes/tipo) para el período previo, y
pasarlos como contexto fijo al generar el informe del período actual. La
comparación es un cálculo determinista (resta/porcentaje sobre datos ya
verificados), no algo que se le pida "recordar" o resumir a la IA — evita
que el informe de julio reinterprete o contradiga lo que ya dijo el
informe de junio sobre sí mismo, y no requiere releer texto completo de
fuentes de meses anteriores.

### Cómo debería funcionar, en línea con el resto del sistema

Igual que las alertas individuales muestran sus fuentes y explican por qué
se clasificaron así, un informe narrativo generado por IA debe incluir
**citas explícitas a la fuente de cada afirmación** (no un resumen sin
atribución) — es la misma disciplina de auditabilidad aplicada a un texto
más largo y sintetizado por IA, donde el riesgo de mezclar detalles de
eventos distintos es mayor que en la verificación de un solo evento a la
vez que ya hace `verify_ai.py`.

### Dependencia

Esta extensión depende de que el objetivo #1 (registro histórico) ya
exista — se implementa como una ampliación de ese mismo registro (agregar
el texto completo por fuente), no como un sistema aparte. No se ha
implementado nada de código; queda documentada para cuando se decida
empezar.

---

## Bono a fuentes regionales reportando sobre su propia zona (26/07/2026)

**Pregunta que originó el cambio**: al revisar alertas publicadas, ¿debería
importar si el medio que reporta un evento está asentado en el lugar de los
hechos o no?

**Decisión**: sí, pero como un ajuste **fluctuante por evento**, no como un
cambio fijo al `peso` de la fuente en `config/sources.yaml`. La razón: un
mismo medio regional (p.ej. "La Verdad", asentado en Zulia) debe pesar más
cuando reporta sobre su propia zona que cuando reporta sobre otro estado —
eso depende de la combinación medio+evento, no solo del medio, así que no
se puede resolver con un campo fijo tipo "es medio local: sí/no".

**Implementación**:
- `config/sources.yaml` gana un campo opcional `region` (estado donde el
  medio está asentado) en los medios claramente regionales/locales. Los
  medios nacionales (Efecto Cocuyo, La Patilla, Runrun.es, El Pitazo, Tal
  Cual, ReliefWeb) se quedan sin ese campo.
- `scripts/verify_ai.py` calcula, al sumar el score de un evento, un "peso
  efectivo" por fuente: si `fuente.region == evento.ubicacion`, se suma un
  bono de **+0.1** al peso de esa fuente para ese evento puntual. El `peso`
  guardado en la config no cambia, y el umbral de confirmación
  (`umbral_confirmado = 1.2`) tampoco.
- 0.1 es un valor conservador de partida, elegido para evitar que un solo
  medio local de baja confiabilidad general se vuelva "confirmante" él
  solo por estar en la zona. Se ajustará según lo que se observe con uso
  real.

---

## Severidad "medio" mal justificada y municipio/parroquia sin detectar (26/07/2026)

**Problema 1 — severidad "medio" sin evidencia real**: `config/keywords.yaml`
incluía "afectados" como palabra clave de severidad "medio". Es una palabra
demasiado genérica: aparece incluso en frases que niegan daño ("sin
afectados que lamentar", "no se reportan afectados"). Se quitó de la lista,
y `classify.py` ahora usa `_contiene_palabra_clave_no_negada`, que descarta
una coincidencia si está negada a pocas palabras de distancia ("sin", "no",
"ningún...").

**Problema 2 — municipio/parroquia casi nunca se detectaban**:
`detectar_municipio_parroquia` solo reconocía el municipio/parroquia si el
texto traía literalmente "municipio X"/"parroquia Y" — la mayoría de las
noticias solo dicen "en Petare", sin esa palabra explícita. Se agregó una
búsqueda por nombre directo usando los datos ya existentes en
`ubicaciones_detalle.json`, descartando nombres repetidos en más de un
estado (Sucre, Bolívar, Miranda, Libertador... son nombres de próceres
reusados como municipio en varios estados a la vez, y también son nombres
de estado) o de menos de 5 caracteres, por ser demasiado ambiguos para una
coincidencia sin ese contexto explícito.

**Extensión con IA (26/07/2026)**: la búsqueda por nombre directo sigue sin
resolver el caso de un municipio que se llama igual que su propio estado
(ej. "Sucre" como municipio de Miranda) cuando el texto no dice
"municipio X" explícitamente. Para esos casos, se extendió la misma llamada
a Groq que ya hace `verify_ai.py` para verificar plausibilidad: cuando
`classify.py` no pudo determinar municipio y/o parroquia, se le pide a la
IA (en el mismo prompt, sin llamada aparte) que intente inferirlo del texto
completo de las fuentes — pero restringido a elegir EXCLUSIVAMENTE un valor
de la lista real de municipios/parroquias de ese estado (o `null`). Un
valor que no esté en esa lista se descarta como si la IA no hubiera
respondido nada, igual que la verificación de plausibilidad nunca confía en
texto libre sin validar. Si `classify.py` ya había determinado un valor,
la IA nunca lo sobrescribe.

**Alias de nombre corto para municipios (26/07/2026)**: al probar el
pipeline con un texto real ("municipio Guaicaipuro"), el municipio quedó
sin detectar porque el nombre oficial en `ubicaciones_detalle.json` es
"Bolivariano Guaicaipuro" — la prensa casi nunca usa el calificativo
oficial completo. Se identificaron 9 municipios con el mismo problema
(calificativos "Autónomo", "Bolivariano", "Indígena Bolivariano" que casi
nunca aparecen en la prensa). En vez de reescribir el nombre oficial (que
sigue siendo el correcto para fines de registro), una entrada de
`municipios`/`parroquias` en `ubicaciones_detalle.json` ahora puede ser
también una lista `[nombre_oficial, alias_corto]` en vez de un string
suelto — `classify.py` reconoce cualquiera de las dos formas al buscar
coincidencias (tanto la explícita "municipio X" como la búsqueda directa
por nombre), y siempre devuelve el nombre oficial como resultado.

---

## Implementación de los informes narrativos (26/07/2026)

Se implementó la extensión de informes narrativos descrita más arriba,
resolviendo las preguntas que habían quedado abiertas:

- **Almacenamiento del texto completo**: archivo aparte,
  `data/historico_fuentes_texto.jsonl` (no se mezcla con
  `data/historico_eventos.jsonl`, que sigue liviano para que
  `build_dashboard.py` lo siga leyendo rápido en cada corrida).
- **Granularidad**: un informe por mes × tipo de emergencia (ej. "incendios
  de julio"), más un informe "general" por mes que cubre todas las
  categorías juntas.
- **Ubicación en el sitio**: una sección plegable más en `docs/index.html`
  (`📰 Informes narrativos por período`), junto a la de tendencias — no una
  página aparte.

**Cómo se evita que el sitio público filtre texto de terceros**: se
descubrió que `render.py` arma la noticia pública haciendo
`{**evento, ...}` — cualquier campo que se le agregara al evento
terminaría publicado tal cual. Por eso el texto completo de cada fuente se
guarda bajo una clave "privada" (`_texto_fuentes_completo`) que
`historico_fuentes.registrar_texto_fuentes()` extrae y **borra** del
evento — y ese paso corre ANTES de `redactar_noticia()`/
`actualizar_datos_sitio()` en `main.py`. Se verificó explícitamente con una
prueba que el texto completo nunca llega al JSON público.

**Piezas nuevas**:
- `scripts/historico_fuentes.py`: registra/lee el texto completo por
  fuente.
- `scripts/build_informes.py`: agrupa el histórico por (período, tipo),
  decide si cada combinación necesita generarse (período cerrado = una
  sola vez y nunca más; período en curso = como mucho 1 vez por día UTC,
  comparando la fecha de la última generación), arma el prompt con las
  fuentes y la comparación numérica determinística contra el mes anterior
  (reutilizando `historico.leer_historico()`, no le pide a la IA que
  "recuerde" nada), y guarda cada informe como
  `docs/data/informes/<periodo>_<tipo>.json` más un `index.json` liviano
  para poblar los selectores de la página sin tener que leer cada informe.
- El prompt de generación exige citas explícitas entre paréntesis al
  nombre del medio en cada afirmación concreta, igual disciplina de
  auditabilidad que ya aplica `verify_ai.py` a la verificación de eventos
  individuales.
- `.github/workflows/monitor.yml`: se corrigió también un riesgo latente
  — `git add` falla si un archivo no existe todavía (y el step corre con
  `-e`), lo que hubiera roto el workflow en un repo nuevo antes de la
  primera corrida con contenido real. Ahora cada ruta se agrega solo si ya
  existe.

Probado de punta a punta con datos simulados: generación de informe
cerrado y en curso, no regeneración de un período cerrado ya existente,
comparación con el mes anterior, y verificación de que el texto completo
de las fuentes nunca se filtra al sitio público.

**Pendiente para retomar más adelante, con datos reales (26/07/2026)**:
antes de recalibrar el prompt hace falta ver cómo sale la narrativa con
eventos reales (esta sesión solo probó con datos simulados) — queda
pendiente para cuando haya uso acumulado. Dos ajustes ya identificados
para esa revisión:

1. **Estructura según volumen de eventos**: el prompt actual pide "3 a 6
   párrafos" sin distinguir si el período tuvo 3 eventos o 40 — con
   muchos eventos, una narrativa así se vuelve una lista ilegible de
   nombres y fechas en vez de una síntesis útil. Con más eventos convendría
   pedir una estructura agrupada (por semana o por estado dentro del
   informe) en lugar de alargar el texto plano. Se descartó por ahora
   ofrecer descarga del informe (PDF/documento) como solución a esto: el
   problema es de estructura de la narrativa, no de pantalla vs.
   descarga.
2. **Énfasis temático**: calibrar el prompt para que la narrativa haga
   énfasis explícito en respuesta del Estado/autoridades, pérdidas
   económicas, pérdida de vidas, y personas heridas — hoy el prompt solo
   pide una síntesis general con citas, sin priorizar estos temas
   puntuales.

**Aviso por Telegram cuando se genera un informe nuevo (26/07/2026,
pendiente)**: hoy Telegram (`publish_telegram.py`) solo envía el mensaje
individual de cada alerta puntual — no participa del panel de tendencias
ni de los informes narrativos, que son contenido de navegación (selectores,
tablas) sin sentido como mensaje de chat. Idea para más adelante: cuando
`build_informes.py` genere un informe mensual nuevo, enviar un aviso corto
a Telegram (ej. "📰 Ya está listo el informe de incendios de julio: 
[link]"), no el contenido completo — un aviso puntual, no una réplica del
panel. No implementado; queda anotado para retomar.

---

## Objetivo #3: ampliar tipos de emergencia cubiertos (26/07/2026)

Se agregaron 11 tipos nuevos a `config/keywords.yaml` (antes solo existían
sismo, incendio, inundación, deslizamiento, infraestructura eléctrica/agua,
vialidad, orden público y salud pública):

- **tsunami** — antes ni siquiera era un tipo detectable (gap ya señalado
  en la sección "Qué es" del objetivo #3 original).
- **tormenta_electrica** — rayos/tormentas eléctricas. Se evitó a propósito
  la palabra suelta "rayo"/"rayos" (demasiado ambigua: "rayos X", "rayos de
  sol", nombres propios) — solo frases específicas como "impacto de rayo",
  "fulminado por un rayo".
- **derrame_petrolero** — derrames de hidrocarburos/contaminación de agua,
  relevante para el Lago de Maracaibo y costas venezolanas.
- **explosion** — se separó de `incendio` (que ya evitaba la palabra suelta
  "explosion" por el mismo motivo de ambigüedad idiomática); usa frases
  específicas ("explosión industrial", "artefacto explosivo", "coche
  bomba").
- **sequia** — escasez prolongada de agua potable, distinto de
  `infraestructura_agua` (que es sobre fallas puntuales del servicio, no
  escasez estructural).
- **colapso_estructural** — colapso de puentes/edificaciones, distinto de
  `deslizamiento` (que ya usa "derrumbe" para deslaves naturales).
- **crisis_migratoria** — desplazamiento/éxodo masivo.
- **escasez_combustible** — colas y desabastecimiento de gasolina.
- **motin_carcelario** — motines, amotinamientos, fugas masivas.
- **accidente_transporte** — accidentes aéreos, marítimos y ferroviarios;
  se mantuvo separado de `vialidad` (que sigue siendo solo lo vial
  urbano/carretera).
- **ataque_armado** — guerrilla, paramilitares, atentados, terrorismo;
  separado de `orden_publico` (que sigue siendo disturbios/protestas/
  saqueos, hechos más espontáneos que un ataque armado organizado).

**salud_publica se amplió en vez de crear un tipo aparte** para
pandemia/alerta epidemiológica: ya tenía palabras clave muy cercanas
(brote, epidemia, enfermedad) y crear `alerta_epidemiologica` como tipo
separado hubiera sido, en la práctica, casi redundante. Se sumaron
pandemia, cuarentena, aislamiento sanitario, emergencia/alerta
epidemiológica, brote epidémico, contagio masivo.

**Qué se dejó fuera a propósito, por ahora**: siguiendo el mismo criterio
usado para `sismo` (los filtros de contexto conflictivo/evidencia fuerte
se agregaron *después* de observar falsos positivos reales en producción,
no de antemano), ninguno de estos 11 tipos nuevos tiene todavía ese tipo de
filtro. Se agregarán si el uso real muestra falsos positivos concretos,
igual que pasó con sismo.

Probado con 12 casos de ejemplo (uno por tipo nuevo + salud_publica
ampliado) contra `classify.detectar_tipo()`, todos con el resultado
esperado. `validar_configs.py` sigue pasando.
