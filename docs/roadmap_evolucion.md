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

**Un tipo más, agregado después (26/07/2026): `emergencia_metro`.** Metro
de Caracas, Metrocable y teleférico no calzaban con ningún tipo existente
— `accidente_transporte` está pensado para aéreo/marítimo/ferroviario
interurbano, no transporte masivo urbano. Se creó como tipo aparte, con
frases como "falla en el metro", "varados en el metro", "descarrilamiento
del metro", "falla en el teleférico". Al probarlo se encontró un caso real
de redacción demasiado rígida ("usuarios varados en el metro" no
calzaba con "usuarios *quedaron* varados en el metro") — se corrigió
quitando el sujeto de la frase clave ("varados en el metro" a secas).

---

## Filtro determinista para vialidad: evitar alertas por choques individuales (26/07/2026)

**Problema real observado en producción**: un choque entre dos
motorizados, con un fallecido, se publicó como alerta de severidad
**CRÍTICA**. La severidad se calcula sin importar el tipo de evento (la
palabra "fallecido" siempre dispara "crítico"), y el prompt de
`verify_ai.py` ya le pedía a la IA rechazar accidentes viales rutinarios
de 1-2 vehículos sin víctimas múltiples ni colapso de vía — pero en la
práctica un caso así se aprobó igual, dependiendo únicamente del juicio
del modelo.

**Solución**: se agregó un filtro determinista para `tipo=vialidad`, que
corre ANTES de la IA (mismo patrón que el filtro de retrospectivas de
sismos) — no depende de su juicio. Un reporte de vialidad se descarta sin
consultar a la IA si el texto no contiene evidencia explícita de:
- **Accidente múltiple/masivo** ("colisión múltiple", "choque múltiple",
  "accidente masivo", "colapso vial"/"vía colapsada").
- **Involucramiento de transporte público** ("volcamiento de autobús",
  "unidad de transporte público").
- **Varios heridos** (3 o más heridos/lesionados explícitos, en número o
  en palabra — "tres heridos" —, o las frases "varios/múltiples/numerosos
  heridos").
- **Varios fallecidos** (**5 o más** fallecidos/muertos explícitos — ajustado
  el mismo día de 3 a 5, un umbral más alto que el de heridos porque un
  choque de la misma magnitud típicamente deja más heridos que fallecidos).

Un choque individual entre 1-2 vehículos con una sola víctima —el caso
real que originó este ajuste— ya no llega ni a evaluarse con IA: se
descarta directamente, sin importar si el texto menciona "fallecido" (que
seguiría disparando severidad "crítica" si el evento pasara, porque la
severidad no distingue tipo o escala).

Probado con 7 casos de ejemplo contra `_vialidad_sin_evidencia_fuerte()`,
incluido el caso real reportado ("choque entre dos motorizados... un
fallecido" → correctamente descartado).

---

## Primera corrida real en producción tras el merge (26/07/2026)

Al mergear el objetivo #1 y disparar el monitor manualmente, se generaron
por primera vez datos reales: 7 eventos nuevos (incluido uno de
`tormenta_electrica`, confirmando que los tipos nuevos del objetivo #3 se
detectan correctamente en producción) y 5 de los 6 informes narrativos
esperados (mes × tipo + general).

**Bug encontrado**: el informe "general" (y también sismo y vialidad) no
se generaron esa corrida — Groq devolvió **429 (rate limit)** para esas 3
llamadas. Causa: en una corrida con muchos eventos agrupados (15 esa vez),
`verify_ai.py` ya hace varias llamadas a Groq antes de llegar a generar
informes, y `build_informes.py` no tenía el mismo reintento con backoff
que `verify_ai.py` sí tiene para sus propias llamadas — un solo 429 hacía
fallar el informe completo esa corrida (aparece de nuevo al día siguiente,
por la regeneración diaria del período en curso, pero se pierde esa
corrida). Se agregó el mismo patrón de reintento (esperar 5s y reintentar
una vez) que ya usa `verify_ai.py`. Probado con un 429 simulado seguido de
una respuesta exitosa.

---

## Filtro determinista para sismos: reducir el ruido de temblores menores (26/07/2026)

**Problema real observado**: demasiados reportes de actividad sísmica
menor (magnitud 3.1-3.3, sin daños) estaban empañando el propósito del
sistema de alerta. Se revisaron las 8 alertas de sismo publicadas hasta
ese momento: ninguna alcanzaba magnitud 4, ninguna mencionaba colapso
estructural, heridos o fallecidos.

**Regla acordada**: un sismo solo se publica si se cumple al menos una de
estas dos condiciones:
1. **Magnitud ≥ 4.0 Y** el texto indica que fue sentido por la población
   ("se sintió", "sacudió", "remezón"...), **o** la fuente es
   sismológica oficial (FUNVISIS/INAMEH).
2. El texto menciona colapso estructural, daños severos, heridos o
   fallecidos — sin importar la magnitud.

**Por qué el "Y" en la condición 1**: "sentido por la población" por sí
solo es casi automático en cualquier reporte de sismo (es casi un
requisito para que un medio lo reporte), así que no filtraría nada. Exigir
magnitud ≥4 además de "sentido" sí reduce el volumen real.

**Nota sobre la excepción de fuente oficial**: FUNVISIS/INAMEH hoy solo
están configurados como canales de Telegram en `config/sources.yaml`, y
la recolección de Telegram está deshabilitada en `main.py` (comentada) —
esta excepción no tiene efecto real todavía, queda lista para cuando se
reactive.

**Implementación**: `_sismo_sin_evidencia_fuerte()` en `verify_ai.py`,
mismo patrón que el filtro de vialidad — corre ANTES de la IA, no depende
de su juicio. Probado con 6 casos de ejemplo.

**Aplicado retroactivamente**: se evaluó la regla contra las 8 alertas de
sismo ya publicadas — las 8 quedarían excluidas (ninguna alcanza magnitud
4, ninguna con evidencia de daño real). Pendiente decidir si se eliminan
manualmente de los archivos (igual que se hizo con la alerta de vialidad).

---

## Bug encontrado: municipio homónimo del propio estado (26/07/2026)

Se reportó una alerta publicada como "Deslizamiento/Derrumbe en Parroquia
Barinas, Municipio Barinas, Barinas" — un municipio y una parroquia con el
mismo nombre que su propio estado, casi con certeza incorrectos.

**Causa**: el estado Barinas tiene un municipio "Barinas" y una parroquia
"Barinas" (común en capitales de estado venezolanas). La búsqueda directa
por nombre (agregada para resolver el caso "Guaicaipuro") solo excluía
nombres repetidos **entre estados distintos**, no nombres que coinciden
con el nombre de su **propio estado** — así que cualquier mención genérica
del estado ("Barinas y Mérida", "carretera Barinas-Mérida") se interpretó
como evidencia de ese municipio/parroquia específico. Además, una de las
tres fuentes del evento sí mencionaba el municipio real ("Municipio
Bolívar"), pero `agrupar_y_verificar` en `verify.py` toma el primer valor
no nulo entre las fuentes fusionadas, y la mención incorrecta de "Barinas"
llegó primero.

**Corrección**: `_buscar_nombre_directo()` ahora también descarta un
nombre si coincide con el nombre normalizado del propio estado. Con este
fix, el caso real vuelve a quedar en `municipio: null, parroquia: null`
(la mención explícita de "Municipio Bolívar" en el texto real no calzó
con el regex de coincidencia explícita porque no hay puntuación cercana
dentro de la ventana de 40 caracteres que exige `_MUNICIPIO_RE` — una
limitación preexistente, no introducida por este fix). Es el resultado
correcto: sin dato confiable, es mejor `null` que un valor incorrecto con
apariencia de certeza.

**Corregido retroactivamente**: se corrigió la alerta ya publicada
(`docs/data/noticias.json`, `data/historico_eventos.jsonl`), regenerando
su texto con `render.redactar_noticia()` para que el título y el cuerpo
también reflejen la ubicación corregida. El informe narrativo de
deslizamientos de julio no necesitó corrección — no afirmaba el
municipio/parroquia incorrectos, solo mencionaba "Barinas" de forma
genérica.

---

## Bug encontrado: republicación del mismo evento al cruzar la medianoche (26/27-07-2026)

Se reportó una segunda alerta sobre el mismo deslizamiento en la
carretera Barinas-Mérida (el mismo del bug anterior), pocas horas después
de la primera.

**Causa**: `state.py` deduplica eventos con la clave
`tipo::ubicacion::dia`, usando el día calendario de `evento["fecha_evento"]`
— que es la fecha de la fuente **más reciente** del grupo (calculado en
`verify_ai.py`). Una cobertura continua de varios días sobre el mismo
hecho (una vía bloqueada, en este caso) hace que esa fecha avance con
cada artículo de seguimiento; en cuanto cruzó la medianoche UTC (de 26 a
27 de julio), la clave de deduplicación cambió de día y el sistema lo
trató como un evento nuevo, aunque las fuentes originales seguían dentro
de la ventana de búsqueda de 12 horas.

**Corrección**: se agrega `fecha_evento_temprana` (la fuente **más
temprana** del grupo) en `verify_ai.py`, y `state.py` ahora ancla el día
de la clave de deduplicación a esa fecha en vez de a la más reciente —
se mantiene estable mientras la fuente original del hecho siga dentro de
la ventana de búsqueda, sin importar cuántos artículos de seguimiento
aparezcan después. `fecha_evento` (la más reciente) se sigue usando para
mostrar "🕒 Hecho reportado" en el texto de la alerta, sin cambios ahí.

**Corregido retroactivamente**: se eliminó la alerta duplicada más vieja
de `docs/data/noticias.json` y `data/historico_eventos.jsonl` (se
conservó la más reciente, que además esta vez sí detectó correctamente
"Municipio Bolívar"), y se corrigió manualmente el conteo del informe
narrativo de deslizamientos de julio (`total_eventos` de 3 a 2 — estaba
contando el mismo hecho dos veces).

---

## Dos alertas publicadas sin verificación de IA por agotamiento de cuota (27-07-2026)

Se reportaron dos alertas problemáticas publicadas en la misma corrida:

1. **"Deslizamiento/Derrumbe en La Guaira"**: el texto real era sobre las
   labores de rescate del terremoto anterior ("...tras el **doblete
   sísmico**, los rescatistas encontraron un autobús bajo los
   escombros..."), mal clasificado como un deslizamiento nuevo.
2. **"Salud pública en Portuguesa"**: un reportaje analítico nacional
   sobre el repunte de virus/enfermedades por las lluvias, no un evento
   agudo puntual.

**Causa común**: ambas fallaron su verificación de IA por **429 (rate
limit) de Groq** en una corrida con 13 eventos agrupados — la cuota se
agotó a mitad de camino, y la política de "no bloquear por falla técnica"
las publicó de todas formas (`estado_verificacion:
PASADO_POR_FALLA_TECNICA`).

**Causas específicas**:
- El caso 1 sí tenía un filtro determinista aplicable (`_PATRON_RETROSPECTIVA`
  ya busca "doble sismo"), pero el texto real decía **"doblete sísmico"**
  — una variante de redacción que el regex no cubría. Se amplió el patrón
  para cubrir "doblete sísmico"/"sismo doble" además de "doble sismo".
- El caso 2 no tiene ningún filtro determinista aplicable — depende
  enteramente del juicio semántico de la IA (distinguir un reportaje/
  análisis de un evento agudo), que no llegó a ejecutarse.

**Mitigación del agotamiento de cuota** (elegida: más reintentos +
más espaciado, sin rediseñar el prompt para agrupar llamadas): en
`verify_ai.py` y `build_informes.py`,
- `ESPERA_ENTRE_LLAMADAS_GROQ` sube de 1.5s a 3s entre cada llamada.
- `MAX_REINTENTOS_GROQ` sube de 2 a 3 intentos totales ante 429, con
  espera creciente (5s, 10s, 20s) en vez de un único reintento fijo de 5s.

Esto alarga la duración de cada corrida del monitor cuando hay muchos
eventos, a cambio de reducir la probabilidad de que la cuota se agote
antes de terminar de verificar todos los eventos de la corrida.

**Corregido retroactivamente**: se eliminaron ambas alertas de
`docs/data/noticias.json`, `data/historico_eventos.jsonl` y
`data/historico_fuentes_texto.jsonl`. El informe narrativo de salud
pública de julio se eliminó por completo (era el único evento de ese
tipo del mes); el de deslizamientos no necesitó tocarse — se había
generado antes de que apareciera la alerta de La Guaira.

---

## Prevención anticipada: demolición controlada en Playa Grande/Caraballeda (27-07-2026)

Se avisó, con varios días de anticipación, de una demolición controlada
programada de estructuras dañadas por el terremoto en Playa Grande y
Caraballeda (La Guaira) entre el 27 y el 31 de julio — con comisiones de
explosivos, derribo de edificaciones, y cobertura mediática esperable.
Riesgo identificado: la cobertura de esa demolición programada podía
calzar con las palabras clave de `explosion` y `colapso_estructural`
(tipos agregados esta misma sesión) y publicarse como si fuera una
emergencia nueva, cuando es un evento planificado y anunciado.

**Corrección preventiva** (antes de que ocurra, no reactiva): se
extendió el mecanismo de "contexto conflictivo" que ya existía solo para
`sismo` (evita que "cerco epidemiológico" se clasifique como sismo) a los
tipos `explosion` y `colapso_estructural`. Si el texto menciona
"demolición controlada/programada", "derribo controlado/programado", o
"voladura/detonación controlada/programada" — y no hay evidencia fuerte
de que sea un colapso/explosión real e inesperado ("colapso repentino",
"explosión accidental", heridos, fallecidos) — el tipo se descarta para
esa mención.

Probado: un colapso/explosión real (con heridos, sin mención de
demolición programada) se sigue detectando con normalidad; la misma
redacción en contexto de demolición controlada anunciada ya no se
clasifica como emergencia.

---

## Ventana de 36 horas para correlacionar el mismo evento entre corridas (27-07-2026)

Se reportó un tercer patrón de duplicación, distinto a los dos anteriores
(Barinas, La Guaira): dos medios reportaron **la misma noticia real** (una
niña ahogada por la crecida del río La Miel en Lara) con **más de 6 horas
de diferencia** entre sí (Noticia al Día, 26/07 18:07; El Pitazo, 27/07
00:41). A diferencia del caso Barinas, estos dos artículos nunca se
agruparon juntos en la misma corrida (`agrupar_y_verificar` en
`verify.py`) — para cuando salió el segundo, el primero ya había quedado
fuera de la ventana de búsqueda de 12 horas (`ventana_horas_fuentes`), así
que cada uno generó su propio evento independiente, con su propia clave de
deduplicación (día 26 vs. día 27).

**Corrección**: se agrega `_resolver_clave()` en `state.py` — antes de
generar una clave nueva, revisa si ya existe un evento publicado del
**mismo tipo + misma ubicación** cuya fuente más temprana esté dentro de
una ventana de **36 horas**; si existe, reutiliza esa clave (se trata como
el mismo evento, no uno nuevo). `marcar_publicados()` ahora también
guarda `fecha_evento_temprana` en `data/publicados.json`, necesaria para
esta comparación.

**Excepciones explícitas, a pedido**: `sismo` (tiene su propio mecanismo
de correlación cruzada por magnitud/ubicación,
`_mismo_sismo_ya_publicado`) y **`orden_publico`** — durante disturbios,
el mismo tipo+ubicación puede repetirse genuinamente día a día (una
protesta nueva cada día en el mismo lugar no es "el mismo evento" solo
porque coincide tipo+ubicación), así que aplicar la ventana de 36h ahí
ocultaría eventos reales distintos.

Probado: dos reportes de inundación en Lara con 6.5h de diferencia ahora
se tratan como el mismo evento; dos reportes de `orden_publico` en el
mismo estado con 24h de diferencia siguen tratándose como eventos
distintos (comportamiento intencional).

**Corregido retroactivamente**: se eliminó la alerta duplicada
("Inundación en Lara", sin municipio/parroquia detectados) de
`docs/data/noticias.json`, `data/historico_eventos.jsonl`,
`data/historico_fuentes_texto.jsonl` y la clave sobrante en
`data/publicados.json` — se conservó la versión con más detalle
("Parroquia Gustavo Vegas León, Municipio Simón Planas"). El informe
narrativo de inundaciones de julio no necesitó corrección, se había
generado antes de que apareciera el duplicado.

---

## Bug de severidad: "perdió la vida" no disparaba severidad crítica (27-07-2026)

Se reportó la alerta "Inundación en Parroquia Gustavo Vegas León..." con
severidad "sin clasificar", pese a que el texto real de la fuente decía
*"una menor de edad perdió la vida por inmersión tras ser arrastrada por
una crecida súbita del río La Miel"* — una muerte real.

**Causa**: `config/keywords.yaml` solo tenía "fallecido(s)", "muerto(s)" y
"víctimas fatales" como palabras clave de severidad "crítico" — ninguna
cubre el eufemismo periodístico "perdió la vida", ni las formas verbales
"murió"/"falleció" (solo estaban las formas de participio/sustantivo).

**Corrección**: se agregan "falleció"/"fallecieron", "murió", "perdió la
vida"/"perdieron la vida" a la lista de severidad crítico.
Deliberadamente **no** se agregó el verbo "muere" a secas (como en el
título "Niña muere ahogada...") por riesgo de falsos positivos con usos
metafóricos ("el optimismo no muere", etc.) — el cuerpo del texto suele
tener una frase más explícita ("perdió la vida", "falleció") que sí
alcanza para clasificar correctamente sin necesidad de esa palabra
suelta.

Probado: el texto real ahora clasifica como "crítico"; un caso con
negación ("no falleció nadie...") sigue sin disparar severidad crítica.

**Corregido retroactivamente**: se actualizó la severidad de la alerta ya
publicada a "crítico" en `docs/data/noticias.json` (regenerando su texto),
`data/historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl` y
`data/publicados.json`.

---

## Garantizar que los informes narrativos nunca omitan eventos con daños/heridos/fallecidos (27-07-2026)

Se reportó que el informe "Todas las categorías" de julio no mencionaba
la tormenta eléctrica con 9 heridos en el aeropuerto de Valencia
(Carabobo) — un evento con severidad "alto" que quedó fuera de la
narrativa entre otros eventos más leves del mismo período. Retomaba el
pendiente ya anotado el 26/07 sobre "énfasis temático" del prompt.

**Corrección** en `build_informes.py`:
- Se agrega `SEVERIDADES_QUE_DEBEN_MENCIONARSE = {"alto", "critico"}` — un
  evento con esa severidad ya significa, por definición de
  `config/keywords.yaml`, que hubo daños materiales, heridos o víctimas
  fatales.
- `_construir_bloque_eventos_obligatorios()` arma una lista explícita de
  esos eventos (tipo, ubicación, fuente) y la agrega al prompt bajo el
  encabezado "EVENTOS QUE DEBEN MENCIONARSE EXPLÍCITAMENTE" — no depende
  de que la IA los note por su cuenta entre el resto de fuentes.
- `_construir_prompt_fuentes()` ahora prioriza las fuentes de esos eventos
  graves primero al ordenar, para que no queden fuera del corte de
  `MAX_FUENTES_POR_INFORME` (40) en períodos con muchos eventos.
- El `SYSTEM_PROMPT` se actualiza con una regla explícita: mencionar cada
  evento de esa lista es el criterio más importante de la tarea, sin
  importar cuántos eventos leves haya.
- Se agrega un chequeo de auditoría (no bloqueante) después de generar la
  narrativa: si el nombre de la fuente de un evento obligatorio no
  aparece en el texto generado, se deja constancia en el log
  (`[WARN] ... la narrativa no mencionó estos eventos...`) para revisión,
  sin fallar la generación — reintentar no garantiza mejor resultado, y
  un informe con el resto del contenido sigue siendo mejor que ninguno.

Probado con un caso que reproduce el problema real (tormenta eléctrica
con heridos + inundación leve): el evento grave queda identificado como
obligatorio, priorizado en el orden de fuentes, y el chequeo de auditoría
detecta correctamente cuando una narrativa simulada lo omite.

No se regeneró manualmente el informe "general" de julio ya publicado —
al ser el período en curso, se regenera solo (como máximo 1 vez al día)
en la próxima corrida del monitor, y ya incorporará esta corrección.

---

## Jerarquía real municipio→parroquia con datos oficiales del INE (27-07-2026)

Se reportó la alerta "Tormenta eléctrica en Parroquia Guajira, Municipio
Cabimas, Zulia" — una combinación que no existe: "Guajira" es una
parroquia del municipio **"Indígena Bolivariano Guajira"**, no de
Cabimas.

**Causa raíz**: `config/ubicaciones_detalle.json` guardaba, por estado,
dos listas planas independientes (`municipios` y `parroquias`) sin
relación jerárquica entre sí. `classify.py` detectaba municipio y
parroquia por separado — a veces de fuentes *distintas* dentro del mismo
evento agrupado — y los combinaba sin verificar que la parroquia
realmente perteneciera al municipio detectado. Al investigar se encontró
que esta clase de colisión de nombres (un municipio y una parroquia
compartiendo nombre) es la norma, no la excepción, en casi todos los
estados venezolanos.

**Corrección**: el usuario proporcionó el archivo oficial de códigos de
división político-territorial del INE (formato COD-AB/PCode: estado →
municipio → parroquia, 1135 filas, 24 estados). Se reconstruyó
`ubicaciones_detalle.json` con la jerarquía real anidada:
`{estado: {"municipios": {municipio: {"parroquias": [...], "alias":
"..."}}}}`. Los 9 alias de nombre corto ya identificados antes
(Guaicaipuro, Angostura, etc.) se preservaron y coinciden exactamente con
los nombres oficiales largos del archivo del INE.

`classify.py` se reescribió para respetar la jerarquía:
- Si el municipio ya se determinó (por regex explícito o por nombre
  directo), la parroquia solo se acepta si **realmente pertenece a ese
  municipio** — si el texto menciona una parroquia de otro municipio, se
  descarta en vez de asumir que el municipio está mal.
- Si el municipio aún no se conoce, una parroquia mencionada directamente
  solo se acepta si es **única en todo el país** (un solo estado, y
  dentro de ese estado un solo municipio) — en cuyo caso también se
  infiere el municipio correcto a partir de ella.
- Se descubrió que algunas parroquias se repiten dentro del **mismo**
  estado bajo municipios distintos (ej. "San José" en Trujilo y Zulia) —
  el chequeo de unicidad ahora cubre también ese caso, no solo la
  ambigüedad entre estados distintos.

`verify_ai.py` (`_listas_ubicacion_valida`, usado para que la IA infiera
ubicación cuando el regex no encuentra nada) se actualizó para aplanar la
nueva estructura anidada en las dos listas simples que ese prompt
necesita — no valida la relación municipio/parroquia en ese camino
(alcance menor, la detección determinista en `classify.py` sí la
respeta).

Probado contra el caso real reportado (ya no combina Cabimas con
Guajira) y contra todos los casos de regresión ya validados antes
(Petare, Guaicaipuro, Angostura, Baruta, "Parroquia Altamira, Municipio
Bolívar, Barinas") — ninguno se rompió. También se corrió contra el
histórico completo de fuentes ya publicadas en producción para revisar
el resultado en volumen, sin encontrar más combinaciones inconsistentes.

**Advertencia honesta**: el archivo del INE no es infalible por sí
mismo (podría tener errores puntuales en municipios/parroquias poco
documentados), pero es sustancialmente más confiable que la ausencia
total de jerarquía que había antes.

---

## División de artículos multiestado en alertas independientes (27-07-2026)

El usuario preguntó: si un artículo describe la situación de lluvias en 5
municipios distintos, con detalles propios de heridos/daños en cada uno,
¿el sistema genera 5 alertas? La respuesta era **no**: `detectar_ubicacion`
solo devolvía el primer estado que encontraba en el texto y descartaba el
resto, y `detectar_severidad` se calculaba sobre el texto **completo** del
artículo — así que incluso el único estado elegido podía heredar
severidad de hechos ocurridos en otro estado mencionado más adelante.

**Corrección implementada** (`scripts/classify.py`):
- `detectar_ubicacion(texto)` ahora devuelve una **lista** de todos los
  estados detectados (antes devolvía solo el primero), cada uno con su
  propia ventana de proximidad de texto cuando aplica.
- `clasificar_item(item)` ahora devuelve una **lista** de items — uno por
  cada estado detectado con evidencia propia cerca — en vez de un único
  item. `tipos` y `severidad` se calculan para cada estado usando
  **solo su propia ventana de texto**, no el artículo completo.
- `main.py` y `fetch_email.py` se actualizaron para aplanar/adaptar esta
  nueva firma de lista.
- Se añadió `_posiciones_de_estados()`, que ubica las posiciones de
  **todas** las menciones de estados en el texto. `_ventana_cerca()` usa
  esas posiciones para **recortar** la ventana de proximidad de cada
  estado en la mención más cercana de otro estado distinto (antes o
  después), evitando que la ventana de un estado se extienda sobre el
  párrafo dedicado a otro.

**Prueba con caso simulado** (Zulia con heridos, Táchira con
deslizamiento sin daños, Mérida con anegaciones menores): sin el recorte
de ventana, los 3 estados resultaban con severidad "alto" y ambos tipos
mezclados. Con el recorte, Zulia mantiene correctamente severidad "alto"
(por "heridos") y Mérida baja a "bajo" con un solo tipo — la separación
mejora sustancialmente pero no es perfecta: cuando la oración de
transición entre dos estados menciona palabras clave de tipo (ej.
"inundaciones" en la frase que conecta la mención de Zulia con la de
Táchira), esas palabras pueden seguir cayendo dentro de la ventana del
segundo estado por estar posicionalmente más cerca de él que de
cualquier otro corte. Esto es una limitación inherente del enfoque
heurístico basado en proximidad de palabras (ya advertida al usuario
antes de implementar) — no hay reconocimiento real de qué frase
"pertenece" a qué estado, solo distancia y recorte en los puntos de
mención de otros estados.

**Prueba de regresión** contra el histórico real de textos de fuentes ya
publicados (`data/historico_fuentes_texto.jsonl`): de 23 fuentes
individuales evaluadas, 7 (30%) resultaron en división multiestado real
y coherente con el contenido del artículo (p.ej. una nota sobre lluvias
que cubre Caracas y La Guaira a la vez, u otra sobre el corredor
Barinas–Mérida) — casos que antes de este cambio habrían generado una
sola alerta con la ubicación del primer estado mencionado nada más.

**Relación con la deduplicación de 36 horas**: son mecanismos
independientes y complementarios. La división multiestado ocurre en
`classify.py`, antes de que el evento llegue a la ventana de 36 horas de
`state.py` (que actúa por tipo + ubicación ya resuelta). Un artículo que
cubre 3 estados generará 3 eventos con ubicaciones distintas, cada uno
sujeto de forma independiente a la regla de las 36 horas frente a
publicaciones previas sobre ese mismo estado — no se pierde ni se duplica
cobertura por la interacción entre ambos mecanismos.

Validado con `python3 scripts/validar_configs.py` (OK) y contra los
casos de regresión de detección de ubicación ya probados en sesiones
anteriores.

---

## Corrección retroactiva: alerta previa a la reconstrucción del INE (27-07-2026)

El usuario reportó que seguía viendo "Parroquia Guajira, Municipio
Cabimas" publicado en el sitio, a pesar de la corrección de la jerarquía
municipio→parroquia (PR #61, fusionado a las 16:49 UTC). Al revisar la
alerta, se confirmó que fue detectada a las 16:02 UTC — **antes** de que
el fix llegara a `main` — por lo que quedó publicada con el dato
incorrecto generado por el código anterior. No es una recurrencia del
bug, sino un dato ya publicado que no se había corregido de forma
retroactiva.

**Corrección**: se actualizó manualmente `docs/data/noticias.json` y
`data/historico_eventos.jsonl` para reflejar el municipio correcto
("Indígena Bolivariano Guajira" en vez de "Cabimas"), y se regeneró
`docs/data/estadisticas.json` con `python3 scripts/build_dashboard.py`.
`data/historico_fuentes_texto.jsonl` no requería cambio (no guarda
municipio). No se encontraron informes narrativos que mencionaran esta
combinación incorrecta.

---

## Bug: la IA inventaba municipio/parroquia sin base en el texto (27-07-2026)

Se reportó la alerta "Colapso estructural en Parroquia San Francisco,
Municipio Maracaibo, Zulia", pero los hechos reales ocurrieron en otro
municipio/parroquia distinto.

**Causa raíz**: la fuente de esta alerta es un resumen de RSS truncado
("Niño de cinco años mueres tras colapso de vivienda en Zulia... Un fatal
incidente se registró luego de que una vivienda colapsara, como…") que
**no menciona ningún municipio ni parroquia**. Cuando `classify.py` (regex
determinista) no logra determinar el municipio/parroquia, `verify_ai.py`
le pide a la misma llamada de verificación de Groq que intente inferirlo
del texto, restringido a una lista de valores válidos del estado, con
instrucción explícita de responder `null` si no hay certeza. En este
caso, la IA respondió con un municipio/parroquia plausible pero **no
respaldado por el texto real** — el modelo no siguió la instrucción de
abstenerse cuando no hay evidencia.

**Corrección** (`scripts/verify_ai.py`): se agregó una verificación
determinista posterior a la respuesta de la IA — el municipio y la
parroquia que proponga solo se aceptan si su nombre **aparece
textualmente** (normalizado, sin tildes/mayúsculas) en el texto combinado
de las fuentes del evento. Si no aparece, se descarta y el campo queda en
`null`, igual que si la IA no hubiera podido determinarlo. Esto no
depende de que el modelo obedezca la instrucción del prompt — es un
chequeo de anclaje textual que no puede pasarse por alto aunque la IA
alucine.

**Corrección retroactiva**: se quitó el municipio/parroquia inventado
("Maracaibo"/"San Francisco") de la alerta ya publicada en
`docs/data/noticias.json` y `data/historico_eventos.jsonl`, dejando la
ubicación en el nivel de estado ("Zulia") que sí está respaldado por el
texto, y se regeneraron las estadísticas.

**Nota pendiente**: al revisar esta alerta también se notó que la
severidad quedó "sin_clasificar" a pesar de que el título de la fuente
menciona la muerte de un niño de cinco años ("mueres" — probable error
tipográfico de "muere" en el sitio de origen). El detector de palabras
clave de severidad crítica no cubre esa variante ortográfica; queda para
evaluar por separado si conviene tolerar errores tipográficos comunes en
las palabras clave de severidad más grave.

---

## Corrección de raíz: resúmenes RSS truncados ocultaban ubicación y gravedad (27-07-2026)

Seguimiento del caso anterior: el usuario mostró que el artículo original
sí menciona claramente "municipio Guajira" (y, en el cuerpo completo,
"parroquia Sinamaica") y que un niño de cinco años murió — datos que el
sistema no capturó.

**Causa raíz real** (más profunda que el caso anterior): `fetch_rss.py`
nunca descarga la página del artículo — solo usa el campo `summary` que
entrega el feed RSS, que muchos medios truncan a una o dos frases
seguidas de puntos suspensivos. En este caso el resumen terminaba en "...
como…", cortando la oración justo antes de "en el municipio Guajira del
estado Zulia" y de "murió". El texto real y completo de la página sí
contiene todo: ubicación exacta y la muerte. El bug de municipio/parroquia
inventados del apartado anterior era, en el fondo, sÍntoma de este
problema más amplio: sin texto suficiente, ni la IA ni el clasificador
determinista tenían con qué determinar la ubicación real ni la severidad
real.

**Corrección** (`scripts/fetch_rss.py`): se agregó `_obtener_texto_completo(link)`,
que descarga la página del artículo (usando `requests` + `BeautifulSoup`,
nueva dependencia `beautifulsoup4`/`lxml` en `requirements.txt`) y extrae
el texto de sus párrafos (`<article>` o el primer contenedor con "content"
en su clase, si existe; si no, todos los `<p>` de la página), limitado a
4000 caracteres. Se agregó `_TRUNCADO_RE`, que detecta cuando el resumen
del RSS termina en puntos suspensivos ("…" o "[...]"), y **solo en esos
casos** se reemplaza el resumen truncado por el texto completo de la
página. Si la descarga falla por cualquier razón (red, sitio caído,
estructura HTML inesperada), se sigue usando el resumen truncado en vez
de fallar la corrida completa — el mismo patrón de "fallar hacia lo
seguro" ya usado en el resto del pipeline.

**Bug adicional encontrado al probar con el texto completo real**: con el
texto completo, la ubicación y el municipio/parroquia se detectaron bien,
pero la severidad seguía saliendo "sin_clasificar" a pesar de que "murió"
aparecía a solo 4 palabras de "Zulia". La causa: el recorte de ventana de
proximidad agregado en el fix de artículos multiestado (que corta la
ventana en la mención más cercana de OTRO estado) también se activaba
entre **dos menciones del mismo estado** — el artículo menciona "Zulia"
una vez como ubicación y otra vez como parte del nombre de un medio local
("Zulia Sin Censura"), y la ventana se cortaba justo antes de esa segunda
mención, dejando "murió" fuera. Se corrigió `_ventana_cerca()` en
`scripts/classify.py` para que el recorte solo considere menciones de
estados **distintos** al que se está evaluando, nunca repeticiones del
mismo estado. Se confirmó que esto no afecta el caso de prueba
multiestado ya validado (Zulia/Táchira/Mérida en un mismo artículo).

**Corrección retroactiva**: se actualizó la alerta ya publicada
("Colapso estructural") en `docs/data/noticias.json` y
`data/historico_eventos.jsonl` con el municipio ("Indígena Bolivariano
Guajira"), la parroquia ("Sinamaica") y la severidad ("crítico")
correctos, y se regeneraron las estadísticas. El informe narrativo
mensual ya generado no mencionaba una ubicación incorrecta, así que no
requirió corrección.

Validado con `python3 scripts/validar_configs.py`, con el caso real
reportado por el usuario (texto completo obtenido manualmente de la
página del artículo) y con regresión contra
`data/historico_fuentes_texto.jsonl` (mismo número de divisiones
multiestado que antes del cambio en `_ventana_cerca`, sin regresiones).

---

## Bug: parroquia inventada cuando coincide con el nombre del municipio (27-07-2026)

El usuario preguntó de dónde salía "Parroquia Guajira" en la alerta de
tormenta eléctrica, ya que ninguna fuente menciona explícitamente
"parroquia Guajira" (solo dicen "municipio Guajira").

**Causa raíz**: en Venezuela es muy común que la parroquia "capital" de un
municipio comparta el mismo nombre que el municipio (o, en este caso, el
alias corto del municipio: "Guajira" es alias de "Indígena Bolivariano
Guajira", y ese municipio tiene una parroquia también llamada "Guajira").
`_buscar_parroquia_directa()` en `classify.py`, al buscar el nombre de una
parroquia mencionado directamente en el texto (sin la palabra
"parroquia" delante) dentro de las parroquias del municipio ya conocido,
no excluía el caso en que el nombre de la parroquia coincidiera con el
nombre/alias del propio municipio — así que la misma palabra que ya se
había usado para identificar el municipio ("Guajira") se reutilizaba
como si fuera evidencia independiente de esa parroquia específica, sin
que el texto lo dijera en realidad.

Se confirmó que este patrón (parroquia homónima al municipio) es muy
extendido: aparece en Barinas, Aragua, Táchira, Falcón, Trujillo, Zulia,
Miranda, Monagas, Yaracuy y otros estados — decenas de municipios donde
la "parroquia capital" lleva el mismo nombre. La alerta ya publicada
"Inundación en Parroquia Bocono, Municipio Bocono, Trujillo" tenía el
mismo problema: la fuente solo dice "municipios Boconó y Vicente Campo
Elías", nunca "parroquia Boconó".

**Corrección** (`scripts/classify.py`, `_buscar_parroquia_directa`): al
buscar una parroquia por coincidencia directa de nombre (sin la palabra
"parroquia" delante) dentro de las parroquias del municipio ya conocido,
ahora se excluye cualquier parroquia cuyo nombre normalizado coincida con
el nombre canónico o el alias del propio municipio. La detección
**explícita** ("parroquia X" con la palabra delante) no se ve afectada —
sigue aceptando la parroquia homónima si el texto realmente la nombra así
(se probó con "parroquia Guajira, municipio Indígena Bolivariano
Guajira" como caso de control).

**Corrección retroactiva**: se quitó la parroquia inferida sin base
("Guajira" y "Bocono" respectivamente) de las dos alertas ya publicadas
afectadas, dejando el municipio (que sí está bien respaldado) y
`parroquia: null`, y se regeneraron las estadísticas.

Validado con `python3 scripts/validar_configs.py`, con el caso real y de
control, y con regresión contra `data/historico_fuentes_texto.jsonl`
completo (ningún otro caso legítimo con parroquia explícita, como
"Parroquia Altamira, Municipio Bolívar, Barinas", se vio afectado).

---

## Revisión general de alertas activas + resumen de medidas preventivas (27-07-2026)

A pedido del usuario, se revisaron todas las alertas publicadas en `main`
buscando otros errores. Se encontró una alerta duplicada: "Inundación en
Parroquia Antimano, Distrito Capital" aparecía dos veces (26/07, 11:46
a.m. y 4:04 p.m.), con datos distintos entre sí (una sin municipio y
severidad "bajo", otra con municipio "Libertador" y severidad "sin
clasificar") — ambas del mismo evento real de lluvias en Caracas. Se
confirmó que **no es un bug activo hoy**: ambas entradas son anteriores
a la fusión del fix de ventana de 36 horas para deduplicar entre corridas
(PR #56, fusionado 27/07 15:41 UTC) — datos residuales de antes de esa
protección, nunca reprocesados. Se eliminó la entrada más antigua e
incompleta de `docs/data/noticias.json`, dejando la más completa
(con municipio correcto).

### Resumen de medidas preventivas contra esta clase de errores (municipio/parroquia/severidad incorrectos)

En esta sesión se identificaron y corrigieron, de raíz, los siguientes
mecanismos que causaban ubicación o severidad incorrecta:

1. **Jerarquía real INE** (`config/ubicaciones_detalle.json`): antes no
   existía relación municipio→parroquia; ahora se usa el archivo oficial
   de códigos del INE, y `classify.py` solo acepta una parroquia si
   realmente pertenece al municipio ya determinado.
2. **Grounding de la IA**: cuando el regex no puede determinar
   municipio/parroquia y se le pide ayuda a la IA (Groq), su respuesta
   solo se acepta si el nombre propuesto aparece **textualmente** en las
   fuentes — nunca se confía en que el modelo obedezca la instrucción de
   responder `null` sin verificarlo.
3. **Texto completo del artículo**: `fetch_rss.py` ahora descarga la
   página del artículo cuando el resumen del RSS viene truncado, en vez
   de clasificar con un fragmento que puede omitir la ubicación exacta o
   los detalles de gravedad (heridos, muertes).
4. **Ventana de proximidad entre estados repetidos**: el recorte de
   ventana para artículos multiestado ya no corta contenido relevante
   (p.ej. una palabra de severidad) cuando el "otro estado" detectado es
   en realidad una repetición del mismo estado (p.ej. el nombre de un
   medio local).
5. **Parroquia homónima al municipio**: ya no se infiere una parroquia
   solo porque su nombre coincide con el del municipio (o su alias) ya
   conocido — se exige mención explícita ("parroquia X") para ese caso
   específico, dado lo común que es este patrón de nombres en Venezuela.

Estas cinco correcciones atacan causas de raíz distintas pero
relacionadas (todas dentro del pipeline de detección de
ubicación/severidad), no parches puntuales para casos individuales — se
espera que prevengan la aparición de la misma clase de error en textos
futuros con estructura similar, aunque no eliminan por completo la
posibilidad de error dado el enfoque heurístico (no hay comprensión
semántica real del texto, solo patrones y proximidad de palabras).

---

## Acceso al correo institucional: diagnóstico y herramienta de setup (27-07-2026)

El usuario reportó que el sistema no logra autenticarse con Outlook
(`fetch_email.py`), con el error de Azure AD "AADSTS900144: The request
body must contain the following parameter: 'refresh_token'". Este canal
es importante porque las filiales regionales de la Cruz Roja reportan
incidentes de sus zonas de influencia por ese correo.

**Diagnóstico**: el error indica que el secreto `OUTLOOK_REFRESH_TOKEN`
en GitHub Actions está vacío o inválido — no es un bug de código. La
autenticación usa `msal.PublicClientApplication.acquire_token_by_refresh_token()`,
que requiere un `refresh_token` vigente obtenido previamente mediante un
login interactivo (no se puede generar sin que un humano inicie sesión
con la cuenta del buzón institucional o una cuenta delegada con acceso a
él).

**Acción**: se agregó `scripts/generar_refresh_token_outlook.py`, una
herramienta de uso manual (no se ejecuta en el workflow automático) que
usa el flujo de dispositivo (`device code flow`) de MSAL para obtener un
refresh_token nuevo de forma interactiva. El usuario la ejecutará
localmente con `OUTLOOK_CLIENT_ID`/`OUTLOOK_TENANT_ID` ya configurados,
iniciará sesión con la cuenta del correo institucional cuando el script
lo indique, y actualizará el secreto `OUTLOOK_REFRESH_TOKEN` en GitHub
con el resultado.

**Próximo paso** (una vez que la lectura de correos funcione): definir
qué información extraer del cuerpo de esos correos y cómo integrarla al
resto del pipeline — hoy `fetch_email.py` solo entiende un formato rígido
de asunto (`EMERGENCIA | Estado | Tipo | Severidad`), que probablemente
no es como las filiales reportan en la práctica. Queda pendiente de
discutir.

---

## Dos falsos positivos más: incendio vehicular aislado y "manifestaciones artísticas" (27-07-2026)

El usuario reportó una alerta de "Incendio en Municipio Araure,
Portuguesa" que en realidad era un camión (gandola) incendiado en la
autopista — un incidente vehicular rutinario, no una emergencia del tipo
que le compete a la Cruz Roja.

**Causa raíz**: no existía un filtro determinista para tipo=incendio
análogo al de vialidad — dependía enteramente del juicio de la IA. Además,
esta alerta específica se publicó por una falla técnica temporal de Groq
(`estado_verificacion: "PASADO_POR_FALLA_TECNICA"`, el mecanismo
intencional de "fallar hacia lo seguro" para no perder eventos reales
cuando la IA no está disponible), saltándose incluso esa verificación.

**Corrección** (`scripts/verify_ai.py`): se agregó
`_incendio_vehiculo_sin_evidencia_fuerte()`, un filtro determinista que
corre ANTES de la llamada a la IA (así que no depende de que Groq esté
disponible). Solo aplica cuando el texto menciona un vehículo (camión,
gandola, carro, moto, autobús, etc.) — un incendio forestal o estructural
no se ve afectado. A pedido explícito del usuario, la condición para NO
descartar la alerta es estricta: el texto debe describir el hecho como un
**accidente múltiple Y** mencionar **heridos o fallecidos**, ambas cosas
a la vez (no basta una sola, a diferencia del filtro de vialidad que
acepta cualquiera de varias señales).

**Segundo hallazgo, al revisar el histórico durante esta corrección**: se
encontró OTRA alerta con el mismo patrón de falla técnica —
"Orden público en Municipio Barinas, Barinas"— que resultó ser un
**falso positivo total**: la fuente es una noticia sobre la
reinauguración de un teatro y entrega de equipos tecnológicos, sin
ninguna relación con disturbios. La causa: la palabra clave
"manifestaciones" (para protestas) hizo falso match con "las
manifestaciones artísticas" (exposiciones/actos culturales) mencionadas
en el texto — la misma clase de ambigüedad idiomática ya identificada
antes para "explosión" (que colisiona con "explosión de alegría/color").

**Corrección** (`config/keywords.yaml`): se quitó "manifestacion"/
"manifestaciones"/"manifestación" como palabra suelta de
`orden_publico`, reemplazada por "manifestantes" (sin la ambigüedad, ya
que "manifestantes artísticos" no es una expresión de uso común) y
frases específicas ("manifestación violenta", "manifestación callejera",
"marcha de protesta").

**Corrección retroactiva**: se eliminaron ambas alertas
(`docs/data/noticias.json`, `data/historico_eventos.jsonl`,
`data/historico_fuentes_texto.jsonl`) y se regeneraron las estadísticas.

Validado con `python3 scripts/validar_configs.py`, casos de control para
ambos filtros (incendio vehicular con/sin accidente múltiple y víctimas;
"manifestaciones artísticas" vs. "manifestantes" en protesta real), y
regresión contra el histórico completo de fuentes (sin otros casos de
`incendio`/`orden_publico` afectados).

---

## Bug de raíz: actualizaciones de un evento creaban una alerta duplicada (28-07-2026)

Al revisar manualmente las alertas del día se encontró un duplicado real:
"Inundación en Lara" (sin municipio, severidad sin clasificar) y
"Inundación en Parroquia Gustavo Vegas León, Municipio Simón Planas,
Lara" (severidad crítico) resultaron ser el mismo evento real (una niña
que murió ahogada en el río La Miel), reportado por dos fuentes
distintas, publicado con 26 horas de diferencia — **dentro** de la
ventana de 36 horas que debería haberlo evitado.

**Causa raíz** (más profunda que un simple fallo de la ventana de 36h):
`state.py` sí resuelve correctamente la misma `clave` de deduplicación
para ambos eventos (mismo tipo+ubicación dentro de la ventana). Pero
`filtrar_nuevos()` trata intencionalmente como "nuevo" cualquier evento
cuya severidad o estado de confirmación cambien respecto a lo ya
publicado bajo esa clave — para poder notificar actualizaciones
legítimas (p.ej. un evento que sube de severidad al confirmarse más
daño). El problema: `build_site.py` (`actualizar_datos_sitio`) simplemente
**agregaba** cada noticia nueva al principio de la lista, sin nunca
reemplazar la entrada anterior del mismo evento — así que cada
"actualización" terminaba como una alerta visualmente independiente en
el sitio, no como una corrección de la anterior.

**Corrección**:
- `state.py`: `filtrar_nuevos()` ahora anota cada evento devuelto con su
  `clave_dedup` (la misma clave de `_resolver_clave`), tanto para
  eventos genuinamente nuevos como para actualizaciones.
- `build_site.py`: `actualizar_datos_sitio()` ahora, antes de agregar las
  noticias nuevas, quita del listado existente cualquier entrada cuya
  `clave_dedup` coincida con una de las nuevas — así una actualización
  **reemplaza** la alerta anterior del mismo evento en vez de sumarse
  como una segunda alerta. Las noticias ya publicadas antes de este
  cambio no tienen `clave_dedup` y no se ven afectadas (se conservan
  igual).

**Bug adicional encontrado en el mismo caso**: la fuente de la segunda
publicación ("Niña muere ahogada...") tampoco disparó severidad
crítica, porque "ahogado"/"ahogada" no estaba en las palabras clave de
severidad crítica (`config/keywords.yaml`). Se agregó junto con sus
formas plurales.

**Corrección retroactiva**: se fusionaron las dos alertas de Lara en una
sola (ubicación completa, severidad crítico, 2 fuentes, confirmado) en
`docs/data/noticias.json`, `data/historico_eventos.jsonl` y
`data/historico_fuentes_texto.jsonl`, y se regeneraron las estadísticas.

Validado con `python3 scripts/validar_configs.py` y con una prueba
directa de `state.py`/`build_site.py` simulando una actualización de
severidad para el mismo evento (confirmando que ambas pasadas comparten
la misma `clave_dedup`).

---

## Pendiente para retomar (28-07-2026)

Quedaron dos tareas pausadas a pedido del usuario, para continuar cuando
tenga la lista de correos de las filiales:

1. **Filtro por remitente en Power Automate**: el flujo
   "AlertaCRV - Reenvío de correos a GitHub" ya está armado y probado
   (dispara con cualquier correo nuevo → crea un issue en
   `alertacrv/alerta-crv-24-` con Asunto/Cuerpo del correo). Falta
   configurar el filtro del disparador para que solo entren correos de
   las cuentas de las filiales autorizadas a reportar.
2. **`scripts/fetch_github_issues.py`** (no implementado aún): leer los
   issues nuevos del repositorio vía la API de GitHub y alimentarlos al
   pipeline de clasificación (`classify.py`), igual que hace
   `fetch_rss.py`/`fetch_email.py` hoy. El cuerpo de los issues llega con
   HTML crudo (`<br>`, enlaces) del cliente de correo — hay que limpiarlo
   igual que ya hace `_limpiar_texto()` en `fetch_rss.py`.

---

## Auditoría diaria autónoma: tres errores de clasificación (28-07-2026)

Auditoría de rutina (sin que el usuario la pidiera) de todas las alertas
publicadas en `main` en las últimas ~36 horas, comparando cada una contra
el texto real de sus fuentes en `data/historico_fuentes_texto.jsonl`. Se
encontraron y corrigieron tres errores de clasificación, todos con causa
raíz distinta.

### 1. Severidad ignoraba "lesionados" como sinónimo de "heridos"

La alerta "Deslizamiento/Derrumbe en Municipio Libertador, Distrito
Capital" quedó con severidad "sin_clasificar" pese a que su única fuente
("Paso de la Onda Tropical N.º 30 causa anegaciones, derrumbes y
**lesionados** en Caracas y varios estados") sí reporta heridos.

**Causa raíz**: `config/keywords.yaml` (severidad `alto`) solo tenía
"heridos", no "lesionados"/"lesionadas"/"lesionado"/"lesionada" — un
sinónimo de uso muy común en la prensa venezolana. `verify_ai.py` ya
trataba ambas palabras como equivalentes en sus propios filtros
deterministas (vialidad, incendio), pero `classify.py`
(`detectar_severidad`) no.

**Corrección** (`config/keywords.yaml`): se agregaron las cuatro formas de
"lesionado" a la lista de severidad `alto`.

**Corrección retroactiva**: se actualizó la severidad a "alto" (y se
regeneró `titulo`/`texto` con `render.redactar_noticia()` para que el
mensaje publicado sea idéntico al que generaría el pipeline real) en
`docs/data/noticias.json`, `data/historico_eventos.jsonl` y
`data/historico_fuentes_texto.jsonl`, y se regeneraron las estadísticas.

### 2. "Derrumbe" también significa colapso de pared/muro, no solo deslizamiento de tierra

La alerta "Deslizamiento/Derrumbe en Municipio Ospino, Portuguesa" resultó
ser un falso positivo total: la fuente ("Filtraciones y humedad generan
colapso parcial en iglesia San Fernando Rey de Ospino") describe el
colapso de una pared junto al campanario de una iglesia, causado por
filtraciones de agua y humedad acumulada **durante años** — ningún
deslizamiento de tierra, ninguna lluvia, nada relacionado con el tipo
"deslizamiento" que el sistema le asignó.

**Causa raíz**: la palabra "derrumbe" (palabra clave de tipo=deslizamiento
en `config/keywords.yaml`) se usa en español tanto para un deslizamiento
de tierra como, genéricamente, para el colapso de una pared o estructura
("el derrumbe de la pared ocurrió a las 5:30 p.m."). Ninguna de las frases
específicas de `colapso_estructural` ("colapso de vivienda", "desplome de
estructura", etc.) coincidía tampoco, así que el evento no tenía ningún
tipo alternativo — quedaba solo con el falso positivo de deslizamiento.

**Corrección** (`scripts/verify_ai.py`): se agregó
`_deslizamiento_estructura_sin_evidencia_fuerte()`, un filtro determinista
análogo al de incendio vehicular/vialidad, que corre antes de la llamada a
la IA. Solo se activa cuando el texto menciona una señal de
construcción/deterioro (filtraciones, humedad acumulada, pared, muro,
techo, campanario, iglesia); en ese caso, descarta el tipo=deslizamiento
salvo que el texto también tenga alguna señal real de lluvia o movimiento
de tierra (lluvia, precipitación, tormenta, onda tropical, tierra, ladera,
talud, cerro, barro, lodo, material rocoso, vía, carretera, quebrada,
desbordamiento). Probado con el caso real (se descarta) y con todos los
casos de deslizamiento ya publicados como control (ninguno se ve
afectado, todos mencionan lluvia/vía/carretera explícitamente).

**Corrección retroactiva**: se eliminó la alerta completa de
`docs/data/noticias.json`, `data/historico_eventos.jsonl` y
`data/historico_fuentes_texto.jsonl`. También se editó manualmente el
informe narrativo ya generado `docs/data/informes/2026-07_deslizamiento.json`
(se quitó la oración y la fuente de Ospino, `total_eventos` 6→5) y
`docs/data/informes/2026-07_general.json` (se quitó la fuente,
`total_eventos` 18→17) — `build_informes.py` no los habría regenerado hoy
(el período en curso se regenera como máximo una vez al día, y ya se había
generado hoy). Se regeneraron las estadísticas.

### 3. Un municipio/parroquia inferido a partir del nombre del país

La alerta "Inundación en Parroquia Venezuela, Municipio Lagunillas, Zulia"
tenía una ubicación sin ningún respaldo textual: ninguna de sus tres
fuentes menciona "Lagunillas", y la única mención de "Venezuela" en el
texto combinado es "...por el occidente de **Venezuela**" (el país, no la
parroquia).

**Causa raíz**: por coincidencia, existe una parroquia real llamada
"Venezuela" (única en todo el país, del Municipio Lagunillas, Zulia — ver
`config/ubicaciones_detalle.json`). `_buscar_parroquia_directa()` en
`classify.py` (coincidencia directa de nombre, sin la palabra "parroquia"
delante, cuando el municipio aún no se conoce) exige que el nombre sea
único en todo el país para aceptarlo sin ambigüedad — "Venezuela" cumple
esa condición técnica, pero ninguna mención del nombre del propio país en
un artículo periodístico debería tratarse jamás como evidencia de esa
parroquia específica. Es la misma clase de bug que la parroquia homónima
al municipio (corregida el 27-07-2026), pero aquí la coincidencia es con
el nombre del país, no con el del municipio.

**Corrección** (`scripts/classify.py`): se agregó la constante
`_NOMBRE_PAIS_NORM = "venezuela"`, excluida explícitamente como candidato
en `_buscar_municipio_directo()` y en ambas ramas de
`_buscar_parroquia_directa()` (municipio conocido y desconocido) — igual
que ya se excluye el nombre del propio estado. La detección **explícita**
("parroquia Venezuela, municipio Lagunillas...") no se ve afectada, sigue
funcionando por la vía del regex `_PARROQUIA_RE`/`_MUNICIPIO_RE` (se probó
como caso de control).

**Corrección retroactiva**: se quitó el municipio/parroquia inventados de
la alerta ya publicada en `docs/data/noticias.json` (regenerando
`titulo`/`texto` con `render.redactar_noticia()`, quedando "Inundación en
Zulia") y `data/historico_eventos.jsonl`. `data/historico_fuentes_texto.jsonl`
no requería cambio (no guarda municipio/parroquia). Se regeneraron las
estadísticas.

Validado con `python3 scripts/validar_configs.py` y con regresión completa
de los tres fixes (tipo, severidad y municipio/parroquia) contra las 34
fuentes de `data/historico_fuentes_texto.jsonl`: ningún caso ya publicado
cambia de resultado salvo los tres corregidos aquí.

---

## Auditoría diaria autónoma: siete duplicados por una causa raíz común (28-07-2026)

Segunda auditoría de rutina del día (sin que el usuario la pidiera), muy
poco después de la anterior. Al revisar `docs/data/noticias.json` completo
contra `data/historico_fuentes_texto.jsonl` no aparecieron errores nuevos de
tipo/severidad/ubicación, pero un barrido sistemático (agrupar por
tipo+ubicación y comparar fechas dentro de la ventana de 36 horas, igual que
hace `state.py`) encontró **siete clusters de alertas duplicadas** — el mismo
evento real publicado dos o más veces — todos con la misma causa raíz de
fondo, ya identificada antes pero que resultó estar más activa de lo que
parecía.

### Causa raíz 1: `publicados.json` guardado antes del fix de ventana de 36h nunca "matchea"

`state._resolver_clave()` solo reutiliza la clave de un evento ya publicado
si ese registro en `data/publicados.json` tiene `fecha_evento_temprana`. Los
registros guardados **antes** de que ese campo se empezara a persistir
(27-07-2026) no lo tienen — así que cualquier re-detección posterior de esa
misma noticia (el mismo artículo reaparece en una corrida nueva, o un
artículo hermano se procesa por separado) nunca encuentra la clave existente,
genera una clave nueva, y se publica como si fuera un evento distinto. Se
confirmó este patrón exacto en `data/publicados.json` para "Deslizamiento
Barinas" (`deslizamiento::Barinas::2026-07-26`, sin `fecha_evento_temprana`)
y "Inundación Lara" (`inundacion::Lara::2026-07-26`, ídem) — ambos con una
clave "huérfana" `::2026-07-27` creada por la re-detección.

**Corrección** (`scripts/state.py`, `_resolver_clave`): cuando el registro
previo no tiene `fecha_evento_temprana`, se usa como fecha aproximada el
**mediodía** del día codificado en la propia clave (no la medianoche, que
recortaría hasta 12h reales de la ventana de 36h y seguiría sin matchear el
caso real de Barinas). Probado con 5 casos: el caso real de Barinas (debe
reusar la clave existente), el caso real de Lara (ídem), un evento fuera de
ventana (debe generar clave nueva), un tipo distinto (no debe matchear), y
una entrada de estilo nuevo con `fecha_evento_temprana` ya presente (no
regresión).

### Causa raíz 2: la IA "confirma" su propia alucinación de municipio porque el nombre del estado está trivialmente presente

Se encontraron dos alertas "Deslizamiento/Derrumbe en Municipio Barinas,
Barinas" (sector El Celoso, reapertura de la vía) cuyo municipio no tiene
ningún respaldo textual real — las fuentes solo dicen "paso entre Mérida y
Barinas"/"carretera Mérida-Barinas", mencionando "Barinas" únicamente como
nombre del estado. El resto de fuentes del mismo evento real (vía
Barinas-Mérida bloqueada por un deslizamiento) sí identifican consistentemente
**Municipio Bolívar, Parroquia Altamira** (sector La Soledad).

**Causa raíz**: el 26-07-2026 se corrigió este mismo patrón
("_buscar_nombre_directo() ahora también descarta un nombre si coincide con
el nombre normalizado del propio estado") pero **solo en la vía determinista**
de `classify.py`. La vía asistida por IA de `verify_ai.py` (cuando el regex no
determina municipio/parroquia y se le pide ayuda a Groq) solo verificaba que
el nombre propuesto apareciera **textualmente** en las fuentes — y "Barinas"
sí aparece textualmente, como nombre del estado, así que la IA podía
"confirmar" su propia alucinación sin que el chequeo de anclaje lo detectara.

**Corrección** (`scripts/verify_ai.py`): antes del chequeo de anclaje
textual, se descarta un municipio/parroquia propuesto por la IA si coincide
con el nombre normalizado del propio estado o con "venezuela" — el mismo
criterio que `classify.py` ya aplica en su búsqueda determinista. Probado con
el caso real (IA propone "Barinas" para el estado "Barinas" → descartado),
un caso de control con municipio real y explícito ("Bolívar" en el mismo
estado → aceptado), y el caso ya conocido de "Venezuela" como nombre de país.

### Los siete clusters encontrados y su corrección

Para cada cluster se fusionaron las fuentes de todos los duplicados en una
sola alerta final (mismo criterio ya usado en fusiones anteriores: unión de
fuentes independientes, severidad más grave del grupo, municipio/parroquia
mejor respaldado), salvo cuando un duplicado era subconjunto exacto de otro
(mismo link, sin fuentes nuevas), en cuyo caso se conservó el original sin
recalcular y se descartó el redundante:

1. **Deslizamiento vía Barinas-Mérida** (4 alertas → 1): además del bug de
   municipio ya descrito, esto era el mismo hecho real (cierre y reapertura
   de la vía, sector La Soledad → El Celoso) fragmentado en 4 alertas por la
   causa raíz 1. Resultado final: Parroquia Altamira, Municipio Bolívar,
   Barinas — confirmado, 5 fuentes.
2. **Inundación Lara** (2 → 1): la alerta ya publicada con municipio/parroquia
   completos (Simón Planas/Gustavo Vegas León, 2 fuentes) tenía un duplicado
   exacto (mismo único link, sin dato nuevo) publicado un día después por la
   causa raíz 1. Se descartó el duplicado.
3. **Inundación Zulia** (2 → 1): dos corridas separadas sobre la misma onda
   tropical N.º 30 en Zulia. Fusionadas en una sola, 4 fuentes.
4. **Inundación Distrito Capital / Antímano** (3 → 1): tres corridas
   separadas sobre lluvias/onda tropical N.º 30 en la misma zona (Carapita,
   parroquia Antímano). Fusionadas, 7 fuentes.
5. **Deslizamiento Distrito Capital** (2 → 1): misma fuente (La Prensa de
   Monagas) publicó dos artículos distintos sobre derrumbes en Caracas en
   corridas separadas; al deduplicar por nombre de fuente (mismo criterio que
   ya usa `verify.py` para no contar dos veces al mismo medio) queda 1 fuente
   independiente. Se conservó la severidad "alto" (heridos/lesionados
   mencionados en el segundo artículo) y el municipio Libertador.
6. **Falla eléctrica Lara** (2 → 1): duplicado exacto, mismo link, detectado
   dos veces con 4 horas de diferencia (25-07-2026, anterior incluso a la
   causa raíz 1). Se conservó la versión con severidad correctamente
   clasificada ("bajo"); no se le aplicó retroactivamente la bonificación por
   fuente regional agregada después, por quedar fuera del alcance de esta
   auditoría.
7. **Tormenta eléctrica Zulia, Maracaibo + Guajira** (2 → 1): dos corridas
   separadas sobre la misma tormenta (onda tropical N.º 30) con fuentes
   propias por municipio. A diferencia de los demás casos, aquí **ningún**
   municipio es incorrecto — ambos son hechos reales y específicos, pero
   `state.py` deduplica solo a nivel de estado (no de municipio), así que el
   diseño actual del sistema ya los trata como "el mismo evento". Se fusionó
   con **`municipio: null`**: afirmar solo uno de los dos implicaría
   falsamente que el otro no fue afectado; la afirmación a nivel estado sigue
   siendo estrictamente cierta. **Limitación conocida, no resuelta**: el
   sistema no puede hoy representar dos alertas separadas para dos municipios
   distintos del mismo estado afectados por el mismo fenómeno regional en
   corridas distintas — queda anotado para si se decide en el futuro que la
   deduplicación debería ser más granular que a nivel de estado.

**Limpieza de claves huérfanas en `data/publicados.json`**: las claves que
cada miembro individual de un cluster fusionado habría generado por su
cuenta (antes de fusionarse) y que ya no corresponden a ninguna noticia
publicada se eliminaron (`deslizamiento::Barinas::2026-07-27`,
`deslizamiento::Distrito Capital::2026-07-27`,
`inundacion::Distrito Capital::2026-07-26`,
`inundacion::Distrito Capital::2026-07-27`, `inundacion::Lara::2026-07-27`) —
dejarlas podía enganchar una futura re-detección a datos desactualizados en
vez de a la clave final ya corregida.

**Backfill de `clave_dedup`**: además de los clusters fusionados, se agregó
`clave_dedup` (calculado con la misma lógica de `state._clave_evento`) a
**todas** las alertas de `docs/data/noticias.json` que todavía no lo tenían —
sin esto, cualquier actualización futura de esas alertas (cambio de
severidad/confirmación) volvería a duplicarlas en vez de reemplazarlas, el
mismo patrón de causa raíz 1 aplicado hacia adelante.

**Archivos corregidos retroactivamente**: `docs/data/noticias.json`,
`data/historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl`,
`data/publicados.json`, y los informes narrativos afectados
(`docs/data/informes/2026-07_deslizamiento.json` 5→2 eventos,
`2026-07_inundacion.json` 7→4, `2026-07_tormenta_electrica.json` 3→2,
`2026-07_general.json` 17→10, y `index.json` con los mismos totales) — en
ningún caso se necesitó agregar o quitar fuentes de los informes (las listas
de fuentes ya eran la unión correcta), solo corregir `total_eventos`,
`comparacion_mes_anterior` y la oración inicial de la narrativa. De paso se
notó y corrigió que `2026-07_general.json` ya tenía un desface preexistente
entre `total_eventos` (17) y el número mencionado en su propia narrativa
(18) — residuo de una edición manual de la auditoría anterior que no había
sincronizado ambos lugares. Se regeneraron las estadísticas con
`python3 scripts/build_dashboard.py`.

Validado con `python3 scripts/validar_configs.py` y con los casos de prueba
descritos arriba para ambos fixes de código.

---

## Auditoría diaria autónoma: cuatro bugs de raíz, uno con corrección retroactiva (28-07-2026, tercera pasada)

Tercera auditoría de rutina del día (sin que el usuario la pidiera). Se
revisaron las 14 alertas actualmente publicadas en `docs/data/noticias.json`
contra el texto real de sus fuentes. Se encontraron y corrigieron cuatro
bugs de raíz distintos; solo uno de ellos afectaba un dato ya publicado.

### 1. Un solo municipio "ganador" cuando el texto menciona varios por igual

La alerta "Falla eléctrica en Municipio Cabimas, Zulia" (3 fuentes,
CONFIRMADO) afirmaba que el corte eléctrico era específicamente de Cabimas,
pero una de sus propias fuentes ("Diario La Nacion") dice explícitamente:
"...afectaron principalmente a los municipios Maracaibo, San Francisco,
**Cabimas**, Mara y La Cañada de Urdaneta" — cinco municipios igualmente
afectados, no uno solo. Afirmar solo Cabimas implica falsamente que los
otros cuatro no fueron afectados.

**Causa raíz** (`scripts/classify.py`, `_buscar_municipio_directo`): la
función itera las variantes de nombre de municipio del estado y devuelve el
**primero** que encuentra mencionado en el texto, sin verificar si hay
**otros** municipios distintos también mencionados en ese mismo texto. Con
una lista de varios municipios en una sola oración, el resultado depende
solo del orden de iteración del diccionario interno, no de cuál aparece
primero en el texto ni de si hay uno solo. El caso ya conocido y corregido
de "Cabimas"/"Guajira" (27-07-2026) era sobre una parroquia inventada por la
IA sin respaldo alguno; este es distinto: un municipio real y mencionado,
pero uno entre varios igualmente válidos, elegido arbitrariamente.

**Corrección** (`scripts/classify.py`): `_buscar_municipio_directo` ahora
junta TODOS los municipios candidatos que aparecen en el texto (no se
detiene en el primero) y solo devuelve uno si es el **único** encontrado;
si hay dos o más, o ninguno, devuelve `None` — igual que el resto del
código de esta función prefiere `None` a una ubicación potencialmente
engañosa. Probado con el caso real (5 municipios en una oración → `None`,
antes devolvía "Cabimas") y contra las 34 fuentes de
`data/historico_fuentes_texto.jsonl` como regresión: ningún caso con un
único municipio mencionado cambia de resultado (Valencia/Carabobo,
Simón Planas/Lara, Bolívar/Barinas, Bocono/Trujillo, y la inferencia de
Libertador/Distrito Capital vía parroquia Antímano, todos sin cambios).

**Corrección retroactiva**: se quitó el municipio "Cabimas" de la alerta ya
publicada en `docs/data/noticias.json` (regenerando `titulo`/`texto`,
quedando "Falla eléctrica en Zulia") y `data/historico_eventos.jsonl`. Los
informes narrativos ya publicados (`2026-07_infraestructura_electrica.json`,
`2026-07_general.json`) ya mencionaban correctamente los 5 municipios en su
texto (se generan resumiendo el texto completo de las fuentes, no el campo
`municipio` del evento), así que no requirieron corrección. Se regeneraron
las estadísticas.

### 2. El anclaje textual de ubicación de la IA usaba fuentes ya rechazadas del mismo cluster

Al revisar el mecanismo de verificación de ubicación asistida por IA
(agregado el 27-07-2026 tras el caso de "Parroquia San Francisco, Municipio
Maracaibo" inventado), se encontró que el chequeo de anclaje —"el
municipio/parroquia que proponga la IA solo se acepta si aparece
textualmente en las fuentes"— usaba el texto de **todos los candidatos**
evaluados en esa llamada a Groq (`candidatos`), no solo el de las fuentes
que la IA termina aprobando (`grupos_aprobados`). Como la verificación de
plausibilidad y la inferencia de ubicación ocurren en la misma llamada,
una fuente del mismo cluster que la IA rechaza por describir un hecho
distinto (u otro criterio de plausibilidad) puede seguir "anclando" un
municipio/parroquia que ninguna fuente realmente publicada menciona.

**Causa raíz** (`scripts/verify_ai.py`, `verificar_evento_con_ia`):
`texto_fuentes_norm` se construía con `for g in candidatos for m in g`
en vez de `for g in grupos_aprobados for m in g` — este último ya estaba
calculado y disponible en ese punto del código (se usa un poco antes para
el chequeo `if not grupos_aprobados: return None`).

**Corrección**: se cambió `candidatos` por `grupos_aprobados` en la
construcción de `texto_fuentes_norm`. Probado con un caso simulado (mock de
la respuesta de Groq, sin llamada real a la API): un cluster de 2 fuentes,
una que menciona explícitamente "Sinamaica"/"municipio Indígena Bolivariano
Guajira" pero que la IA rechaza (`NO`, hecho distinto), y otra que la IA sí
aprueba (`SI`) pero sin esa ubicación en su propio texto — con el código
viejo la ubicación de la fuente rechazada se colaba igual en el evento
publicado; con el fix, se descarta correctamente (`municipio`/`parroquia`
quedan `None`). Un segundo caso de control (ubicación mencionada en la
fuente que sí se aprueba) sigue funcionando sin cambios.

No se encontró ninguna alerta actualmente publicada afectada por este bug
específico: se revisó la alerta más parecida al patrón ("Colapso
estructural en Parroquia Sinamaica, Municipio Indígena Bolivariano Guajira,
Zulia") y su municipio/parroquia ya habían sido confirmados como correctos
en una sesión anterior (27-07-2026, "texto completo obtenido manualmente de
la página del artículo" por el usuario) — no hace falta ni conviene tocar
ese dato ya verificado. El fix queda para prevenir el mismo problema en
clusters futuros con fuentes rechazadas que mencionen una ubicación
distinta a la del hecho real.

### 3. Entidades HTML dobles impedían detectar resúmenes de RSS truncados

Siguiendo el hilo del bug anterior: la fuente de esa misma alerta de
colapso estructural sigue almacenada, en
`data/historico_fuentes_texto.jsonl`, con el resumen truncado ("...una
vivienda colapsara, como&#8230;") en vez del texto completo que el usuario
confirmó manualmente el 27-07-2026. Es decir, el mecanismo automático de
`fetch_rss.py` para traer el texto completo cuando el resumen viene
truncado (agregado ese mismo día) nunca se disparó para esta fuente en la
corrida real.

**Causa raíz** (`scripts/fetch_rss.py`, `_limpiar_texto`/`_TRUNCADO_RE`):
el feed de esta fuente entrega su marca de truncamiento como entidad HTML
numérica ("&#8230;") en vez del carácter real "…" o de puntos suspensivos
literales. `_TRUNCADO_RE` busca el carácter Unicode real, así que nunca
coincide con el texto literal "&#8230;" -- la entidad no se decodifica en
ningún punto de la limpieza de texto (`feedparser`/`BeautifulSoup` ya
decodifican una vez, pero algunos feeds entregan sus entidades doblemente
escapadas, dejando un residuo como este tras un solo `unescape`). El mismo
patrón aparece en otras fuentes ya publicadas (p.ej. "El fenómeno&#8230;"
en la fuente de Turimiquire sobre el rayo en Valencia, Carabobo) — un
problema sistémico, no de una sola fuente.

**Corrección** (`scripts/fetch_rss.py`): se agregó `html.unescape()` al
inicio de `_limpiar_texto()`, antes de los demás pasos de limpieza. Probado
con el texto real de la fuente del colapso estructural ("...como&#8230;" →
ahora sí coincide con `_TRUNCADO_RE` y dispara la descarga del texto
completo), con el caso del rayo en Carabobo, con texto sin truncar (no debe
activar el chequeo), y con los dos formatos ya soportados (elipsis real y
"[...]"), sin regresión.

No se intentó volver a descargar el texto completo real de estas fuentes ya
publicadas para esta corrección (las URLs son de fuentes de prensa externas
y el dato ya fue verificado manualmente por el usuario en su momento); el
fix solo previene que el mismo problema oculte información en fuentes
nuevas de aquí en adelante.

### 4. `redactar_noticia()` descartaba en silencio el texto recién regenerado

Al intentar aplicar la corrección retroactiva del bug 1 (punto 1 de esta
misma auditoría), se detectó que llamar a
`render.redactar_noticia(evento)` sobre un evento que **ya tiene** sus
propias claves `titulo`/`texto` (exactamente el caso de regenerar el texto
de una alerta ya publicada, el patrón usado en casi todas las correcciones
retroactivas anteriores documentadas en este roadmap) no tiene ningún
efecto: el `titulo`/`texto` viejos sobreviven sin cambios, sin ningún error
que lo advierta.

**Causa raíz** (`scripts/render.py`, `redactar_noticia`): la función
retorna `{"titulo": titulo, "texto": texto, **evento}` — como `evento` ya
trae sus propias claves `"titulo"`/`"texto"` (las del texto viejo), el
`**evento` puesto **después** las sobreescribe de vuelta, ganando siempre
sobre los valores recién calculados. En el uso normal del pipeline
(`scripts/main.py`, sobre un evento recién verificado que todavía no tiene
`titulo`/`texto`) esto nunca se nota, porque no hay colisión de claves —
por eso el bug pasó inadvertido pese a usarse la función repetidamente para
correcciones retroactivas.

**Corrección**: se invirtió el orden — `{**evento, "titulo": titulo,
"texto": texto}` — para que el texto recién calculado gane siempre,
sin cambiar el comportamiento para el uso normal (evento sin esas claves
todavía). Se verificó que las correcciones retroactivas anteriores de esta
misma auditoría (punto 1) sí toman efecto ahora sin necesidad de que quien
llama a la función recuerde borrar `titulo`/`texto` de antemano.

Se revisó también si alguna alerta ya publicada tiene `titulo`/`texto`
desincronizado de sus propios datos (síntoma de que este bug ya afectó una
corrección retroactiva anterior): las únicas discrepancias encontradas
(4 alertas con etiquetas de severidad en formato antiguo, "ALTO"/"BAJO" en
vez de "SEVERIDAD ALTA"/"SEVERIDAD BAJA") son de alertas nunca tocadas por
una corrección retroactiva -- corresponden a un cambio de formato de
`SEVERIDAD_EMOJI` anterior a su publicación, no a este bug. No se
encontró ninguna alerta con datos y texto realmente inconsistentes; se
dejan esas 4 etiquetas de formato antiguo sin tocar (es un cambio
cosmético, no un error de clasificación, y no justifica una corrección
retroactiva por sí solo).

Validado con `python3 scripts/validar_configs.py` y con los casos de
prueba descritos arriba para los cuatro fixes de código.

---

## Se elimina la integración con el correo institucional de Outlook (28-07-2026)

A pedido explícito del usuario: el último intento de conectar el correo
institucional vía Power Automate resultó infructuoso (y, según se
diagnosticó en la auditoría de esta misma noche, el secreto
`OUTLOOK_REFRESH_TOKEN` en GitHub Actions estaba vacío — el canal llevaba
fallando en todas las corridas del día con "AADSTS900144: The request body
must contain the following parameter: 'refresh_token'"). El usuario decidió
abandonar esta vía por completo y retomar la estrategia alternativa ya
conversada (el flujo de Power Automate → issue de GitHub →
`fetch_github_issues.py`, descrito en la sección "Pendiente para retomar"
más arriba en este documento) en vez de seguir intentando reparar la
integración directa con Microsoft Graph.

**Eliminado**:
- `scripts/fetch_email.py` (el módulo que autenticaba con
  `msal.PublicClientApplication` y leía mensajes vía Microsoft Graph
  `/me/messages`).
- `generar_token_outlook.py` (raíz) y
  `scripts/generar_refresh_token_outlook.py` (herramientas manuales para
  obtener/renovar el `refresh_token`).
- La llamada a `fetch_email_items()` en `scripts/main.py` (import y las dos
  líneas que la invocaban al recolectar items).
- La dependencia `msal` de `requirements.txt` (sin más usos en el código
  tras lo anterior).
- Las variables de entorno `OUTLOOK_CLIENT_ID`/`OUTLOOK_TENANT_ID`/
  `OUTLOOK_REFRESH_TOKEN` del step "Ejecutar monitoreo" en
  `.github/workflows/monitor.yml`.

**No se tocó**: los secretos `OUTLOOK_CLIENT_ID`/`OUTLOOK_TENANT_ID`/
`OUTLOOK_REFRESH_TOKEN` configurados en GitHub (Settings → Secrets and
variables → Actions) — ya no se usan, pero borrarlos es una acción sobre la
configuración del repositorio en GitHub, no sobre el código, y queda a
criterio del usuario hacerlo o dejarlos huérfanos sin efecto.

El pipeline sigue recolectando de RSS (`fetch_rss.py`) y Telegram
(`fetch_telegram.py`, ya deshabilitado por separado en `main.py` desde
antes de este cambio). Cuando se implemente `fetch_github_issues.py` (la
estrategia acordada), se integrará igual que hacía `fetch_email_items()`:
una llamada más en `main.py` que aporta items a la lista antes de
`clasificar_item()`.

Validado con `python3 scripts/validar_configs.py` y confirmando que no
queda ninguna referencia a `outlook`/`msal`/`fetch_email` en el código ni
en la configuración del workflow.

---

## Nuevo mecanismo para el correo institucional: reenvío a Gmail + IMAP (29-07-2026)

Tras descartar Outlook/Microsoft Graph (por requerir permisos de
administrador del tenant) y Power Automate (también descartado hoy — la
organización bloquea o exige aprobación de administrador para ese tipo de
conexión), se definió con el usuario un mecanismo alternativo que preserva
el flujo de trabajo de las filiales sin cambios: las filiales siguen
enviando sus reportes al correo institucional de siempre.

**Mecanismo**: una regla de bandeja de entrada configurada por el propio
usuario en el buzón institucional (Outlook → Reglas → "Reenviar a", sin
necesidad de administrador ni de Power Automate) reenvía automáticamente
los correos a una cuenta Gmail dedicada y de uso exclusivo para esto
(`alertacrv.reportes@gmail.com`). Un nuevo `scripts/fetch_gmail.py` lee esa
cuenta por IMAP (usando únicamente `imaplib`/`email` de la librería
estándar de Python — sin dependencias nuevas), con una contraseña de
aplicación de Google (requiere verificación en 2 pasos activada en esa
cuenta), en vez de OAuth/Graph API.

**Por qué es más sostenible que la integración anterior**: no depende de
autenticación básica sobre Exchange Online (que Microsoft viene
deshabilitando por defecto en cada tenant) ni de ningún token que expire o
requiera renovación coordinada con IT — la cuenta Gmail y su contraseña de
aplicación las controla el usuario por completo y de forma indefinida.

**Diseño de `fetch_gmail.py`**:
- Reutiliza sin cambios la lógica de interpretación del asunto que ya tenía
  `fetch_email.py` (formato `EMERGENCIA | Estado | Tipo | Severidad`,
  `TIPO_MAP`, `SEVERIDADES_VALIDAS`) — ese formato y su validación no eran
  el problema, solo el transporte (Microsoft Graph) sí lo era.
- **Causa raíz anticipada y corregida antes de probarse en producción**: el
  reenvío de Outlook (manual o por regla) suele anteponer un prefijo al
  asunto original ("FW:", "Fwd:", "RV:", y sus combinaciones en cadenas de
  reenvío repetidas) — sin quitarlo, el asunto de **todo** correo reenviado
  dejaría de coincidir exactamente con el formato esperado y se
  descartaría en silencio, inutilizando el mecanismo completo desde el
  primer correo real. Se agregó `_quitar_prefijos_reenvio()`, que quita
  estos prefijos en un bucle (una cadena de varios reenvíos puede acumular
  más de uno) antes de validar el formato.
- Lee los mensajes **no leídos** de la bandeja (IMAP `SEARCH UNSEEN`, no
  filtra por fecha/hora como sí hacen `fetch_rss.py`/`fetch_telegram.py` —
  `SEARCH SINCE` de IMAP solo tiene granularidad de día) y los marca como
  leídos al procesarlos, coincidan o no con el formato esperado — así
  nunca se reprocesa el mismo correo dos veces, y un correo que no matchea
  (ej. una consulta administrativa) no queda "atascado" como no leído para
  siempre.
- Extrae el cuerpo del mensaje priorizando texto plano sobre HTML (si solo
  hay HTML, le quita las etiquetas, mismo criterio que `fetch_rss.py` con
  los resúmenes de RSS).
- El link publicado para cada fuente institucional apunta a una búsqueda
  por `Message-ID` en Gmail (`https://mail.google.com/mail/u/0/#search/
  rfc822msgid:...`), reemplazando el `webLink` de Outlook que ya no existe
  en este mecanismo.

**Probado** (sin conexión real, con mensajes MIME de prueba y un IMAP
simulado): asunto limpio, asunto con un prefijo de reenvío, asunto con dos
prefijos encadenados, asunto que no matchea el formato (se descarta sin
error), cuerpo multipart con texto plano y HTML (prioriza texto plano),
cuerpo solo-HTML (extrae y limpia), ausencia de credenciales (devuelve
lista vacía sin fallar, mismo patrón "fail-safe" que el resto del
pipeline), y el flujo completo contra `classify.py`/`clasificar_item()`
para confirmar que el item generado es compatible con el resto de la
tubería.

**Cambios**: nuevo `scripts/fetch_gmail.py`; `scripts/main.py` vuelve a
recolectar una fuente de correo (ahora `fetch_gmail_items()` en vez de
`fetch_email_items()`); `.github/workflows/monitor.yml` agrega los
secretos `GMAIL_ADDRESS`/`GMAIL_APP_PASSWORD` al step de ejecución (no se
agrega ninguna dependencia nueva a `requirements.txt` — `imaplib`/`email`
son de la librería estándar).

**Pendiente**: el usuario está configurando la cuenta Gmail y la regla de
reenvío; falta que agregue los dos secretos (`GMAIL_ADDRESS`,
`GMAIL_APP_PASSWORD`) en GitHub para que el mecanismo quede activo. Sin
esos secretos, `fetch_gmail_items()` se comporta igual que antes sin
`OUTLOOK_REFRESH_TOKEN`: devuelve una lista vacía con una advertencia,
sin afectar al resto del pipeline.

Validado con `python3 scripts/validar_configs.py` y los casos de prueba
descritos arriba.

---

## Diagnóstico y correcciones sobre el nuevo mecanismo de correo (29-07-2026)

Al probar en vivo el mecanismo de Gmail + IMAP recién implementado, aparecieron
dos problemas reales que no se habían detectado en las pruebas con mensajes
simulados de la sesión anterior.

### 1. El reenvío automático por regla estaba bloqueado por política del tenant (no era un bug de código)

El correo de prueba nunca llegó a Gmail. El rebote de Microsoft fue explícito:
`550 5.7.520 Access denied, Your organization does not allow external
forwarding`. Las cabeceras del mensaje rebotado confirman que lo generó
`Mailbox Rules Agent` (la regla automática) — es la política de anti-spam
saliente de Exchange Online (`AutoForwardingMode`) que bloquea el reenvío
automático (por regla o por el ajuste clásico de auto-forward SMTP) hacia
cualquier dominio externo, independientemente de a qué proveedor se reenvíe.
No hay forma de evitarla sin aprobación de administrador, así que se descartó
la regla de bandeja de entrada como mecanismo de transporte.

**Decisión del usuario**: en vez de seguir buscando un mecanismo 100%
automático, reenvía manualmente cada correo institucional a la cuenta Gmail
mientras se evalúa una solución definitiva. Un reenvío manual (clic en
"Reenviar" + enviar) es una acción humana deliberada, no un reenvío
automático por regla — la política de `AutoForwardingMode` que bloqueó la
regla no aplica a este caso, y en la práctica el reenvío manual sí llegó.
`scripts/fetch_gmail.py` no necesitó ningún cambio para este caso: ya
quitaba el prefijo "RV:"/"FW:" que Outlook antepone al reenviar (manual o
por regla).

### 2. El formato rígido de asunto nunca iba a coincidir con reportes reales

Aun llegando el correo a Gmail, `fetch_gmail_items()` seguía sin encontrar
nada. Causa: el diseño heredado de `fetch_email.py` (la integración anterior
con Outlook) exigía un asunto con el formato exacto `EMERGENCIA | Estado |
Tipo | Severidad`. El usuario confirmó que los reportes reales de las
filiales **nunca** llegan en ese formato — llegan en lenguaje natural (caso
real probado: "Actualización de desplazados de La Guaira en los municipios
Colina, Zamora y Tocopero"). Con el formato rígido, absolutamente ningún
reporte real habría sido nunca clasificado, sin importar qué tan bien
funcionara el transporte (Outlook, Gmail, o cualquier otro).

**Corrección de raíz** (`scripts/fetch_gmail.py`): se eliminó por completo
`_parsear_asunto()`/`TIPO_MAP`/`SEVERIDADES_VALIDAS` y el mecanismo
`_preclasificado` que se pasaba a `classify.py` para saltarse su detección.
Ahora cada correo se entrega como un item de texto libre (asunto + cuerpo),
exactamente igual que un item de `fetch_rss_items()` — `clasificar_item()`
en `classify.py` hace la detección de ubicación/tipo/severidad a partir del
texto con el mismo mecanismo que ya usa para artículos de RSS, sin exigir
ningún formato particular. El prefijo "RV:"/"FW:" se sigue quitando, pero
solo por prolijidad del texto mostrado, no porque el clasificador lo
necesite (la detección escanea todo el texto, no depende de cómo empiece el
asunto).

**Probado** con el caso real reportado por el usuario: el texto completo
("Actualización de desplazados de La Guaira en los municipios Colina, Zamora
y Tocopero. Se mantiene la atención a las familias afectadas por los
terremotos, con refugios activos...") se clasifica correctamente como
ubicación "La Guaira", tipo "sismo" (por la mención de "terremotos"),
`es_relevante() = True` — pasaría a la verificación de plausibilidad de
`verify_ai.py` igual que cualquier otra fuente (incluido el filtro de
retrospectiva de sismo, que podría rechazarlo si la IA lo considera una
actualización de seguimiento en vez de un hecho nuevo — comportamiento
esperado y compartido con el resto de fuentes sobre el mismo tema, no un
problema de este fetcher). También probado el flujo completo de IMAP
simulado con este texto real, confirmando que el item generado y marcado
como leído es idéntico al que produciría `clasificar_item()` sobre un
artículo de RSS equivalente.

**Nota para el futuro**: si en algún momento se decide que "desplazados"
(sin la palabra "masivo") debería activar por sí solo el tipo
`crisis_migratoria`, es un cambio de una sola línea en
`config/keywords.yaml` — se deja pendiente de una decisión explícita en vez
de agregarlo sin que se haya discutido, ya que "desplazados" en este
contexto se refiere a víctimas de los sismos (que ya se cubre razonablemente
bien con el tipo `sismo`), no necesariamente a una crisis migratoria en el
sentido que ese tipo representa en el resto del sistema.

Validado con `python3 scripts/validar_configs.py`.

---

## Acuerdo pendiente de implementar: adjuntos de correo con datos personales sensibles (29-07-2026)

El usuario mostró ejemplos reales de los reportes institucionales que reciben
por correo (filiales de la Cruz Roja reportando personas desplazadas por los
sismos de La Guaira): la mayoría vienen como adjuntos en PDF, Word y
PowerPoint, y **hoy `fetch_gmail.py` descarta todos los adjuntos por completo**
(`_extraer_cuerpo()` salta explícitamente cualquier parte con
`Content-Disposition: attachment`).

**Hallazgo crítico al revisar los adjuntos de muestra**: contienen datos
personales y de salud de personas identificables, incluyendo menores de
edad — nombres completos, cédulas de identidad, teléfonos, direcciones
exactas con puntos de referencia, y diagnósticos médicos individuales
(hipertensión, epilepsia, embarazo, trastornos psiquiátricos, etc.).

**Por qué esto no puede tratarse igual que un adjunto cualquiera**: el
pipeline actual envía el texto completo de cada fuente a Groq (IA de
terceros) para clasificación/verificación, y además lo guarda en
`data/historico_fuentes_texto.jsonl` específicamente para que
`build_informes.py` genere resúmenes narrativos que **se publican en el
sitio público**. Sin un paso de por medio, datos personales y de salud de
personas desplazadas vulnerables podrían viajar a un servicio externo de IA
y/o terminar reflejados, aunque sea parafraseados, en una página pública.

**Acuerdo con el usuario** (criterio de diseño, pendiente de implementar):

- La alerta pública **nunca** debe incluir datos a nivel de persona
  individual. Solo debe reflejar: conteo consolidado por edad y sexo, lugar
  de procedencia de las personas desplazadas, condición general (no
  diagnósticos individuales), y la parroquia/municipio/estado donde están
  albergadas.
- En vez de intentar "limpiar" el texto completo quitándole los datos
  personales (frágil: un regex puede fallar y dejar pasar un nombre o
  cédula en un formato no anticipado), el diseño acordado es el opuesto:
  **extraer únicamente la sección de totales/resumen agregado** que estos
  reportes ya suelen incluir (ejemplos reales confirmados: "Número de
  Familias: 17", "Masculinos: 24", "Femeninas: 22", "Niños: 5",
  "Necesidades identificadas...", municipios de destino). Esa sección —y
  solo esa— se convierte en el texto que entra a clasificación. El resto
  del documento (el detalle por familia/persona) se descarta inmediatamente
  después de extraer los adjuntos y nunca se guarda en ningún archivo ni se
  envía a la IA.
- **Si un reporte no trae esa sección de totales reconocible** (ej. un PDF
  que solo lista el detalle por familia sin un resumen agregado al final),
  el sistema debe descartar esa fuente por completo en vez de intentar
  construir un resumen a partir de los datos individuales — se prefiere
  perder el evento a arriesgar una fuga de datos personales. Queda como
  limitación conocida: si una filial no incluye la sección de totales, ese
  reporte específico no se capturará automáticamente hasta que la incluya.

**Pendiente de implementar** (próxima sesión): extracción de texto de
adjuntos PDF/Word/PowerPoint (nuevas dependencias: `pypdf`, `python-docx`,
`python-pptx`) + la función de extracción de la sección de totales con el
criterio de "fail closed" descrito arriba, probada contra los documentos
reales de muestra.

---

## Diagnóstico: publicación a Telegram rota tras poner el grupo en privado (29-07-2026)

Al revisar los logs de una corrida real se encontró:
`[ERROR] No se pudo publicar en Telegram: 400 {"ok":false,"error_code":400,
"description":"Bad Request: chat not found"}`, repetido para varios eventos.
Coincide en el tiempo con que el usuario puso el grupo de destino en
privado.

**Diagnóstico**: la hipótesis más probable es que, al cambiar la
configuración de privacidad, el grupo pasó de "grupo básico" a
"supergrupo" (una conversión que Telegram hace automáticamente al activar
ciertas opciones, y que es **irreversible**) — eso cambia el `chat_id`
interno del grupo (normalmente agregándole el prefijo `-100`), y el
`TELEGRAM_CHAT_ID` guardado en los secretos de GitHub quedó apuntando a un
chat que ya no existe con ese identificador.

**Decisión**: no revertir la privacidad del grupo (el usuario quiere
mantenerlo privado a propósito, para que el público general no vea alertas
de las filiales sin verificar). En su lugar, obtener el `chat_id` actual
vía `https://api.telegram.org/bot<TOKEN>/getUpdates` (con un mensaje nuevo
en el grupo) y actualizar el secreto `TELEGRAM_CHAT_ID` con el valor
correcto — funciona sin importar la causa exacta del cambio y no requiere
tocar la configuración de privacidad del grupo.

**Pendiente**: el usuario todavía no confirmó el nuevo `chat_id` ni lo
actualizó en los secretos de GitHub. La publicación a Telegram permanece
rota hasta que se haga ese cambio.

---

## Auditoría de las 4 alertas publicadas por falla técnica de Groq: 3 errores reales (29-07-2026)

El usuario pidió revisar las últimas alertas publicadas, calificándolas de
"un total desastre". Las 4 alertas más recientes se habían publicado con
`estado_verificacion: "PASADO_POR_FALLA_TECNICA"` — Groq devolvió 429
(límite de tasa) varias veces seguidas en la misma corrida y el mecanismo
de "fallar hacia lo seguro" las dejó pasar sin la verificación de
plausibilidad real. De las 4, 3 resultaron ser errores reales.

### 1. Pie de página en inglés no se quitaba del texto ("Portuguesa" como estado inventado)

La alerta "Sismo en Portuguesa" no tenía ninguna base real: el artículo de
"Portuguesa Reporta" no menciona ese estado en ningún lugar de su
contenido — la única aparición es el pie de página en inglés que WordPress
agrega ("...first appeared on **Portuguesa Reporta**."), donde
"Portuguesa" es el nombre del medio, no del estado.

**Causa raíz** (`scripts/fetch_rss.py`): `_BOILERPLATE_RE` solo cubría la
variante en español de este pie de página ("la entrada X se publico
primero en Y"), ya corregida en una sesión anterior para el mismo problema
con "El Periodico de Monagas". Nunca se cubrió la variante en inglés ("The
post X first appeared on Y"), que varios feeds de WordPress usan indistinto
del idioma del artículo.

**Corrección**: se agregó la variante en inglés al mismo `_BOILERPLATE_RE`.
Probado con el texto real (ya no detecta "Portuguesa" como ubicación tras
la limpieza) y con el caso de control en español (sigue funcionando sin
cambios).

**Corrección retroactiva**: se eliminó la alerta completa
"sismo::Portuguesa" de `docs/data/noticias.json`,
`data/historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl` y
`data/publicados.json`.

### 2. Lista de "artículos relacionados" al final del resumen contaminaba el tipo detectado

La alerta "Incendio en La Guaira" era un falso positivo total: la fuente
("UBV Monagas continúa demostrando su firme vocación solidaria") es sobre
una jornada de recolección de donaciones para las familias de La Guaira —
ninguna relación con un incendio. La palabra "incendios" solo aparecía en
el título de **otra** nota ("Tres incendios en menos de un mes registra la
ciudad de Maturín"), listada al final bajo "Lea también:" — el pie de
página de WordPress que enlaza artículos relacionados, no contenido del
artículo real.

**Corrección** (`scripts/fetch_rss.py`): se agregó
`_ARTICULOS_RELACIONADOS_RE`, que quita todo el texto desde "Lea
también:"/"Lee también:" en adelante, igual que ya se hace con el pie de
página "la entrada X se publico primero en...". Probado con el texto real
(ya no detecta tipo=incendio tras la limpieza) y con un caso de control
que menciona "lealtad" (para confirmar que el límite de palabra evita
falsos positivos con palabras que empiezan igual).

**Corrección retroactiva**: se eliminó la alerta completa
"incendio::La Guaira" de los mismos cuatro archivos, y se borró el informe
narrativo `docs/data/informes/2026-07_incendio.json` (generado
enteramente a partir de este evento erróneo, era el único de tipo
incendio del período) junto con su entrada en
`docs/data/informes/index.json`.

### 3. "En los últimos N días" se confundía con la duración real de un corte

La alerta "Falla eléctrica en Anzoategui" tenía severidad "bajo" sin base
real: la fuente dice "en los **últimos 15 días** aumentaron los cortes...
con una duración que va desde cuatro hasta siete horas" — 15 días es la
ventana de tiempo sobre la que se reporta una tendencia, no la duración de
un corte continuo (que en este caso es de 4 a 7 horas, muy por debajo del
umbral de 24 horas para severidad "bajo").

**Causa raíz** (`scripts/classify.py`, `_severidad_por_duracion`): el
regex de duración en días (`_DURACION_DIAS_RE`) no distinguía "N días de
corte continuo" (evidencia real de severidad) de "en los últimos N días"
(una ventana de reporte). Cualquier mención de "N días" en el texto,
sin importar el contexto, disparaba la severidad "bajo" si N superaba el
umbral del tipo.

**Corrección**: se agregó `_es_ventana_reciente()`, que revisa el
contexto inmediatamente anterior a la coincidencia y descarta a "últimos/
últimas/pasados/pasadas N días" como evidencia de duración. Probado con el
caso real (ya no escala a "bajo"), con el caso de control ya publicado
("cortes eléctricos que superan las 94 horas", sigue dando "bajo"), y con
un caso adicional de agua ("en los últimos 10 días fallas de agua", ya no
escala) además de su contraparte legítima ("10 días sin agua", sigue
escalando). Se corrió el conjunto completo de fuentes ya publicadas contra
`classify.py` como regresión: ningún otro evento cambia de tipo o
severidad salvo el corregido aquí.

**Corrección retroactiva**: se actualizó la severidad a "sin_clasificar"
(regenerando `titulo`/`texto`) en `docs/data/noticias.json`,
`data/historico_eventos.jsonl` y `data/publicados.json` — se conservó la
alerta (el evento en sí es real, solo la severidad estaba mal).

### Nota sobre la causa de fondo compartida

Las 3 alertas erróneas comparten un patrón: son casos que la IA (Groq)
muy probablemente habría rechazado o corregido de haber podido evaluarlas
— de hecho, ese mismo artículo de "Portuguesa Reporta" **sí** fue
rechazado por Groq para las ubicaciones "La Guaira" y "Distrito Capital"
en la misma corrida (por ser un balance retrospectivo del sismo de hace un
mes, no un hecho nuevo) — pero para "Miranda" y "Portuguesa", Groq ya
había empezado a devolver 429 por límite de tasa, y el mecanismo de
"fallar hacia lo seguro" las dejó pasar sin ese mismo criterio. Por eso
también se eliminó "sismo::Miranda" (el mismo artículo retrospectivo,
misma razón de fondo que ya rechazó a La Guaira/DC, solo que aquí no llegó
a evaluarse). No se modificó el mecanismo de "fallar hacia lo seguro" en
sí (es una decisión de diseño ya conversada: preferir publicar sin
confirmar a perder un evento real cuando la IA no está disponible) — los
tres fixes de código corrigen la causa real de cada falso positivo
específico, independientemente de si Groq estaba disponible o no.

Validado con `python3 scripts/validar_configs.py`, los casos de prueba
descritos arriba, y `python3 scripts/build_dashboard.py` para regenerar
las estadísticas.

---

## Preparación para reportes de filiales: palabra clave nueva y bug de ambigüedad encontrado al probar (29-07-2026)

Al acordar con el usuario el criterio de análisis para los correos/adjuntos
de filiales (ver seccion anterior sobre datos personales sensibles), se
simuló el caso real de La Vela (personas desplazadas de La Guaira
albergadas en Falcón) para mostrarle cómo se vería la alerta publicada,
antes de implementar la extracción de adjuntos en sí.

**Palabra clave agregada** (`config/keywords.yaml`, tipo `crisis_migratoria`):
"desplazados"/"desplazadas"/"personas desplazadas"/"familias desplazadas",
a pedido explícito del usuario. Necesaria no solo para asignar el tipo
correcto, sino porque sin ninguna palabra clave de tipo cerca, **la
ubicación tampoco se detectaba en absoluto** (`_ventana_cerca()` exige una
palabra de tipo dentro de la ventana de proximidad para aceptar una mención
de estado como real).

**Bug encontrado al probar con el texto real**: un texto que menciona a
propósito varios municipios ambiguos ("los municipios Colina, Zamora y
Tocopero del estado Falcón") debía quedar con `municipio: None` (ya
corregido el 29-07-2026 para el caso de Zulia/Cabimas), pero en este caso
el municipio se "colaba" de vuelta como "Petit" — un municipio totalmente
distinto.

**Causa raíz** (`scripts/classify.py`): `_buscar_municipio_directo()`
descartaba correctamente el municipio por ambigüedad (3 nombres
distintos encontrados), pero devolvía `None` sin informarle a nadie
*cuáles* eran esos nombres. Como el municipio quedaba en `None`,
`_buscar_parroquia_directa()` entraba a su rama de "municipio desconocido",
que busca cualquier parroquia única en todo el país -- y "Colina" resultó
ser, por coincidencia, también el nombre de una parroquia única del
municipio "Petit" en el mismo estado. Sin saber que "Colina" ya había sido
descartado como ambiguo, esa búsqueda lo aceptó como evidencia de una
parroquia real, infiriendo un municipio ("Petit") que no tiene ninguna
relación con el texto.

**Corrección**: `_buscar_municipio_directo()` ahora devuelve también el
conjunto de nombres normalizados que encontró (ambiguos o no), y
`detectar_municipio_parroquia()` se lo pasa a `_buscar_parroquia_directa()`
como `excluir_normalizados` -- un nombre ya descartado por ambigüedad en la
búsqueda de municipio nunca puede "colarse" de vuelta en la búsqueda de
parroquia. Probado con el caso real (ya no infiere "Petit") y con
regresión completa contra las fuentes ya publicadas (ningún
municipio/parroquia ya detectado cambia).

**Nota de diseño encontrada de paso**: la ubicación de una alerta de
filial depende de qué mención de estado quede más cerca de la palabra
clave de tipo en el texto -- si el texto menciona primero el estado de
*origen* de los desplazados y despues el de *destino* (donde están
albergados y donde se necesita la respuesta), el sistema puede terminar
atribuyendo la alerta al origen en vez del destino. Al redactar el texto
sintético para estos reportes (pendiente de implementar junto con la
extracción de adjuntos), hay que asegurarse de que la ubicación de
destino/albergue quede más cerca de la palabra clave que la de origen.

Validado con `python3 scripts/validar_configs.py` y la regresión descrita
arriba. **Pendiente**: la extracción de adjuntos en sí
(`fetch_gmail.py`) con el criterio de solo-totales-agregados ya acordado
con el usuario, todavía no implementada.

---

## Implementación: extracción segura de adjuntos de filiales, distintivo visual y fecha del documento (29-07-2026)

Se implementó de una vez todo lo acordado en las dos secciones anteriores:
extracción de adjuntos (.docx/.pptx/.pdf) con el criterio de
solo-totales-agregados, el distintivo visual "REPORTE DE FILIAL" con
resumen consolidado en la tarjeta, y el uso de la fecha del propio
documento (no la del reenvío) como fecha del hecho.

### `scripts/attachments_filial.py` (nuevo módulo)

`extraer_item_filial(nombre_archivo, contenido, fecha_email,
remitente_email, message_id)` procesa un adjunto y devuelve un item para
`clasificar_item()`, o `None` si no se pudo interpretar con confianza
(fail closed). Nunca copia texto libre del documento al item resultante:
solo usa (a) nombres de estado/municipio/parroquia, ya validados contra
`config/estados.yaml`/`config/ubicaciones_detalle.json` (nunca son datos
personales), y (b) pares etiqueta/número de la sección de totales,
extraídos con anclas estrictas — nunca la sub-cadena de texto que los
rodea (evita que un detalle pegado al número, ej. "1(24 semanas)", se
cuele). Con eso arma un **texto sintético** propio, que es el único texto
que llega a `clasificar_item()`/Groq/`historico_fuentes.py`/el sitio
público — el documento original (con nombres, cédulas, teléfonos,
direcciones y diagnósticos individuales) nunca sale de esta función.

- **Extracción de texto por formato**: `.docx`/`.pptx` se leen con
  `zipfile` + regex sobre el XML interno (`word/document.xml` /
  `ppt/slides/slideN.xml`), no con `python-docx`/`python-pptx` — una
  muestra real de filial trae una imagen incrustada con el CRC corrupto,
  que hace fallar a cualquier librería que valide el zip completo
  (`BadZipFile`), pese a que el documento en sí es perfectamente legible.
  `.pdf` se lee con `pypdf` (única dependencia nueva agregada a
  `requirements.txt`). Los formatos legados `.doc`/`.ppt` (binarios, sin
  parser seguro disponible) se descartan explícitamente con un aviso.
- **Cifras consolidadas**: se buscan pares etiqueta+número adyacentes en
  cualquier orden ("Femeninas: 4" o, como en un formato real de PowerPoint,
  "91\nFamilias"), usando **solo formas plurales** ("femeninas", "ninos",
  "adultos mayores"...) — en las muestras reales, la sección de totales
  siempre usa el plural, mientras que el detalle por persona (el que trae
  datos personales) usa el singular ("Femenina", "Adulto mayor de 74
  años"). Esa distinción gramatical es lo que evita que la edad de una
  persona puntual se confunda con una cifra consolidada real. Si no se
  encuentra ningún par, se descarta el adjunto completo.
- **Ubicación origen/destino**: se buscan las menciones de estado en el
  texto y se distinguen por las palabras cercanas ("provenientes del
  estado" → origen; "localización"/"albergados"/"acogida"/"trasladados" →
  destino). Si el documento solo nombra el municipio destino sin repetir
  el estado (caso real: "municipio Colina" sin decir nunca "Falcón"), se
  infiere el estado por búsqueda inversa en
  `config/ubicaciones_detalle.json` (solo si el municipio pertenece a un
  único estado). El municipio/parroquia dentro del estado destino ya
  detectado se resuelve reusando `classify.detectar_municipio_parroquia()`
  tal cual. Si no se puede determinar ninguna ubicación destino, se
  descarta el adjunto (fail closed).
- **Bug encontrado y corregido durante la construcción del texto
  sintético**: si la palabra clave de tipo ("personas desplazadas") queda
  ANTES de la mención del estado destino en el texto, cae dentro de la
  ventana de proximidad del estado ORIGEN también (la ventana de un estado
  solo se acota en la mención del estado *siguiente*, no antes) — el
  origen terminaba generando su propia alerta de crisis migratoria por
  error. Se corrigió construyendo el texto sintético con la palabra clave
  siempre DESPUÉS de la mención del destino ("...ahora en \[destino\], como
  personas desplazadas."). Verificado con `clasificar_item()` sobre los 3
  documentos reales de muestra: cada uno genera exactamente un item, con
  la ubicación correcta (destino, no origen).
- **Fecha del documento**: se busca un patrón `DD/MM/AAAA` en los primeros
  ~300 caracteres (las plantillas de la filial la traen justo debajo del
  encabezado) y se usa como `fecha` del item en vez de la fecha del correo
  reenviado, con fallback a esta última si no se encuentra. Esto hace que
  `fecha_evento` en el evento final refleje cuándo ocurrió realmente el
  reporte de la filial, no cuándo se reenvió o procesó.
- **Nombre de fuente con fecha incluida**: se detectó, probando con los 2
  reportes reales de la misma filial (uno inicial del 07/07 y una
  "actualización" del 28/07, ambos con cifras distintas), que
  `agrupar_y_verificar()` deduplica fuentes por `fuente_nombre` exacto —
  como ambos documentos identifican a la misma filial ("Filial La Vela"),
  el segundo se descartaba en silencio como si fuera la misma fuente que
  el primero. Se corrigió agregando la fecha del documento al
  `fuente_nombre` (ej. "Filial La Vela (28/07/2026)"), para que
  actualizaciones sucesivas de la misma filial cuenten como fuentes
  distintas en vez de perderse una.

### `scripts/fetch_gmail.py`

Ya no descarta los adjuntos: por cada correo no leído, si al menos un
adjunto de formato soportado produce un item válido, se usan esos items
en vez del texto libre del cuerpo (más confiable: trae ubicación, fecha
del documento y cifras ya extraídas). Si ningún adjunto produjo un item
utilizable (o no hay adjuntos), se usa el cuerpo en texto libre como
antes.

### `scripts/verify_ai.py`

`_finalizar_evento()` ahora propaga `es_reporte_filial` (true si alguna
fuente aprobada del evento viene de un adjunto de filial) y
`resumen_consolidado` al evento final. Cuando hay varias fuentes de
filial para el mismo evento (reporte inicial + actualización posterior),
se muestra **solo el resumen de la más reciente** — una actualización de
filial reemplaza las cifras anteriores, no se le suman como si fueran
corroboraciones independientes de dos medios de prensa distintos.

### `scripts/render.py`

`redactar_noticia()` distingue los eventos con `es_reporte_filial`:
título fijo por tipo (`REPORTE_FILIAL_TITULOS`, ej. "Reporte de personas
desplazadas" para `crisis_migratoria`, con fallback al formato genérico
para otros tipos), un distintivo "🏢 REPORTE DE FILIAL" al inicio de la
tarjeta, y un bloque "📋 Resumen consolidado" con las cifras seguras en
vez de la lista de "Fuentes" con enlaces — el enlace de un correo de
Gmail no es accesible para nadie más que el sistema, a diferencia del
enlace de un artículo de RSS.

Probado de punta a punta (adjunto → `clasificar_item()` →
`agrupar_y_verificar()` → `_finalizar_evento()` → `redactar_noticia()`)
con los 3 documentos reales de muestra que sí traen sección de totales
(dos reportes de La Vela sobre las mismas familias, correctamente
fusionados en un solo evento por `agrupar_y_verificar()`, y uno de Apure)
y confirmado el descarte fail-closed del cuarto documento de muestra (un
PDF del que `pypdf` no logra extraer ningún texto). Validado con
`python3 scripts/validar_configs.py` y una regresión de la ruta no-filial
de `redactar_noticia()` (sin cambios de comportamiento).

**Pendiente real**: falta la prueba con correos reales de Gmail (el
usuario va a reenviar todo su historial pendiente de reportes de
filiales) — el diseño está probado contra los documentos de muestra, pero
el formato exacto de cada filial puede variar.

---

## Primera prueba real con correos reenviados: 3 hallazgos (29-07-2026)

El usuario reenvió 5 correos reales a la cuenta de Gmail institucional
(remitente real: `sala.situacional.nacional@cruzroja.ve`). Resultado: solo
2 alertas publicadas (Falcón y Apure). Investigado con los logs de la
corrida y `data/historico_fuentes_texto.jsonl` (que guarda el texto
sintético ya seguro de cada fuente, nunca el documento original).

### 1. Fusión correcta, pero con una fuente de origen dudoso

La alerta de Falcón fusionó 3 fuentes (07/07, 28/07, y una tercera sin
fecha propia reconocible que usó la fecha de hoy como fallback, mencionando
"municipio Zamora" con cifras internamente contradictorias — "Familias: 22"
junto con "Número de familias: 17"). El usuario no reconoce ese tercer
documento como algo que haya enviado a propósito — sospecha de trabajo
pendiente de confirmar es que sea una copia duplicada de "Reporte # 4"
(28/07, que sí menciona Zamora y Tocopero de pasada) reenviada por
separado, con una estructura interna ligeramente distinta que hizo que la
extracción de cifras se confundiera. **No se pudo diagnosticar la causa
exacta sin acceso al archivo real** — queda pendiente que el usuario
confirme/reenvíe ese documento específico para reproducir el bug.

### 2. Reporte de Filial Puerto Píritu (cuerpo de correo, sin adjunto) nunca generó alerta

Diagnosticado y **no es un bug, es una limitación real de diseño**:
`detectar_ubicacion()` (`classify.py`) solo reconoce menciones explícitas
del nombre del ESTADO — nunca infiere el estado a partir de un municipio o
localidad mencionados solos. Un texto libre tipo "Filial Puerto Píritu
reporta familias desplazadas..." sin decir "Anzoátegui" en ningún lado no
genera ninguna ubicación, y el item se descarta en silencio (sin ningún
`[WARN]`, ya que `es_relevante()` filtra sin registrar nada).

Se evaluó agregar un mecanismo de inferencia (buscar un municipio/parroquia
conocido y deducir su estado) pero se descartó por **evidencia concreta de
riesgo real**, encontrada en la misma prueba:

- Un texto de prueba con la palabra genérica "comunidad" coincidió, por
  nombre, con una parroquia real llamada "Comunidad" en Amazonas.
- "Píritu" existe como municipio en **dos** estados distintos (Anzoátegui
  y Falcón) — un texto que solo dice "Puerto Píritu" es genuinamente
  ambiguo sin más contexto.

Con el historial de esta sesión de bugs de ambigüedad de nombres de
municipio/parroquia, no se consideró seguro implementar esto de forma
apresurada. **Mitigación práctica sin riesgo de código**: si un reporte de
filial llega solo en el cuerpo del correo (sin adjunto), el estado debe
mencionarse explícitamente en el texto (el usuario puede agregarlo al
reenviar si el reporte original no lo trae).

### 3. Contradicción entre "Ubicación" y "Albergados en" en la tarjeta — corregido

Cuando varias fuentes de filial del mismo evento mencionaban municipios
distintos (Colina vs. Zamora, dos reportes de la misma situación en
Falcón), el encabezado `📍 Ubicación:` (que usa `evento["municipio"]`,
calculado en `agrupar_y_verificar()` como el primer valor no nulo entre
las fuentes) podía no coincidir con `🏠 Albergados en:` del resumen
consolidado (que ya usaba la fuente más reciente, ver sección anterior).

**Corrección** (`scripts/verify.py`): `municipio`/`parroquia` del evento
ahora también se toman de la fuente más reciente (ordenando por fecha
antes de buscar el primer valor no nulo), igual que ya hacía
`resumen_consolidado` — ambos quedan siempre alineados a la misma fuente.

---

## Cambio de política: retener eventos en vez de publicarlos sin verificar cuando Groq falla (29-07-2026)

Al revisar las alertas del día a pedido del usuario ("muchas son
retrospectivas, falsas alertas"), se encontró la causa raíz real: **10 de
las 15 alertas publicadas ese día tenían `estado_verificacion:
PASADO_POR_FALLA_TECNICA`** — Groq agotó su límite de tasa (múltiples
"429" en casi todas las corridas) y el mecanismo de "fallar hacia lo
seguro" las dejó pasar **sin ninguna verificación de plausibilidad real**.
No era un problema de frecuencia de auditoría (la verificación de IA ya
corre en cada ciclo de 10 minutos) sino de que Groq está fallando la
mayoría de las veces.

El usuario eligió cambiar la política: en vez de publicar de inmediato sin
confirmar cuando Groq falla, **se retiene el evento hasta
`MAX_CICLOS_ESPERA_GROQ` (2) ciclos adicionales** (~20-30 min, el
monitoreo corre cada 10 min) para darle chance a que una corrida
posterior sí logre verificarlo con IA. Solo si sigue fallando tras agotar
esos reintentos se publica sin confirmar, como red de seguridad (nunca se
pierde un evento real solo porque Groq esté caído por más tiempo).

**Implementación** (`scripts/verify_ai.py`): nuevo archivo
`data/pendientes_verificacion.json` (persistido entre corridas por
`monitor.yml`, igual que `publicados.json`) que cuenta cuántos ciclos
lleva fallando cada cluster (clave `tipo::ubicacion::día`, se reinicia
sola cada día). `_manejar_falla_temporal()` centraliza la decisión
(retener vs. publicar) y reemplaza las dos llamadas que antes publicaban
de inmediato (JSON de veredictos inválido, y excepción de red/rate
limit). Cuando Groq sí responde con éxito se limpia cualquier pendiente
de ese cluster (`_limpiar_pendiente()`). El caso de `GROQ_API_KEY` no
configurada (falla permanente de configuración, no transitoria) se dejó
sin cambios — publica de inmediato, reintentar no ayudaría.

Probado directamente: 2 llamadas seguidas retienen (`None`), la 3ra
publica con `PASADO_POR_FALLA_TECNICA`. Validado con
`python3 scripts/validar_configs.py`.

---

## Bug real encontrado probando la retención con un correo real: se quedaba retenido para siempre (29-07-2026)

Al probar la política de retención de la sección anterior con un caso
real (el usuario reenvió un adjunto real de "Filial Puerto Píritu"),
Groq falló por límite de tasa y el evento quedó retenido en intento 1/2,
como se esperaba. Pero el ciclo siguiente **nunca llegó a reintentarlo**:
`fetch_gmail.py` marca cada correo como leído (`\Seen`) apenas lo procesa
una vez, exitosamente o no, así que el correo nunca se vuelve a leer en
una corrida posterior. La retención asume que el mismo cluster puede
"reaparecer" en el próximo ciclo -- cierto para RSS (el artículo sigue en
la ventana de búsqueda de horas) pero **falso para correos
institucionales**: sin el item original, el cluster nunca se reconstruye
y el evento queda retenido para siempre, sin publicarse jamás.

**Corrección** (`scripts/verify_ai.py`): `_manejar_falla_temporal()` ahora
revisa si el cluster completo proviene únicamente de fuentes de correo
(`fuente_tipo == "correo"` en todos sus miembros). Si es así, se publica
de inmediato sin confirmar (el comportamiento de antes de este cambio) en
vez de retenerlo -- retener solo tiene sentido para clusters que puedan
reaparecer (RSS, o correo mezclado con RSS). Probado directamente: un
cluster 100% de correo publica en el primer intento fallido, sin quedar
retenido.

**Nota para el reporte de Puerto Píritu ya afectado**: como el correo
original ya quedó marcado como leído durante el intento fallido, el fix
de código no lo revive automáticamente -- hace falta que el usuario
reenvíe el correo de nuevo (o lo marque como no leído en Gmail) para que
se vuelva a procesar, esta vez con la corrección ya desplegada.

---

## Auditoría diaria automática: 7 alertas erróneas encontradas y corregidas (29-07-2026)

Auditoría de rutina (tarea programada diaria) de las alertas publicadas en
las últimas ~24-48 horas, comparando cada una contra el texto real de sus
fuentes. Se encontraron y corrigieron 4 causas raíz distintas en el código,
que en conjunto habían generado 7 alertas falsas o mal ubicadas -- 6 de
las 7 tenían `estado_verificacion: PASADO_POR_FALLA_TECNICA` (nunca
pasaron por Groq), confirmando otra vez el patrón ya documentado: son
casos que la IA muy probablemente habría rechazado.

### 1. Boletín retrospectivo de corrección de epicentro generaba un "sismo nuevo"

Un artículo ("USGS ajusta el epicentro del terremoto en Venezuela: Se
ubicó en La Guaira y no en Yaracuy") sobre una corrección técnica del
epicentro de un sismo de magnitud 7.5 ocurrido **el 24 de junio** (más de
un mes antes) generó dos alertas nuevas de tipo sismo, una en La Guaira y
otra en Yaracuy (esta última en una ubicación que el propio texto niega
explícitamente: "y no en Yaracuy"). El texto contiene todas las palabras
de evidencia fuerte de sismo ("magnitud", "epicentro", "sacudió"), así que
ninguno de los mecanismos existentes lo descartaba.

**Causa raíz** (`scripts/classify.py`): no existía ningún filtro
determinista para boletines retrospectivos de sismo -- el único mecanismo
que los habría descartado es el juicio de la IA, que falló por límite de
tasa en ambas menciones.

**Corrección**: nueva función `_es_correccion_epicentro_retrospectiva()`,
con una lista de frases decisivas ("ajusta el epicentro", "corrigió el
epicentro", "reubicando el epicentro", etc.) que, a diferencia del
mecanismo existente de `_CONTEXTO_CONFLICTIVO_POR_TIPO`/
`_EVIDENCIA_FUERTE_POR_TIPO`, **no se anula por evidencia fuerte** --
precisamente porque esa evidencia (magnitud/epicentro/sacudió) describe el
sismo original que se está corrigiendo, no uno nuevo. Se aplica sobre el
texto completo del artículo (no sobre la ventana de proximidad de cada
estado): un artículo multi-estado puede mencionar la evidencia de que es
retrospectivo lejos, en términos de palabras, de alguna de las menciones
de estado, sin que eso lo vuelva un sismo nuevo para ese estado. Probado
con el caso real (ambas ubicaciones descartadas) y un caso de control
(sismo real nuevo con las mismas palabras de evidencia fuerte, se
mantiene).

### 2. Rescates de mascotas en escombros de un colapso viejo se clasificaban como derrumbe nuevo

Dos artículos de interés humano sobre mascotas rescatadas de los escombros
de un edificio colapsado por el mismo sismo de hace un mes ("Rescatan al
gato «Noche» tras sobrevivir 33 días bajo los escombros", "Rescatistas
hallan con vida a Mino, un gato atrapado entre los escombros de Catia La
Mar") generaron dos alertas de tipo deslizamiento -- una de ellas incluso
pasó la verificación de IA (`APROBADO_IA`).

**Causa raíz**: la palabra clave "escombros" (tipo deslizamiento) no
distingue entre un derrumbe ocurriendo ahora y una nota sobre el rescate
de una mascota de un colapso ya cubierto hace semanas.

**Corrección**: se agregó `deslizamiento` a `_CONTEXTO_CONFLICTIVO_POR_TIPO`
(marcadores: gato/gata/mascota/perro/felino/canino cerca de la palabra
clave) con su propia `_EVIDENCIA_FUERTE_POR_TIPO` (heridos, fallecidos,
viviendas colapsadas/destruidas, evacuados, familias afectadas) para que
un derrumbe real que además mencione una mascota de pasada no se
descarte. Probado con ambos casos reales (descartados), un derrumbe real
de control (se mantiene) y un derrumbe real que menciona un gato pero
también heridos/viviendas colapsadas (se mantiene, por evidencia fuerte).

### 3. Artículo desmintiendo rumores de Hantavirus generaba dos alertas "críticas" duplicadas

Un artículo titulado "Hantavirus: Enfermedad totalmente controlada en
Venezuela" -- que explícitamente dice que "no existen registros
confirmados por parte de MinSalud sobre la propagación de esta
enfermedad" y que solo desmiente rumores -- generó **dos** alertas
`salud_publica` con severidad `crítico` (Anzoátegui y Aragua, ambas
mencionadas en el mismo artículo), solo porque el texto mencionaba de
pasada "3 fallecidos" históricos por esta causa.

**Causa raíz**: la palabra "fallecidos" (severidad crítica) no distingue
un reporte de una crisis activa de un artículo que **desmiente** rumores
de una crisis, y el mecanismo de detección de tipo no tenía ningún filtro
de contexto para `salud_publica`.

**Corrección**: se agregó `salud_publica` a
`_CONTEXTO_CONFLICTIVO_POR_TIPO` (marcadores: "totalmente controlada",
"enfermedad controlada", "no existen registros confirmados", "brote
descartado", etc.) con su propia evidencia fuerte ("brote confirmado",
"casos confirmados", "declaró emergencia sanitaria", "cuarentena",
"hospitalizados") -- al descartarse el tipo, ambas menciones de estado
del mismo artículo quedan sin tipo y no generan ninguna alerta. Probado
con el caso real (ambas ubicaciones descartadas) y un caso de control
(brote real con casos confirmados y emergencia sanitaria declarada, se
mantiene).

### 4. Apellido "Bolívar" de un vocero citado se confundía con el estado Bolívar

Un artículo sobre un riesgo real de incomunicación en Río Chiquito
(municipio Piar, **estado Monagas**, dicho en el texto solo como "entidad
monaguense", nunca por su nombre) se publicó como alerta del **estado
Bolívar** (también con municipio "Piar", que por coincidencia existe en
ambos estados). La única mención de "Bolívar" en todo el artículo es el
apellido de un vocero citado dos veces: "El líder social de la zona,
Julián Bolívar, subrayó..." y, más adelante, "...alertó Bolívar."

**Causa raíz doble**:
- `config/estados.yaml` no tenía "monaguense" como alias de Monagas (el
  artículo nunca usa la palabra "Monagas" en sí), así que el único estado
  que el sistema podía detectar era el falso positivo.
- `scripts/classify.py` no distinguía una mención de un apellido de
  persona ("Julián **Bolívar**", "alertó **Bolívar**") de una mención real
  del estado -- varios nombres de estado (Bolívar, Miranda, Sucre...)
  también son apellidos comunes en Venezuela.

**Corrección**:
- `config/estados.yaml`: se agregó "monaguense" como alias de Monagas.
- `scripts/classify.py`: nueva función `_es_mencion_de_persona_citada()`,
  que descarta una mención de nombre de estado como evidencia de ubicación
  si tiene un verbo de atribución de cita justo antes o justo después
  ("dijo", "afirmó", "alertó", "subrayó"...) **y** la palabra
  inmediatamente anterior no es un calificador de lugar conocido (ciudad,
  estado, municipio, de, del...) -- esta segunda condición es la que evita
  descartar lugares reales como "Ciudad Bolívar" o "el gobernador de
  Bolívar, Fulano, dijo..." (que sí tiene un verbo de atribución cerca,
  pero "de" justo antes de "Bolívar" señala que es el estado, no un
  apellido). Probado con el caso real (ya no detecta Bolívar en absoluto),
  "Ciudad Bolívar" de control (se mantiene) y "el gobernador de Bolívar,
  Nombre, dijo..." de control (se mantiene).

  Con esta corrección, el artículo de Río Chiquito ya no genera ninguna
  alerta (ni Bolívar -- incorrecto -- ni Monagas): la mención de
  "monaguense" queda demasiado lejos (más de la ventana de proximidad de
  35 palabras) de la palabra clave "derrumbe", que aparece mucho más
  adelante en el artículo. Preferible a mantener la ubicación incorrecta;
  la ventana de proximidad es una limitación preexistente del sistema, no
  parte de esta corrección puntual.

### Corrección retroactiva

Se eliminaron por completo las 7 alertas afectadas de
`docs/data/noticias.json`, `data/historico_eventos.jsonl`,
`data/historico_fuentes_texto.jsonl`, `data/publicados.json` y las
entradas correspondientes de `data/pendientes_verificacion.json`:
`deslizamiento::Bolivar::2026-07-29` (Piar/Río Chiquito),
`sismo::La Guaira::2026-07-29::mag7.5`, `sismo::Yaracuy::2026-07-29::mag7.5`,
`deslizamiento::Distrito Capital::2026-07-29` (gato Noche),
`deslizamiento::La Guaira::2026-07-29` (gato Mino),
`salud_publica::Anzoategui::2026-07-29` y `salud_publica::Aragua::2026-07-29`
(hantavirus). No había ningún informe narrativo en
`docs/data/informes/` construido a partir de estos eventos. Se regeneró
`docs/data/estadisticas.json` con `python3 scripts/build_dashboard.py`
(total de eventos: 32 → 25).

Se corrió una regresión completa de `clasificar_item()` contra el texto
real de las 32 fuentes ya registradas en
`data/historico_fuentes_texto.jsonl`: los únicos cambios de tipo/ubicación
fueron los 7 casos corregidos aquí; ningún otro evento ya publicado
cambió. Validado con `python3 scripts/validar_configs.py`.

### Nota: caso ya documentado, sin cambios

La alerta `crisis_migratoria::Falcon::2026-07-07` (cifras internamente
contradictorias entre fuentes de filial) sigue pendiente de que el
usuario confirme/reenvíe el documento original, tal como se documentó en
la sesión anterior ("Primera prueba real con correos reenviados"). No se
tocó en esta auditoría.

---

## Plan de confiabilidad: suite de regresión + IA de respaldo (30-07-2026)

A pedido del usuario, tras una evaluación de la evolución del sistema
(¿los errores se resuelven eficientemente, o es la misma debilidad
repitiéndose?), se diseñaron dos mecanismos para atacar el patrón
identificado: la mayoría de los "errores nuevos" de cada auditoría son
manifestaciones nuevas de un puñado de debilidades estructurales
recurrentes (ambigüedad de nombres de ubicación, palabras clave
demasiado genéricas, artículos retrospectivos), no bugs realmente
aislados. El diseño completo, con justificación y detalle de
implementación, quedó en `docs/plan_confiabilidad_clasificacion.md` (no
se duplica aquí para no desincronizar dos fuentes de verdad).

**Implementado en esta sesión**: la suite de regresión persistente
(`tests/`, 80 pruebas, corre en CI vía `validar.yml`) — automatiza el
paso de "regresión contra el histórico real" que cada sesión de auditoría
venía repitiendo a mano, y deja un formato (`casos_clasificacion.jsonl`)
para que futuras correcciones agreguen su caso real + control de forma
ejecutable en vez de solo en prosa.

**Diseñado, pendiente de decisión del usuario**: un proveedor de IA de
respaldo para `verify_ai.py`, para que la verificación de Groq deje de
ser el eslabón más frágil (la mayoría de los falsos positivos recientes
son casos que la IA probablemente habría rechazado si hubiera llegado a
evaluarlos, pero falló por límite de tasa). No implementado — depende de
que el usuario elija un proveedor/consiga una API key, o decida subir de
plan en Groq.

---

## Decisión: no proceder con el proveedor de IA de respaldo por ahora (30-07-2026)

Seguimiento del plan de confiabilidad de la sección anterior. Al
comparar opciones concretas (Gemini vs. subir de plan en Groq), el
usuario decidió **no implementar el mecanismo A por ahora**: *"no quiero
pagar eso con mi tarjeta de crédito porque si me voy de la CRV el
sistema colapsaría"* — atar la confiabilidad del sistema a una tarjeta o
cuenta personal reemplaza el punto único de falla actual (`GROQ_API_KEY`)
por otro igual de fràgil, no lo resuelve. Aplica también a un segundo
proveedor gratuito (Gemini incluido): aunque su nivel gratuito no exige
tarjeta, seguiría dependiendo de una cuenta personal salvo que la CRV
tenga una cuenta institucional propia, algo no evaluado en esta sesión.

El diseño técnico completo queda documentado en
`docs/plan_confiabilidad_clasificacion.md` para retomarse si la
organización dispone en el futuro de un método de pago o cuenta
institucional propia. Sin código nuevo en esta sesión — es una decisión
de alcance, no un fix.

---

## Auditoría de 3 alertas erróneas adicionales tras revisión del usuario (30-07-2026)

El usuario revisó el sitio en vivo y señaló 3 alertas concretas que la
auditoría del día anterior no había atrapado, más un cuarto pedido
(evaluar el medio "Noticia al Dia"). Investigadas a fondo, las 3 eran
errores reales — dos de ellas ya habían sido revisadas el día anterior y
descartadas como "borderline, no tocar" con un criterio demasiado laxo.

### 1. Reportaje retrospectivo de una avería de 5 meses se publicaba como falla nueva

"Falla de agua en Sucre" venía de un reportaje titulado "Cinco meses de
espera: así aprendieron los cumaneses a vivir sin agua" — un artículo de
seguimiento sobre una avería del sistema Turimiquire de hace 5 meses, sin
ningún desarrollo nuevo el día de publicación. El sistema lo publicaba
como si el corte hubiera empezado esa misma mañana ("🕒 Hecho reportado:
29/07/2026, 9:01 a.m."). Ya se había revisado el 29-07-2026 y se dejó
pasar por "ser real y no estar exagerado" — un criterio insuficiente: lo
que importa no es si la crisis es real, sino si el artículo reporta algo
**nuevo** hoy.

**Causa raíz** (`scripts/classify.py`): ningún mecanismo generalizaba el
filtro de "boletín retrospectivo" (agregado el 29-07-2026, pero limitado
a sismo/corrección de epicentro) a otros tipos de emergencia.

**Corrección**: nueva función `_es_articulo_retrospectivo_larga_duracion()`,
con marcadores de reportaje-de-seguimiento sobre una crisis crónica
("meses de espera", "años de espera", "así aprendieron", "aprendieron a
vivir") — a diferencia de `_CONTEXTO_CONFLICTIVO_POR_TIPO`, es una señal
decisiva (no se anula por evidencia fuerte) y **aplica a cualquier tipo**,
no solo a sismo, porque la señal ("esto es un reportaje sobre algo viejo")
no depende de la categoría de la emergencia. Probada con el caso real
(descartado) y una falla de agua nueva de control (causa puntual de hoy,
se mantiene).

### 2. Artículo de ayuda humanitaria en curso se publicaba como salud pública

"Salud pública en Parroquia Caraballeda..." venía de un artículo sobre
brigadistas voluntarios pidiendo donaciones para armar kits de higiene
"para prevenir enfermedades" — ayuda humanitaria en curso post-terremoto,
sin ningún caso o brote real. La palabra "enfermedades" en una frase
puramente preventiva disparaba el tipo. El usuario no pudo abrir el
enlace originalmente (funcionaba al reintentar; se confirmó el contenido
con el texto completo del artículo, no solo el resumen truncado del RSS).

**Corrección** (`scripts/classify.py`): se agregaron "prevenir
enfermedades"/"prevenir la propagación" a la lista de contexto
conflictivo ya existente de `salud_publica` (creada el 29-07-2026 para el
caso de Hantavirus) — reutiliza la misma evidencia fuerte ya definida
("brote confirmado", "casos confirmados", etc.), sin necesidad de
arquitectura nueva.

### 3. Bug real en la fusión de fuentes: municipio y parroquia de reportes distintos, combinados sin validar que fueran el mismo lugar

El usuario notó que la alerta de crisis migratoria en Falcón mostraba
"📍 Ubicación: Parroquia Las Calderas, Municipio Colina" pero el resumen
consolidado (de la fuente más reciente) decía "🏠 Albergados en: municipio
Zamora". Al investigar con el código actual (no solo los datos ya
publicados), se confirmó que **no era solo un dato viejo sin corregir
retroactivamente** — es un bug real y todavía vigente en
`scripts/verify.py`: `agrupar_y_verificar()` elegía el municipio del
miembro más reciente que lo tuviera, y la parroquia del miembro más
reciente que la tuviera, **cada uno por separado**, sin exigir que
vinieran del mismo miembro ni verificar que la parroquia perteneciera al
municipio elegido. Con 3 reportes de la misma filial (07/07: "parroquia
Las Calderas, municipio Colina"; 28/07: "municipio Colina"; 29/07:
"municipio Zamora", sin parroquia), el resultado combinado terminaba en
"Municipio Zamora, Parroquia Las Calderas" — una combinación que no
existe (Las Calderas es parroquia de Colina, no de Zamora, confirmado
contra `config/ubicaciones_detalle.json`).

Es la misma clase de bug que la jerarquía real INE ya corrigió el
27-07-2026 (nunca combinar municipio y parroquia de fuentes distintas sin
verificar la relación entre ambos) — pero esa corrección se aplicó dentro
de `classify.py` (un solo texto), no al **fusionar varias fuentes ya
clasificadas por separado** en `verify.py`, que es un lugar de código
distinto donde el mismo problema podía reaparecer.

**Corrección** (`scripts/verify.py`, `agrupar_y_verificar`): la parroquia
del evento fusionado ahora solo se acepta de un miembro cuyo propio
municipio coincida con el municipio ya elegido (o que no declare ninguno)
— nunca de un miembro con un municipio distinto. Probado con el caso real
(ahora da "Municipio Zamora, sin parroquia" en vez de la combinación
inválida) y un caso de control (dos fuentes del mismo municipio, una con
parroquia y otra sin ella — la parroquia se sigue conservando
correctamente cuando sí pertenece al municipio elegido).

### Corrección retroactiva

Se eliminaron por completo `infraestructura_agua::Sucre::2026-07-29` y
`salud_publica::La Guaira::2026-07-29` de `docs/data/noticias.json`,
`data/historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl`,
`data/publicados.json` y `data/pendientes_verificacion.json`. La alerta
de Falcón (`crisis_migratoria::Falcon::2026-07-07`) **no se eliminó** —el
evento en sí es real (hay familias desplazadas)— se corrigió su
municipio/parroquia a "Zamora"/`null` en `docs/data/noticias.json`
(regenerando `titulo`/`texto`) y `data/historico_eventos.jsonl`, quedando
alineada con el resumen consolidado. Se regeneraron las estadísticas.

Se agregaron los 3 casos reales + 2 controles a
`tests/casos_clasificacion.jsonl`, y un archivo nuevo
`tests/test_verify_agrupacion.py` (primera prueba de `verify.py` en la
suite — hasta ahora solo cubría `classify.py`/`verify_ai.py`) con el caso
real de la fusión de municipio/parroquia y su control. 83 pruebas en
total, todas pasan.

### Evaluación del medio "Noticia al Dia" (Zulia): sin evidencia suficiente para penalizarlo

El usuario sospechaba que `noticialdia.com` genera muchas falsas
alertas — en efecto fue la fuente de la alerta de Caraballeda corregida
arriba. Se revisó su peso actual (`config/sources.yaml`: 0.55, el nivel
**más común** entre las ~62 fuentes configuradas, no una excepción) y su
historial completo en `data/historico_fuentes_texto.jsonl` y en todo
`docs/roadmap_evolucion.md`.

**Hallazgo**: solo aparece en **2 eventos** en toda la historia del
sistema (~5 días de operación) — el falso positivo de hoy, y un
verdadero positivo real y grave ("Niña muere ahogada tras crecida súbita
del río La Miel en Lara", 26-07-2026, correctamente clasificado como
crítico). Con una muestra de 2 casos, uno de cada tipo, **no hay
evidencia de un patrón sistémico** que justifique bajar su peso — hacerlo
con esta muestra sería sobreajustar a un solo caso. Además, el falso
positivo de hoy ya se corrigió en la raíz (el filtro de "prevenir
enfermedades" en `classify.py`, que aplica a **cualquier** fuente, no
solo a esta), así que penalizar el medio no habría evitado nada que el
fix de tipo no evite ya, y sí podría hacer que una futura alerta real y
grave de este medio (como la de Lara) pese menos de lo que debería.

**Decisión**: no se ajusta el peso de esta fuente. Si en el futuro
aparecen más falsos positivos de `noticialdia.com` que no queden
cubiertos por fixes de causa raíz en `classify.py`/`verify_ai.py`, ahí sí
valdría la pena reconsiderar su peso con una muestra más grande.

---

## Auditoría diaria automática: 4 alertas erróneas y un bug de deduplicación que borraba una alerta ya validada (30-07-2026)

Auditoría de rutina (autónoma, sin pedido del usuario) sobre las alertas
publicadas en las últimas ~24-48 horas, comparando cada una contra el
texto real de sus fuentes. Se encontraron 4 errores de clasificación y,
al investigar uno de ellos a fondo, un bug de deduplicación en
`state.py` con un efecto mucho más serio: pérdida silenciosa de una
alerta ya publicada y validada.

### 1. Boletín epidemiológico nacional generaba una alerta de salud pública en el estado equivocado

"Aumentan los casos de enfermedades diarreicas en Venezuela" es un
boletín epidemiológico del Ministerio de Salud que compara la tasa de
contagio de **todos** los estados contra la media nacional -- una tabla,
no el reporte de un evento en un estado concreto. El propio artículo cita
al Ministerio de Salud descartando explícitamente cualquier alarma
sanitaria por el repunte ("se descarta alguna alarma sanitaria... se
entiende como algo normal durante la temporada de lluvias"). El sistema
igual generó una alerta de `salud_publica` para **Apure** -- el estado
que, por pura coincidencia del orden del listado ("el primero que aparece
por debajo de la media nacional"), quedó más cerca de la palabra clave
"enfermedades" dentro de la ventana de proximidad de 35 palabras. Ni
Amazonas (la tasa más alta del país) ni ningún otro estado del listado
generó alerta -- el "seleccionado" no tenía ninguna relación real con un
evento en Apure.

**Causa raíz**: la ventana de proximidad de `_CONTEXTO_CONFLICTIVO_POR_TIPO`
(usada para los filtros de "Hantavirus"/"prevenir enfermedades" del
29-07-2026) solo mira el fragmento cercano a la ubicación detectada -- la
frase que descarta la alarma sanitaria estaba varios párrafos antes de
"Apure" (después de la lista completa de 11 estados), fuera de esa
ventana, así que nunca llegaba a evaluarse para ese estado en particular.

**Corrección** (`scripts/classify.py`): nueva función
`_es_boletin_estadistico_salud_sin_alarma()`, con el mismo patrón que el
filtro de corrección de epicentro retrospectivo de sismo (decisiva,
evaluada contra el **artículo completo**, no solo la ventana de un
estado) -- porque la señal ("este artículo es una tabla estadística sin
alarma, no una emergencia localizada") es una propiedad del artículo
entero, no de la mención puntual de un estado. Requiere un marcador de
boletín estadístico ("boletín epidemiológico", "media nacional", "por
cada 100.000/100 mil habitantes") **y** un marcador explícito de "sin
alarma" ("descarta alguna/cualquier alarma sanitaria", "sin alarma
sanitaria"...); se anula si hay evidencia fuerte real (brote/casos
confirmados, emergencia sanitaria declarada, cuarentena, hospitalizados),
reusando la misma lista ya definida para `salud_publica`. Probado con el
caso real (Apure ya no genera alerta) y un caso de control (el mismo tipo
de boletín, pero con una emergencia sanitaria real y localizada
declarada en un estado, sigue alertando).

### 2. Nota de protesta diplomática se publicaba como orden público -- y sin pasar por la IA

"Venezuela entregó nota de protesta a Irán por declaraciones de su
canciller" es una noticia diplomática sin ninguna relación con disturbios
civiles en Venezuela. Generó una alerta de `orden_publico` solo por la
palabra "protesta", y además se publicó como `PASADO_POR_FALLA_TECNICA`
(sin pasar por la verificación de IA) -- exactamente el patrón que la
tarea de auditoría advierte revisar con más cuidado, y en efecto ahí
apareció el error.

**Causa raíz**: "protesta"/"protestas" es palabra clave de `orden_publico`
sin ningún filtro de contexto -- el mismo tipo de ambigüedad ya conocida
para "manifestaciones" (que por eso se excluye sola de los keywords desde
antes), pero nunca aplicada a "nota de protesta".

**Corrección** (`scripts/classify.py`): se agregó `orden_publico` a
`_CONTEXTO_CONFLICTIVO_POR_TIPO` (marcadores "nota de protesta"/"notas de
protesta") con su propia `_EVIDENCIA_FUERTE_POR_TIPO` (heridos, detenidos,
saqueo, disturbios, tiroteo, enfrentamiento) para no descartar un
artículo que además de la nota diplomática describa disturbios reales.
Probado con el caso real (ya no genera alerta) y un caso de control (nota
de protesta diplomática + disturbios reales explícitos en un estado,
sigue alertando).

### 3. "avenidas Bolívar" (plural) esquivaba la lista negra y duplicaba un incendio real bajo el estado equivocado

Un incendio en el centro comercial Los Cedros de Porlamar (estado
**Nueva Esparta**, Isla de Margarita) ya se había publicado
correctamente bajo `incendio::Nueva Esparta::2026-07-30` con 2 fuentes.
Una tercera fuente sobre el mismo incendio, que solo menciona la
ubicación como "la intersección de las **avenidas** Bolívar y Raúl
Leoni en Porlamar", generó una alerta **duplicada** bajo
`incendio::Bolivar::2026-07-30` -- el mismo incendio, publicado dos
veces, una bajo el estado correcto y otra bajo un estado que no tiene
nada que ver.

**Causa raíz**: `LISTA_NEGRA_POR_ESTADO["Bolivar"]` ya tenía "avenida
bolivar" (singular) para evitar justo este tipo de confusión -- pero es
una comparación de substring literal, y "avenida" no es substring de
"avenidas" (falta la "s" antes del espacio). El plural, muy común cuando
se listan dos avenidas juntas ("avenidas X y Y"), se colaba sin que la
lista negra lo detectara.

**Corrección** (`scripts/classify.py`): se agregó "avenidas bolivar" a
la lista negra. Probado con el caso real (ya no se detecta el estado
Bolívar en ese texto) y un caso de control (un incendio real y genuino en
el estado Bolívar, sin mención de la avenida, se sigue detectando
normalmente).

### 4. Homicidio con machete se publicaba con severidad SIN CLASIFICAR

"Discusión por tierras termina con un sexagenario asesinado a
machetazos en Lara" -- un artículo sobre un homicidio real ("le propinó
una herida mortal a la altura del cuello") se publicó con severidad
`sin_clasificar` en vez de `critico`.

**Causa raíz**: la lista de palabras clave de severidad crítica
(`config/keywords.yaml`) cubría "fallecidos/murió/perdió la vida" y
similares, pero no "asesinado"/"asesinato" ni "herida mortal" -- formas
muy comunes de reportar un homicidio en la prensa venezolana que nunca
usan la palabra "fallecido" en sí.

**Corrección** (`config/keywords.yaml`): se agregaron "asesinado(s/a/as)",
"asesinato(s)", "herida(s) mortal(es)" y "muerte violenta" a la severidad
`critico`. Probado con el caso real (ahora `critico`) y un caso de
control sintético distinto (mismo patrón, sin ninguna otra palabra de
severidad crítica presente).

### 5. Intoxicación por monóxido de carbono en un incendio se publicaba con severidad SIN CLASIFICAR

"Reportan 5 personas afectadas tras el incendio en una librería del
CCCT": el texto (ya disponible al clasificador, no truncado) dice que
las 5 personas "resultaron afectadas al inhalar monóxido de carbono" y
"recibieron atención médica" -- un daño real por inhalación de humo, que
se publicó igual con severidad `sin_clasificar` porque ninguna palabra
de severidad alta ("heridos"/"lesionados"/"hospitalizados") cubre la
inhalación de humo/monóxido de carbono, un patrón de lesión muy común y
específico de incendios.

**Corrección** (`config/keywords.yaml`): se agregaron "inhalar/inhalación
de monóxido de carbono" e "intoxicados/intoxicadas por humo" a la
severidad `alto`. Probado con el caso real (ahora `alto`) y un caso de
control sintético en otro estado.

### 6. Bug real y más serio, encontrado al investigar el caso 5: `state.py` fusionaba incendios distintos y borraba la alerta más antigua

Al revisar por qué el incendio del CCCT (5 personas, 30-07) tenía la
clave `incendio::Distrito Capital::2026-07-29` -- un día antes de su
propia fecha -- se encontró que esa clave pertenecía originalmente a
un evento **completamente distinto**: una explosión de una bombona de
gas en la avenida Nueva Granada (29-07, 17:06, severidad `alto`, **dos
heridos**, ya corroborada por 3 fuentes independientes, `score` 1.65).

`state.py` tiene un mecanismo (`_resolver_clave`, `VENTANA_HORAS_MISMO_EVENTO
= 36`) que reutiliza la clave de un evento ya publicado del mismo
tipo+ubicación si cae dentro de 36 horas, para tratar coberturas de
varios medios sobre el **mismo** hecho como una sola alerta actualizada
en vez de una duplicada. El incendio del CCCT (30-07, 14:46 -- unas 21
horas después de la explosión de gas) cayó dentro de esa ventana, y al
compartir tipo (`incendio`) y ubicación (`Distrito Capital`) con la
explosión de gas, el sistema lo trató como "el mismo evento, actualizado"
y **sobrescribió silenciosamente** la alerta de la explosión de gas --
que desapareció por completo del sitio público, reemplazada por un
incendio no relacionado con menor severidad conocida en ese momento.

Esto ya se había identificado como un problema real para otros tipos:
`TIPOS_SIN_VENTANA_MISMO_EVENTO` ya excluía `sismo` y `orden_publico` de
esta ventana de 36h, con el mismo razonamiento ("el mismo tipo+ubicación
puede repetirse genuinamente día a día, y agruparlos ocultaría eventos
reales distintos") -- pero `incendio` se quedó fuera de esa lista, y es
exactamente el mismo patrón: un estado populoso como Distrito Capital
puede tener varios incendios/explosiones genuinamente distintos en menos
de 36 horas.

**Corrección** (`scripts/state.py`): se agregó `incendio` a
`TIPOS_SIN_VENTANA_MISMO_EVENTO`, siguiendo el mismo criterio ya
establecido para sismo/orden_publico. Primera prueba de `state.py` en la
suite (`tests/test_state.py`): reproduce el caso real (dos incendios
distintos en 36h ya no comparten clave), un control de que la ventana de
"mismo evento" sigue funcionando para tipos no excluidos (inundación), y
un control de que `filtrar_nuevos()` sigue tratando un segundo incendio
como nuevo aunque tenga la misma severidad que el anterior.

**Corrección retroactiva de la alerta perdida**: se reconstruyó la
alerta de la explosión de gas a partir de `data/historico_eventos.jsonl`
(la entrada original de esa corrida nunca se modificó ni se borró --
solo dejó de reflejarse en `docs/data/noticias.json`/`data/publicados.json`
al ser sobrescrita en corridas posteriores) y
`data/historico_fuentes_texto.jsonl`, y se publicó de nuevo bajo su
propia clave `incendio::Distrito Capital::2026-07-29` (`alto`, sin
confirmar porque `PASADO_POR_FALLA_TECNICA` fuerza `confirmado=false`
sin importar el score, 3 fuentes, municipio Libertador/parroquia San
Pedro). El incendio del CCCT se re-etiquetó con su propia clave real
`incendio::Distrito Capital::2026-07-30`. **Limitación de la
reconstrucción, documentada por transparencia**: el registro histórico
no guarda la hora exacta de publicación de cada fuente individual (solo
la fecha del evento más reciente del grupo), así que las 3 fuentes de la
explosión de gas quedaron con la misma fecha aproximada
(2026-07-29T17:06:27Z) en vez de sus horas reales de publicación
-- sin efecto visible en el sitio público, que no muestra fecha por
fuente individual en el texto renderizado.

### Corrección retroactiva (hallazgos 1-3)

Se eliminaron por completo `salud_publica::Apure::2026-07-30`,
`orden_publico::Distrito Capital::2026-07-29` (nota de protesta) e
`incendio::Bolivar::2026-07-30` (duplicado) de `docs/data/noticias.json`,
`data/historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl` y
`data/publicados.json`. Se corrigió la severidad de
`orden_publico::Lara::2026-07-30` a `critico` y de la alerta del CCCT
(reclavada a `incendio::Distrito Capital::2026-07-30`) a `alto`, ambas
regenerando `titulo`/`texto` con `render.redactar_noticia()`. Se
regeneró `docs/data/estadisticas.json` con
`python3 scripts/build_dashboard.py` (total de eventos: 34 → 31 en el
log histórico; 34 → 32 en el sitio público, que ahora sí distingue los
dos incendios de Distrito Capital como eventos separados).

Se agregaron los 5 casos reales + 5 controles a
`tests/casos_clasificacion.jsonl` (106 pruebas en total con
`tests/test_state.py`, todas pasan) y se corrió una regresión completa de
`clasificar_item()` contra el texto real de las 31 fuentes restantes en
`data/historico_fuentes_texto.jsonl`: ningún otro evento ya publicado
cambió de tipo/ubicación. Validado con `python3 scripts/validar_configs.py`.

**Nota sobre los informes narrativos**: `docs/data/informes/2026-07_orden_publico.json`
todavía menciona la nota de protesta ya retractada (su narrativa se
generó con Groq antes de esta corrección). No se regeneró en esta sesión
porque requiere `GROQ_API_KEY` (no disponible en este entorno) -- pero
`scripts/build_informes.py` regenera el informe del mes en curso como
máximo una vez por día, y la próxima corrida de producción lo hará
automáticamente a partir de los datos ya corregidos en
`data/historico_fuentes_texto.jsonl`.

---

## Auditoría diaria automática (31-07-2026): roadmap corrompido, dos falsos positivos de "enfrentamiento", severidad faltante y hallazgos pendientes de discutir

### 0. `docs/roadmap_evolucion.md` se había corrompido a un solo placeholder

Al empezar esta auditoría, `docs/roadmap_evolucion.md` en `main` contenía
literalmente la palabra `PLACEHOLDER` (11 bytes) en vez de todo su
historial. La causa fue una restauración manual fallida en la sesión
anterior: el commit `44bb053` había recuperado el contenido completo tras
un primer incidente ("Fix: pushed placeholder by mistake in previous
commit"), el commit `6998cb5` agregó más contenido ("part 1+2 of 5"), pero
el commit `e385172` ("part 4 of 5") sobrescribió por error el archivo
entero con un solo placeholder, borrando 1714 líneas. Ninguno de esos
commits llegó a completar la restauración (nunca hubo "part 3" ni "part
5"), y el archivo quedó así en `main`.

**Corrección**: se recuperó el contenido completo (3195 líneas) del commit
`3d62c74` (el padre de `2f9b136`, el commit donde el archivo se reemplazó
por primera vez por un placeholder) — la última versión íntegra conocida,
anterior a todo el incidente. Se restauró tal cual, sin reescribir nada
existente, como base para seguir agregando entradas nuevas (esta misma).

### 1. Falso positivo recurrente de `orden_publico`: la palabra "enfrentamiento" sola no distingue un disturbio civil de una disputa personal o un operativo policial

Se encontró publicada la alerta "Orden público en Lara" (31-07-2026,
fuente Nuevo Día): el texto real es un hombre de 62 años asesinado a
machetazos por un vecino en una disputa de linderos de terreno — un
homicidio individual, un asunto criminal entre dos personas, no un
disturbio civil que le competa al sistema de alertas. Se encontró también
"Orden público en Monagas" (30-07-2026, fuente Primicia): el texto es un
operativo antidrogas exitoso ("Diosdado Cabello informó... incautación de
más de 3,3 toneladas de cocaína... se registraron enfrentamientos con
presuntos implicados, quienes lograron escapar") — una nota de éxito
policial, no un disturbio.

**Causa raíz**: `config/keywords.yaml` tenía "enfrentamiento"/
"enfrentamientos" como palabra disparadora suelta del tipo `orden_publico`
— la misma clase de ambigüedad idiomática ya identificada antes para
"manifestaciones" y "explosión": la palabra es igual de común en un
disturbio civil real que en una pelea entre dos vecinos o un choque entre
policías y delincuentes durante un operativo, ninguno de los cuales es el
tipo de emergencia colectiva que el sistema debe alertar.

**Se descubrió, además, que este caso ya se había "corregido" dos veces
sin arreglar la causa raíz**: la sesión inmediatamente anterior (mismo
día, 31-07-2026) encontró el mismo problema y lo parchó borrando las filas
de `docs/data/noticias.json` directamente, dos veces (PR #114 para el
evento del 30-07, PR #115 para el del 31-07), sin tocar
`config/keywords.yaml`/`classify.py` ni `data/historico_eventos.jsonl`/
`data/historico_fuentes_texto.jsonl`/`data/publicados.json`, y sin
documentar nada en este roadmap. Como la causa raíz seguía intacta, la
siguiente corrida de producción (20:46 UTC) volvió a detectar y publicar
la misma noticia del machete como alerta nueva — es la que esta sesión
encontró. Los casos de prueba de `tests/casos_clasificacion.jsonl`
tampoco se habían corregido: uno de ellos (agregado el 30-07-2026, ver
"hallazgo 4" de esa fecha) esperaba explícitamente `tipos: ["orden_publico"]`
para este mismo patrón de homicidio por disputa de tierras — esa
expectativa, no solo la severidad, era el error real.

**Corrección** (`config/keywords.yaml`): se quita "enfrentamiento"/
"enfrentamientos" de los disparadores de tipo de `orden_publico`. Se
conserva en `_EVIDENCIA_FUERTE_POR_TIPO["orden_publico"]` (`classify.py`)
sin cambios, para no perder un disturbio civil genuino que además la
mencione junto a otra palabra de la lista (p. ej. "protesta"/"disturbios"
ya disparan el tipo; "enfrentamiento" solo confirma severidad/evidencia
cuando el contexto lo pone en duda, no dispara el tipo por sí sola).

**Pruebas**: se corrigió el caso de test existente (que esperaba
`orden_publico` para el homicidio del 30-07) a `tipos: [], relevante:
false`, y se agregaron 3 casos nuevos a `tests/casos_clasificacion.jsonl`:
el homicidio del 31-07 (Nuevo Día), el operativo antidrogas de Monagas, y
un caso de control (un enfrentamiento colectivo real entre bandas con
"disturbios"/"saqueos"/heridos sigue detectándose como `orden_publico` —
quitar la palabra disparadora no rompe la detección de disturbios civiles
genuinos). Regresión completa contra las 33 fuentes de
`data/historico_fuentes_texto.jsonl`: solo cambiaron los 2 casos
corregidos, ningún otro evento se vio afectado. `python3
scripts/validar_configs.py` → OK. 112 pruebas pasan (1 xfail conocido, sin
relación).

**Corrección retroactiva**: se eliminaron por completo `orden_publico::Lara::2026-07-30`,
`orden_publico::Monagas::2026-07-30` y `orden_publico::Lara::2026-07-31`
(las 2 detecciones del mismo evento) de `docs/data/noticias.json`,
`data/historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl` y
`data/publicados.json`. Se actualizó `docs/data/informes/2026-07_orden_publico.json`
(se quitó la fuente del operativo antidrogas, `total_eventos` 9→8,
`comparacion_mes_anterior.actual` corregido a 8 -- ya estaba desincronizado
de `total_eventos` desde la corrección parcial anterior, mismo patrón de
desface ya visto antes en `2026-07_general.json`) y `docs/data/informes/index.json`
(mismo conteo). Se regeneró `docs/data/estadisticas.json` con `python3
scripts/build_dashboard.py`.

### 2. Deslizamiento en Táchira con vía destruida y familias damnificadas se publicaba con severidad SIN CLASIFICAR

"Alerta en Táchira: Al menos 1.300 familias incomunicadas y varias
damnificadas deja deslizamiento de terreno... Completamente destruido
quedó un tramo de la vía principal..." se publicó con severidad
`sin_clasificar` pese a describir un daño de infraestructura mayor
afectando a miles de familias.

**Causa raíz**: ninguna palabra de la lista de severidad `alto` cubría
"damnificado/a" — un término estándar y sin ambigüedad idiomática en la
prensa venezolana para víctimas de un desastre con daño material o
desplazamiento.

**Corrección** (`config/keywords.yaml`): se agregó "damnificado(s/a/as)"
a la severidad `alto`. Se evaluó deliberadamente NO agregar
"incomunicado/a" (ambiguo: también se usa para presos incomunicados, sin
relación con desastres).

**Pruebas**: caso real (ahora `alto`) y un caso de control ("damnificadas"
sin ningún tipo de emergencia presente no genera alerta). Regresión
completa sin otros cambios. `python3 scripts/validar_configs.py` → OK.

**Corrección retroactiva**: severidad actualizada a `alto` en
`docs/data/noticias.json` (texto regenerado con `render.redactar_noticia()`),
`data/historico_eventos.jsonl` y `data/historico_fuentes_texto.jsonl`.
Estadísticas regeneradas.

### 3. Hallazgo pendiente de discutir (NO corregido): reportes de filial agrupados sin ventana de tiempo pueden mezclar actualizaciones de hasta 22 días de diferencia

La alerta "Reporte de personas desplazadas" (municipio Zamora, Falcón,
`PASADO_POR_FALLA_TECNICA`) combina 3 correos de la misma filial
institucional (Cruz Roja) fechados 07-07, 28-07 y 29-07-2026 -- 22 días
de diferencia entre el primero y el último -- en un solo evento con
`num_fuentes: 3` y un `resumen_consolidado` con cifras que no calzan
claramente entre sí (Familias: 22 / Número de familias: 17 / Total de
familias: 111; Personas: 42 / Total de personas: 229).

**Por qué no se corrigió a ciegas**: `verify.agrupar_y_verificar()` agrupa
por `(tipo, ubicación)` dentro de los items ya recolectados en una corrida,
sin ninguna ventana de tiempo -- a diferencia de `state._resolver_clave()`
(ventana de 36h entre corridas). No está claro si el comportamiento
correcto para reportes de filial es exactamente este (consolidar
actualizaciones sucesivas de la misma situación de albergue, que es
además el propósito explícito de `resumen_consolidado`) o si 22 días es
demasiado para asumir que se trata de la misma situación sin verificarlo
-- cambiarlo sin saber la intención real de las filiales al reenviar estos
reportes arriesga romper la consolidación legítima que el sistema ya hace
a propósito. Queda documentado aquí para que el usuario decida si aplica
una ventana de tiempo a los reportes de filial (y de cuánto), o si el
comportamiento actual es intencional y las cifras dispares ameritan más
bien un ajuste al formato del resumen consolidado.

### 4. Hallazgo de proceso, fuera del alcance de esta auditoría (NO modificado): workflow de auto-aprobación/auto-merge agregado por la sesión anterior

La sesión inmediatamente anterior (31-07-2026, junto con los parches
incompletos del hallazgo 1) agregó `.github/workflows/auto-cleanup.yml`
(PR #116): aprueba y fusiona automáticamente, sin revisión humana, CUALQUIER
pull request cuyo título o cuerpo contenga "remove", "cleanup" o
"non-alert" -- usando una GitHub Action de terceros
(`hmarroqq/auto-approve-action@v3.2`) para auto-aprobar y `gh pr merge
--auto --merge` para fusionar. El único chequeo que corre en paralelo
valida que `noticias.json` sea JSON bien formado, no que el cambio sea
correcto. Como el título/cuerpo de un PR lo controla quien lo abre, esto
es una puerta de fusión sin revisión para cualquiera que pueda abrir un
PR contra este repositorio con esas palabras -- y ya se usó (sin
mala intención) para fusionar en ~1-3 minutos los dos parches incompletos
del hallazgo 1 arriba, sin pasar por el check "validar" de este flujo de
trabajo. No se modifica ni se deshabilita en esta sesión (cambiar
workflows de CI/CD no es parte del alcance de una auditoría de datos, y es
una decisión que le corresponde al usuario) -- queda documentado aquí y
notificado explícitamente por su severidad.

---

## Auditoría a pedido del usuario (31-07-2026, ~21:00 UTC): 4 alertas de incendio repetidas y mal ubicadas

El usuario reportó 4 alertas de incendio visibles en el sitio que parecían
duplicadas y/o mal ubicadas: "Incendio en Parroquia La Vega, Municipio
Libertador, Distrito Capital", "Incendio en Nueva Esparta", "Incendio en
Distrito Capital" e "Incendio en Municipio Mariño, Nueva Esparta".

### Diagnóstico: eran en realidad 2 incendios reales, cada uno duplicado

1. **Incendio del CCCT** (30 y 31-07): el mismo incendio en el Centro
   Ciudad Comercial Tamanaco, reportado primero el 30-07 (3 fuentes: La
   Verdad, La Prensa de Monagas, Noticias de Aqui) y de nuevo el 31-07 (1
   fuente adicional, Reporte Confidencial) -- dos alertas separadas para
   el mismo hecho.
2. **Incendio del C.C. Los Cedros, Porlamar** (30 y 31-07): el mismo
   incendio en Nueva Esparta, reportado primero el 30-07 (2 fuentes) y de
   nuevo el 31-07 con un artículo de seguimiento del mismo medio (El
   Periodico de Monagas) más una tercera fuente -- misma duplicación.

### Causa raíz 1: `incendio` estaba excluido por completo de la ventana de 36h que reconoce "el mismo evento" entre corridas distintas

`state.TIPOS_SIN_VENTANA_MISMO_EVENTO` incluía `incendio` desde el
30-07-2026 (ver hallazgo anterior en este mismo documento), para evitar
que dos incendios genuinamente distintos en un estado populoso se
fusionaran por error (el caso real de la explosión de gas vs. el CCCT).
Pero excluirlo por completo generó el problema opuesto: un artículo de
seguimiento sobre el MISMO incendio, publicado horas o un día después,
nunca se reconocía como el mismo evento y generaba una alerta duplicada.

**Corrección** (`scripts/state.py`): `incendio` vuelve a tener ventana de
36h, pero ahora exige además que el municipio coincida en ambos lados
(`TIPOS_CON_VENTANA_EXIGE_MISMO_MUNICIPIO`) -- si cualquiera de los dos
eventos no tiene municipio detectado, no se reutiliza la clave. Esto
evita el falso positivo original (la explosión de gas tenía municipio
Libertador; el CCCT, antes del fix de causa raíz 2 abajo, no tenía
municipio detectado) sin reintroducir las alertas duplicadas, ya que dos
reportes del mismo incendio casi siempre nombran, entre ambos, el mismo
municipio. `marcar_publicados()` ahora guarda `municipio` en
`data/publicados.json` para esta comparación.

### Causa raíz 2: el CCCT (municipio Chacao) se clasificaba como Distrito Capital

El CCCT está en el municipio **Chacao**, que pertenece al estado
**Miranda** -- Distrito Capital solo tiene un municipio (Libertador). El
problema es que la prensa venezolana casi siempre describe la zona como
"en Caracas" (uso coloquial del área metropolitana, que incluye
municipios de Miranda como Chacao/Baruta/El Hatillo), y "caracas" es
alias de Distrito Capital en `config/estados.yaml` -- el artículo
terminaba clasificado como Distrito Capital pese a nombrar "municipio
Chacao" explícitamente.

**Corrección** (`scripts/classify.py`): se agrega Chacao/Baruta/El
Hatillo a `LISTA_NEGRA_POR_ESTADO["Distrito Capital"]` -- pero a
diferencia de otras entradas de esa lista (que solo descartan el match),
aquí se **redirige** la detección al estado real
(`_REMAPEO_MUNICIPIO_A_ESTADO`), reutilizando la misma ventana de
proximidad ya encontrada para "Caracas" (que ya contenía la evidencia de
tipo cercana -- el problema nunca fue esa ventana, solo la etiqueta de
estado resultante). No se agregaron como alias directos de Miranda en
`estados.yaml` porque casi siempre aparecen como "municipio Chacao", y
`_es_mencion_subestatal()` ya excluye por diseño cualquier mención
"municipio X"/"parroquia X" como evidencia de estado (para no confundir
"municipio Sucre" con el estado Sucre) -- lo que también habría
bloqueado a Chacao como evidencia directa de Miranda.

**Limitación conocida, no resuelta**: el remapeo solo aplica a la fuente
que efectivamente nombra Chacao/Baruta/El Hatillo. Si dentro de una misma
corrida varias fuentes del mismo incendio se clasifican por separado y
solo alguna de ellas nombra el municipio de Miranda, es posible que el
evento se fragmente entre dos estados dentro de esa corrida (mitigado en
la práctica porque `verify.agrupar_y_verificar` ya agrupa por
tipo+ubicación tomando el municipio del miembro más reciente que lo
tenga). Se marcaron 3 fuentes reales como excepción conocida (`xfail`) en
`tests/test_classify_regresion_historico.py` -- ninguna nombra Chacao por
sí sola, pero el evento fusionado sí es correcto porque otra fuente del
mismo cluster lo nombra.

### Causa raíz 3 (la más seria, encontrada al investigar "La Vega"): el municipio/parroquia que classify.py fija a nivel de CLUSTER no se revalidaba contra las fuentes que la IA realmente aprueba

La alerta "Incendio en Parroquia La Vega, Municipio Libertador, Distrito
Capital" (31-07) tenía una sola fuente publicada (Reporte Confidencial,
artículo sobre el CCCT) cuyo texto **nunca menciona La Vega ni
Libertador** -- solo dice "en el este de Caracas". "La Vega" es una
parroquia real de Libertador (pasó la validación de "¿es un nombre válido
de la jerarquía del INE?"), pero no tiene ninguna relación con este
artículo.

**Causa raíz real**: `verify.agrupar_y_verificar()` fija
`evento["municipio"]`/`["parroquia"]` a partir de **todos** los miembros
crudos agrupados en el cluster (el más reciente con un valor no nulo),
**antes** de que `verify_ai.py` decida qué fuentes se aprueban. Si el
cluster tenía, además de la fuente del CCCT, otra fuente sobre un hecho
distinto que sí nombraba "Parroquia La Vega, Municipio Libertador" y la
IA la rechazó (por no ser el mismo hecho), esa ubicación quedaba "pegada"
al evento final de todos modos -- exactamente el mismo patrón que ya se
había corregido para el municipio/parroquia que *propone la IA*
(`verify_ai.py`, caso real de Zulia/Sinamaica-Guajira, ver entrada
anterior de este documento), pero ese fix nunca cubrió el municipio que
**classify.py ya había fijado** antes de llamarla.

**Corrección** (`scripts/verify_ai.py`, `_finalizar_evento`): se agrega
el mismo chequeo de anclaje textual (¿el municipio/parroquia aparece
literalmente en el texto de las fuentes **aprobadas**?) también para el
municipio/parroquia que llega ya fijado por `classify.py`, no solo para
el que propone la IA. Si no aparece, se descarta a `None` en vez de
publicarse.

### Pruebas

- `tests/test_verify_ai_filtros.py`: 2 pruebas nuevas de `_finalizar_evento`
  (el municipio se descarta si ninguna fuente aprobada lo nombra; se
  conserva si sí).
- `tests/casos_clasificacion.jsonl`: 4 casos nuevos (CCCT real → Miranda,
  control de Distrito Capital genuino sin Chacao, control de Baruta,
  Porlamar como alias de Mariño en un artículo de seguimiento real).
- `config/ubicaciones_detalle.json`: se agrega `"alias": "Porlamar"` al
  municipio Mariño (Nueva Esparta) -- la prensa casi nunca dice "municipio
  Mariño" explícitamente, siempre "Porlamar" (su capital).
- Regresión completa de `clasificar_item()` contra las fuentes de
  `data/historico_fuentes_texto.jsonl`: sin cambios fuera de lo esperado.
  `python3 scripts/validar_configs.py` → OK. 115 pruebas pasan (4 xfail
  conocidos, documentados arriba).

### Corrección retroactiva

Se fusionaron los 2 pares de alertas duplicadas en `docs/data/noticias.json`,
`data/historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl` y
`data/publicados.json`: `incendio::Distrito Capital::2026-07-30` +
`incendio::Distrito Capital::2026-07-31` → `incendio::Miranda::2026-07-30`
(municipio Chacao, 4 fuentes, severidad alto, confirmado); e
`incendio::Nueva Esparta::2026-07-30` + `incendio::Nueva Esparta::2026-07-31`
→ una sola entrada bajo la clave del 30-07 (municipio Mariño, 3 fuentes
únicas, sin_clasificar, confirmado). El score y la confirmación se
recalcularon con la misma fórmula de `verify_ai._peso_efectivo()`
(incluye el bono de fuente regional). Título y texto se regeneraron con
`render.redactar_noticia()`. Los informes narrativos de julio
(`2026-07_incendio.json`, `2026-07_general.json`) no necesitaron
corrección: ambos se generaron a las 10:04 UTC del 31-07, antes de que
existieran las alertas duplicadas -- se regenerarán solos en la próxima
corrida de producción (máximo 1 vez al día). Estadísticas regeneradas con
`python3 scripts/build_dashboard.py`.

### Respuestas a las preguntas del usuario sobre el proceso

**¿Por qué no los vio la auditoría diaria de las 7:00 p.m.?** Esa
auditoría (la que corrió esta misma sesión más temprano hoy, ver PR #118
arriba) reviso alertas hasta su propia hora de corte; las 4 alertas de
incendio se publicaron/duplicaron horas **después** de esa corrida (el
segundo incendio del CCCT se detectó a las 00:15 UTC del 01-08, y el
mecanismo de dedup de `incendio` recién se corrigió en esta sesión). No
es que la auditoría las pasara por alto: no existían todavía cuando
corrió.

**¿El sistema monitorea/publica cada 10 minutos?** Sí -- confirmado en
`scripts/verify_ai.py` (comentario de `MAX_CICLOS_ESPERA_GROQ`: "El
monitoreo corre cada 10 minutos"). Cada corrida agrupa, verifica con IA y
publica de forma automática sin intervención humana.

**¿Se puede hacer la auditoría diaria más efectiva?** El hallazgo de hoy
sugiere una mejora concreta: la auditoría diaria (prompt de la tarea
programada) revisa alertas por rango de fecha de detección, pero no tiene
un paso explícito que busque duplicados **entre alertas ya publicadas de
tipo incendio/inundación/deslizamiento con el mismo municipio** (no solo
mismo estado+tipo+día, que es lo que ya cubre `state.py`). Sería valioso
agregar ese chequeo explícito al prompt de la auditoría diaria: comparar
`fuentes[].link`/nombres de centros comerciales o vías mencionadas entre
alertas del mismo tipo dentro de una ventana de 72h, no solo confiar en
que `state.py` las haya fusionado correctamente en el momento de publicar.
Queda como sugerencia para el usuario, no implementada en este PR (cambiar
el prompt de la tarea programada está fuera del alcance de un cambio de
código).

---

## A pedido del usuario (01-08-2026): auditoría de duplicados como chequeo de CI + informes narrativos con fuentes retractadas

Dos pedidos sobre el hallazgo anterior (incendios duplicados del CCCT/Los
Cedros): (1) implementar la mejora sugerida para que la auditoría diaria
sea más efectiva, y (2) investigar el reporte de que "los informes
narrativos por período documentan hechos que no están reseñados en las
alertas, o que anteriormente eran alertas y fueron eliminadas por ser
bugs".

### 1. `scripts/detectar_inconsistencias.py`: chequeo determinista (sin IA), corre en cada push/PR

En vez de depender de que una futura sesión de auditoría "se acuerde" de
comparar enlaces entre alertas del mismo tipo (la sugerencia original), se
implementó como código: un script que detecta dos clases de problema y se
agregó como paso informativo (no bloqueante) a `.github/workflows/validar.yml`
-- corre en cada push/PR, **incluidas las PRs automáticas de "Actualizar
reportes"**, sin depender de que ninguna sesión humana o de IA se acuerde
de ejecutarlo a mano.

1. **Posibles alertas duplicadas ya publicadas**: mismo tipo, dentro de
   72h, que comparten municipio o una palabra distintiva del link de
   alguna fuente (nombre de centro comercial, vía...). La lista de
   palabras "ruido" a ignorar se construye automáticamente a partir de
   `config/keywords.yaml` (tipos + severidad, son genéricas del dominio
   por definición) más una lista manual de verbos/conectores/sustantivos
   frecuentes en titulares de prensa. Probado contra los 2 casos reales
   del incendio del CCCT/Los Cedros (uno se detecta por token de link
   compartido -- "ccct" --, el otro solo por municipio compartido, ya que
   sus links no comparten ninguna palabra) y contra 4 casos de control
   (eventos genuinamente distintos, fuera de ventana, de tipo distinto, o
   reportes de filial cuyo link es una búsqueda de Gmail) para no generar
   ruido.
2. **Informes narrativos con fuentes "muertas"**: un link citado en
   `docs/data/informes/*.json` que ya no existe en
   `data/historico_fuentes_texto.jsonl` -- señal de que el evento se
   retractó (bug corregido) o se fusionó con otro después de generarse el
   informe, y este nunca se regeneró (requiere Groq, no siempre
   disponible -- ver hallazgo 2 abajo).

No corrige nada automáticamente -- solo imprime un reporte para revisión
humana, porque los falsos positivos son posibles (dos eventos genuinamente
distintos pueden compartir una palabra común). Pruebas en
`tests/test_detectar_inconsistencias.py` (7 casos).

### 2. 6 informes narrativos de julio citaban fuentes ya retractadas como bugs

Al correr el nuevo detector contra los informes actuales, aparecieron 14
fuentes muertas en 6 informes distintos. La causa raíz es de **proceso**,
no de lógica: `build_informes.py` regenera un informe del período en curso
como máximo 1 vez por día calendario (UTC) -- si en el medio de ese día se
retracta un evento (como ya pasó varias veces: nota de protesta
diplomática, corrección retrospectiva de epicentro sísmico, operativo
antidrogas, homicidio a machetazos...), el informe queda citando esa
fuente hasta la siguiente regeneración exitosa. Este entorno no tiene
`GROQ_API_KEY` disponible, así que no se pudo regenerar la narrativa con
IA -- se corrigió a mano:

- **`2026-07_sismo.json`**: su única fuente era la corrección
  retrospectiva de epicentro (evento retractado el 29-07, ver esa fecha en
  este documento) -- **no queda ningún evento sísmico real en julio**, así
  que se eliminó el archivo completo y su entrada de `index.json` (una
  regeneración real desde `historico_fuentes_texto.jsonl`, que ya no tiene
  ninguna fuente de tipo sismo para julio, tampoco lo generaría).
- **`2026-07_orden_publico.json`**: de 8 eventos narrados, 4 citaban
  fuentes retractadas (protesta de jubilados de Cantv, demolición de la
  torre C en La Guaira, nota de protesta a Irán, un hombre detenido por
  arrollar a su pareja -- este último es el mismo patrón de "enfrentamiento"
  ya documentado: un delito individual, no un disturbio civil). Se
  reescribió la narrativa con los 3 eventos reales que sí sobreviven en el
  histórico (Maturín, tranca en el sur de Bolívar, marcha en Caracas) --
  `total_eventos` corregido de 8 a 3.
- **`2026-07_general.json`**, **`2026-07_incendio.json`**,
  **`2026-07_infraestructura_electrica.json`**, **`2026-07_salud_publica.json`**:
  se quitaron las fuentes muertas de la lista de citas y se ajustó
  `total_eventos`/`comparacion_mes_anterior` con la misma función de
  conteo que usa `build_informes.py`
  (`_conteos_por_periodo_y_tipo(leer_historico())`). Para
  `2026-07_incendio.json` y `2026-07_infraestructura_electrica.json` se
  editó además la narrativa (frases/citas que mencionaban directamente el
  hecho retractado); `2026-07_general.json` no necesitó tocar la narrativa
  -- ninguna de sus 5 fuentes muertas se mencionaba en el texto, solo en
  la lista de citas.

**Limitación reconocida**: esta corrección es manual y puntual, no
resuelve la causa raíz de fondo (que la regeneración automática dependa de
que Groq esté disponible exactamente el día en que cambia el calendario
UTC). Si el usuario nota informes desactualizados en el futuro, el nuevo
`scripts/detectar_inconsistencias.py` (corriendo en cada PR desde ahora)
debería señalarlo mucho antes de que se acumulen 14 referencias muertas
otra vez.

### Pruebas

`python3 -m pytest tests/` → 122 passed, 4 xfailed (conocidos, sin
relación). `python3 scripts/validar_configs.py` → OK. `python3
scripts/detectar_inconsistencias.py` → "Sin inconsistencias detectadas."
tras las correcciones de este hallazgo.

---

## Decisión del usuario (01-08-2026): eliminar el workflow de auto-merge y agregar ventana de tiempo a reportes de filial

Respuesta a los 2 hallazgos pendientes documentados en la entrada anterior.

### A. `.github/workflows/auto-cleanup.yml` eliminado

El usuario preguntó si era posible mantener el sistema automatizado sin
depender de que él tuviera que intervenir manualmente varias veces al
día. La respuesta es que **ya lo está**, por dos caminos que no dependen
de `auto-cleanup.yml`:

1. **`monitor.yml`** (corrida cada 10 minutos) ya publica y fusiona sus
   propias PRs de "Actualizar reportes" de forma segura con `gh pr merge
   --auto` -- esto solo completa la fusión cuando el check "validar" (la
   suite de pruebas real) pasa, respetando el ruleset de `main`. Nunca
   usó `auto-cleanup.yml`.
2. **Las sesiones de Claude Code** (la auditoría diaria de las 7pm, y
   sesiones interactivas como esta) ya abren PR, esperan activamente a
   que "validar" pase, y fusionan -- sin que el usuario tenga que hacer
   clic en nada.

`auto-cleanup.yml` no agregaba automatización real: duplicaba lo que ya
hacían los dos mecanismos de arriba, pero de forma insegura (auto-aprobación
por coincidencia de texto en el título del PR, usando una GitHub Action de
terceros, sin exigir que el check de pruebas pasara primero). Ya se había
usado, sin mala intención, para fusionar en 1-3 minutos dos parches
incompletos del bug de "enfrentamiento" (ver esa entrada). Se elimina el
archivo por completo -- la automatización que el usuario pidió se
mantiene intacta.

### B. Reportes de filial: cada correo es independiente, se agrega ventana de tiempo

El usuario confirmó cómo funciona el reporte de las filiales en la
práctica: "cada correo se toma como independiente sin considerar si en
el pasado se informó sobre lo mismo y sin considerar si es o no una
actualización". Esto confirma que el sistema no puede asumir que dos
correos sobre el mismo municipio, sin importar cuánto tiempo los separe,
describen la misma situación -- necesita su propio criterio.

**Corrección** (`scripts/verify.py`): se agrega
`_separar_reportes_filial_por_ventana()`, análoga a
`_separar_sismos_por_magnitud()` ya existente -- dentro de un cluster
(mismo tipo+ubicación, misma corrida), los reportes de filial se separan
en sub-eventos si el hueco entre reportes consecutivos (ordenados por
fecha) supera `VENTANA_HORAS_MISMO_EVENTO_FILIAL` (36h, misma duración ya
usada en `state.VENTANA_HORAS_MISMO_EVENTO` para no inventar un criterio
nuevo sin motivo). Los miembros que no son reporte de filial (un artículo
de prensa sobre el mismo tipo+ubicación, caso raro) se unen al sub-grupo
más reciente.

**Efecto secundario esperado, y por qué es correcto**: dos pruebas ya
existentes (`test_municipio_y_parroquia_no_se_mezclan_entre_fuentes_distintas`,
`test_parroquia_se_conserva_si_coincide_con_el_municipio_elegido`) usaban
fechas separadas por 21 días asumiendo que debían fusionarse en un solo
evento -- se ajustaron las fechas de esos casos sintéticos a dentro de la
ventana (sin cambiar lo que realmente prueban: que municipio/parroquia no
se mezclen entre fuentes de un mismo cluster), y se agregaron 2 pruebas
nuevas para la ventana en sí (un caso real que ahora se separa en 2
eventos, un control de que reportes cercanos en el tiempo se siguen
fusionando).

### Hallazgo adicional al reconstruir el caso real: un mismo link de correo con contenido distinto

Al revisar el texto completo de las 3 fuentes de
`crisis_migratoria::Falcon::2026-07-07` para la corrección retroactiva, se
encontró que **2 de las 3 fuentes comparten el mismo link** (mismo
Message-ID de Gmail) pero tienen contenido completamente distinto:

- 28/07/2026: "municipio Colina... 17 familias, 46 personas..."
- 07/07/2026: "parroquia Las Calderas, municipio Colina... 3 familias, 11
  personas..." -- **mismo link que la fuente del 28/07**, pero cifras y
  fecha distintas.
- 29/07/2026: "municipio Zamora... 22 familias, 42 personas..."

No se investigó la causa raíz de esta colisión de Message-ID en esta
sesión (requeriría acceso a la bandeja de Gmail para diagnosticar
`fetch_gmail.py`, no disponible aquí) -- queda anotado como hallazgo
pendiente para una futura auditoría. Para la corrección retroactiva de
abajo se trataron como 2 fuentes distintas (por su contenido, no por su
link), ya que claramente describen hechos/fechas diferentes.

### Corrección retroactiva

`crisis_migratoria::Falcon::2026-07-07` (3 fuentes, "Municipio Zamora") se
dividió en 2 alertas en `docs/data/noticias.json`,
`data/historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl` y
`data/publicados.json`:

- `crisis_migratoria::Falcon::2026-07-07`: solo la fuente del 07/07 --
  "Parroquia Las Calderas, Municipio Colina" (11 personas, 3 familias).
- `crisis_migratoria::Falcon::2026-07-28`: fuentes del 28/07 y 29/07 (24h
  de diferencia, dentro de la ventana) -- "Municipio Zamora" (mismo
  resumen consolidado ya publicado, que ya usaba la fuente más reciente).

Título y texto regenerados con `render.redactar_noticia()`. Estadísticas
regeneradas. `python3 scripts/detectar_inconsistencias.py` → sin
inconsistencias tras la corrección.

### Pruebas

`python3 -m pytest tests/` → 124 passed, 4 xfailed (conocidos, sin
relación). `python3 scripts/validar_configs.py` → OK.

---

## A pedido del usuario (01-08-2026): "Ataque armado en Tachira" ocurrió en Colombia, no en Venezuela

El usuario preguntó si la alerta "Ataque armado en Tachira" sería
detectada como falsa por la auditoría de las 7pm, o si el sistema no la
iba a detectar. Se investigó de inmediato en vez de esperar.

### El hecho ocurrió en Colombia

La fuente (El Pitazo) dice explícitamente: *"Frontera con Colombia | 11
heridos por la explosión de un carro bomba contra la policía de Santander
Táchira.- Por tercer día consecutivo se registran atentados con
explosivos en el **Norte de Santander, Colombia**. La madrugada de este 1
de agosto un carro bomba explotó en la sede de la Policía de **Norte de
Santander**."* -- "Táchira" solo aparecía como el dateline del medio (El
Pitazo reporta desde la frontera venezolana sobre un hecho ocurrido del
otro lado), no como la ubicación del ataque. Norte de Santander es un
departamento de Colombia, no un lugar de Venezuela.

**No existía ningún filtro para esta clase de bug** -- ni
`classify.py` (que solo mira si el nombre del estado aparece cerca de
evidencia de tipo, sin verificar en qué país ocurrió el hecho) ni la
verificación de IA (`estado_verificacion: APROBADO_IA` -- Groq la aprobó
igual). Sin este chequeo, la respuesta honesta a la pregunta del usuario
era "no, el sistema no la iba a detectar por su cuenta" -- se corrigió de
inmediato en vez de dejarlo como una apuesta para la auditoría de la
noche.

**Corrección** (`scripts/classify.py`): se agrega "norte de santander" a
`LISTA_NEGRA_POR_ESTADO["Tachira"]`. A diferencia de
Chacao/Baruta/El Hatillo (que sí son lugares reales de Venezuela, solo
del estado equivocado, y por eso se remapean), Norte de Santander no es
un lugar de Venezuela -- no hay a dónde remapear, se descarta sin más (el
sistema solo monitorea emergencias en Venezuela).

**Limitación reconocida**: este fix cubre el caso confirmado (Táchira /
Norte de Santander). El mismo patrón -- un medio venezolano fronterizo
reportando "desde" un estado venezolano sobre un hecho ocurrido en el
departamento colombiano vecino -- podría repetirse para Zulia (La
Guajira/Cesar, Colombia), Apure (Arauca, Colombia) o Amazonas (Vichada,
Colombia). No se agregaron esos casos hoy por no tener un ejemplo real
que confirme el patrón exacto de redacción (y "Guajira" en particular es
ambiguo: también es un municipio real de Zulia, Venezuela) -- queda
anotado para que una futura auditoría los tenga en cuenta si aparece un
caso similar.

### Pruebas

Caso real (ya no genera alerta) y un caso de control (un ataque armado
genuino en Táchira que de paso menciona la cercanía con la frontera
colombiana sigue generando alerta -- el filtro no debe descartar eventos
venezolanos reales solo por mencionar a Colombia como referencia
geográfica) en `tests/casos_clasificacion.jsonl`.

### Corrección retroactiva

Se eliminó `ataque_armado::Tachira::2026-08-01` de
`docs/data/noticias.json`, `data/historico_eventos.jsonl`,
`data/historico_fuentes_texto.jsonl` y `data/publicados.json`. El informe
narrativo `docs/data/informes/2026-08_ataque_armado.json` -- generado el
mismo día, con esta como su única fuente -- se eliminó por completo (no
queda ningún ataque armado real en agosto), igual que se hizo antes con
`2026-07_sismo.json`; también se quitó su entrada de `index.json`. El
nuevo `scripts/detectar_inconsistencias.py` (agregado ayer a CI) detectó
esta fuente muerta automáticamente en cuanto se corrigió el dato --
funcionando exactamente como se esperaba.

`python3 -m pytest tests/` → 129 passed, 4 xfailed (conocidos, sin
relación). `python3 scripts/validar_configs.py` → OK. `python3
scripts/detectar_inconsistencias.py` → sin inconsistencias.

---

## A pedido del usuario (01-08-2026): generalizar el fix de Táchira/Colombia a todos los estados fronterizos, con una condición de seguridad clave

Sobre el hallazgo anterior ("Ataque armado en Tachira" ocurrido en
realidad en Colombia): el usuario pidió generalizar el fix a Zulia, Apure
y Amazonas (limitado a la frontera con Colombia, no Brasil por ahora), y
antes de implementar propuso 2 casos reales para evaluar el diseño:
combates entre el ELN y la Segunda Marquetalia "en los estados
venezolanos Apure y Amazonas" (Infobae, 07-08-2025), y un ataque de las
FARC contra un puesto militar venezolano en "municipio Páez de Apure"
(SwissInfo, 29-03-2021).

### El diseño ingenuo (solo lista de lugares colombianos) habría sido un error grave

Se leyeron ambos artículos completos antes de escribir código. Los dos
son eventos **reales, graves y ocurridos en territorio venezolano**
(combate armado y toma de territorio por guerrilla colombiana en Apure/
Amazonas; ataque contra un puesto militar venezolano) -- pero ambos
mencionan extensamente a Colombia y a grupos armados colombianos (ELN,
FARC, Segunda Marquetalia), porque esa es la naturaleza real del
fenómeno: grupos armados colombianos operan y combaten **dentro** de
territorio venezolano fronterizo. Un filtro que descartara la ubicación
venezolana solo por la presencia de "Colombia"/nombres de lugares
colombianos habría descartado exactamente el tipo de alerta grave que el
sistema más necesita capturar -- el efecto contrario al buscado.

### Corrección con salvaguarda: solo descarta si NO hay municipio venezolano detectado

`scripts/classify.py`: nuevo mecanismo `FRONTERA_EXTRANJERA_POR_ESTADO` +
`_es_evento_extranjero_sin_municipio()`, separado de `LISTA_NEGRA_POR_ESTADO`
(la entrada puntual de Táchira/Norte de Santander se migró aquí). Un
estado fronterizo con un lugar colombiano conocido en el texto **solo se
descarta si además no se detectó ningún municipio/parroquia venezolano
específico** de ese estado -- si el artículo nombra "municipio Páez" o
"municipio Rómulo Gallegos", la mención de Colombia se trata como
contexto (el fenómeno real de grupos armados colombianos operando en
Venezuela), no como evidencia de que el hecho ocurrió del otro lado.

**Gazetteer agregado** (Colombia solamente, por ahora):
- Táchira: "norte de santander", "cucuta" (se agrega "Cúcuta" sola, el
  caso original solo cubría el departamento).
- Zulia: "riohacha", "valledupar", "la guajira, colombia"/"departamento
  de la guajira", "cesar, colombia"/"departamento del cesar".
- Apure: "arauca, colombia"/"departamento de arauca", "arauquita",
  "saravena", "puerto carreño".
- Amazonas: "vichada", "inirida", "puerto carreño", "guainia,
  colombia"/"departamento de guainia".

**Verificación de colisiones con lugares reales de Venezuela** (a mano
contra `config/ubicaciones_detalle.json`, antes de escribir cualquier
frase): "guainia" es substring de "Guainiamo" (parroquia real de Cedeño,
Bolívar) y "cesar" es substring de "Julio Cesar Sala" (municipio real de
Mérida) -- por eso ninguna de esas dos palabras se usa suelta, solo en
frases específicas ("guainia, colombia", "cesar, colombia") que no
coinciden por accidente con esos lugares venezolanos.

### Limitación reconocida y aceptada explícitamente por el usuario: Zulia/La Guajira

Zulia es el caso más delicado: "Guajira" es *también* un municipio real
de Zulia ("Indígena Bolivariano Guajira", ver PR #61). El usuario aceptó
el trade-off de ser menos agresivo ahí -- **pero se descubrió durante las
pruebas que el problema es más profundo de lo previsto**: cuando el texto
menciona "La Guajira, Colombia", el detector de municipio (que ya usa
"Guajira" como alias del municipio venezolano) lo interpreta como
evidencia del municipio venezolano, lo cual además **desactiva la
salvaguarda** ("si hay municipio, no se descarta") -- es decir, un
artículo sobre un hecho real en Riohacha/La Guajira, Colombia, podría
sobrevivir como alerta de Zulia con municipio "Guajira" atribuido por
error. Probado y confirmado: sin la palabra "Guajira" en el texto (ej.
solo "Riohacha"), el descarte funciona correctamente. Esto no es una
regresión introducida hoy -- es la misma ambigüedad de nombre ya conocida
desde antes, ahora también afecta a este mecanismo nuevo. Queda
documentado, no resuelto (arreglarlo a ciegas sin un caso real de este
patrón específico arriesga más de lo que soluciona).

### Pruebas

6 casos nuevos en `tests/casos_clasificacion.jsonl`: Cúcuta sola (se
descarta), los 2 casos reales de Apure/Amazonas y del ataque a militares
venezolanos (ambos se MANTIENEN pese a mencionar Colombia extensamente),
Riohacha/Zulia (se descarta), y 2 controles de que los municipios
venezolanos reales con nombres ambiguos (Guajira de Zulia, Julio César
Sala de Mérida) siguen detectándose con normalidad.

Regresión completa contra `data/historico_fuentes_texto.jsonl`: ningún
evento ya publicado se vio afectado (no hizo falta corrección
retroactiva esta vez). `python3 -m pytest tests/` → 135 passed, 4 xfailed
(conocidos, sin relación). `python3 scripts/validar_configs.py` → OK.
`python3 scripts/detectar_inconsistencias.py` → sin inconsistencias.

---

## A pedido del usuario (01-08-2026): confirmación real de la limitación de Zulia/Guajira, corregida

El usuario proporcionó 3 artículos reales sobre ataques de las FARC en La
Guajira, Colombia, para poner a prueba el mecanismo recién generalizado.
Dos de los tres describen, de forma consistente, ataques armados
ocurridos en el departamento de La Guajira, Colombia (uno menciona
además que la guerrilla usa la frontera con Venezuela -- Zulia y Apure --
como zona de repliegue).

### Se confirmó, con un caso concreto, la limitación ya documentada

Un texto basado en ese patrón real (ataque armado en "La Guajira,
Colombia", con mención explícita de los estados venezolanos Zulia y
Apure como contexto) sí generaba una alerta falsa: `Zulia`, con
municipio **"Indígena Bolivariano Guajira"** -- exactamente la
combinación que se había anticipado como riesgo al generalizar el fix a
Zulia.

**Causa raíz exacta**: `detectar_municipio_parroquia()` ya usa "Guajira"
como alias directo del municipio venezolano "Indígena Bolivariano
Guajira" (desde PR #61). Cuando el texto dice "La Guajira, Colombia", esa
MISMA palabra activa dos señales contradictorias: la evidencia de que el
hecho es colombiano (`FRONTERA_EXTRANJERA_POR_ESTADO`) y, por accidente,
la "evidencia" de que hay un municipio venezolano específico -- lo que
anulaba la salvaguarda pensada para proteger eventos reales como los de
Apure/Amazonas.

### Corrección

`scripts/classify.py`: nuevo `_MUNICIPIO_NO_CUENTA_COMO_SALVAGUARDA`
-- una lista de municipios que, aunque se detecten, NO cuentan como
evidencia venezolana confiable cuando el estado también tiene evidencia
de `FRONTERA_EXTRANJERA_POR_ESTADO`, porque la misma palabra que los activa
es la que prueba lo contrario. Por ahora solo contiene
`Zulia: {"Indígena Bolivariano Guajira"}`. El caso de control (el mismo
municipio venezolano real, sin ninguna mención de Colombia) se sigue
detectando con normalidad -- la salvaguarda solo se anula cuando además
hay evidencia de que el hecho es colombiano.

### Pruebas

2 casos nuevos en `tests/casos_clasificacion.jsonl` (basados en el patrón
real reportado por el usuario, sin reproducir texto de los artículos): el
caso que ahora se descarta correctamente, y el control de que el
municipio venezolano real sigue funcionando. Regresión completa contra
`data/historico_fuentes_texto.jsonl`: sin corrección retroactiva
necesaria. `python3 -m pytest tests/` → 137 passed, 4 xfailed (conocidos,
sin relación). `python3 scripts/validar_configs.py` → OK. `python3
scripts/detectar_inconsistencias.py` → sin inconsistencias.

---

## Auditoría diaria automática (02-08-2026): 4 hallazgos corregidos de raíz y 2 pendientes de discutir

Auditoría de rutina de las ~14 alertas publicadas entre el 01-08 y el
02-08-2026, comparando cada una contra el texto real de su(s) fuente(s).
Se encontraron y corrigieron 4 errores reales; se dejan documentados 2
patrones ambiguos sin corregir (ver sección final).

### 1. "Las Mercedes" (incendio) se publicaba como Distrito Capital -- el municipio real (Baruta) nunca llegaba al clasificador

El resumen RSS de la fuente ("Un incendio en un edificio de Las Mercedes
deja dos personas lesionadas. Efectivos de los Bomberos de Caracas
sofocaron las llamas...") es una oración **completa**, sin puntos
suspensivos -- `_TRUNCADO_RE` nunca se disparó, así que `fetch_rss.py`
nunca bajó el texto completo de la página. El cuerpo completo del
artículo sí dice "en el municipio Baruta" (confirmado descargando la
página real), pero esa palabra nunca llegó al texto que ve
`classify.py`. Sin "Baruta"/"Chacao"/"El Hatillo" en el texto, el único
alias detectado es "Caracas" (via "Bomberos de Caracas") → Distrito
Capital.

**Causa raíz 1** (`scripts/fetch_rss.py`): el disparador de descarga del
texto completo solo cubre resúmenes truncados. Un resumen sin truncar
puede seguir siendo, en la práctica, solo la meta-descripción SEO del
artículo (típicamente ~150 caracteres) y omitir igual el municipio real.

**Corrección 1**: se agregó un segundo disparador -- si el texto
menciona "Caracas" y **ninguno** de los municipios reales conocidos de
Miranda que a veces se confunden con Distrito Capital (Libertador,
Chacao, Baruta, El Hatillo), también se descarga el texto completo de la
página, igual que para el caso truncado (fallback silencioso si la
descarga falla, mismo patrón ya usado).

**Causa raíz 2** (`scripts/classify.py`): con el texto completo real, la
ubicación sí se corregía a Miranda/Baruta (el mecanismo de
`LISTA_NEGRA_POR_ESTADO`/`_REMAPEO_MUNICIPIO_A_ESTADO` ya existente desde
el 31-07 funcionó), pero la **severidad se perdía** ("sin_clasificar" en
vez de "alto"): la ventana de proximidad para el remapeo se calculaba
alrededor de la (única) mención de "Caracas" en el artículo -- que
aparece varias frases después, solo como "Bomberos de Caracas" -- dejando
"lesionados" (que está justo antes de "municipio Baruta", pero a más de
35 palabras de "Caracas") fuera de la ventana.

**Corrección 2**: `_detectar_ubicacion_texto_plano()` ahora intenta
anclar la ventana primero en la frase de la lista negra misma (p.ej.
"Baruta", con un nuevo parámetro `permitir_subestatal=True` en
`_ventana_cerca()` -- aquí "municipio Baruta" es la evidencia real, no
una ambigüedad a filtrar como en el caso general de "municipio Sucre"),
y solo si eso tampoco encuentra el tipo cerca, cae de vuelta a la
ventana de "Caracas" y finalmente al texto completo (si el tipo aparece
en cualquier otro punto del artículo). Esto es un mecanismo general, no
un parche puntual: cualquier remapeo futuro (Chacao/El Hatillo) se
beneficia igual.

**Corrección retroactiva**: `incendio::Distrito Capital::2026-08-02` →
reclasificado a `incendio::Miranda::2026-08-02` (municipio "Baruta",
severidad "alto", antes "sin_clasificar" en cuanto a ubicación aunque la
severidad ya salía "alto" por casualidad con el resumen corto). Corregido
en `docs/data/noticias.json` (`render.redactar_noticia()` para
regenerar título/texto), `data/historico_eventos.jsonl` y
`data/historico_fuentes_texto.jsonl` (aquí también se reemplazó el
resumen truncado por el texto completo real de la página, descargado
manualmente en esta sesión, para que la regresión automática contra este
archivo quede corrigiendo el caso real en vez de depender de una
excepción `xfail`) y `data/publicados.json`. Se regeneró
`docs/data/estadisticas.json`.

### 2. Golpiza en un partido de fútbol en Barquisimeto (Lara) se publicaba TAMBIÉN como alerta de Carabobo -- por el nombre del equipo visitante

"Salvaje golpiza a un inocente empaña el encuentro entre Portuguesa FC y
**Carabobo FC** en Barquisimeto" generaba dos alertas del mismo artículo:
una correcta (Lara, donde ocurrió el hecho real) y una falsa (Carabobo,
solo porque el equipo visitante se llama "Carabobo FC" y ese nombre
coincide con el alias del estado).

**Corrección**: se agregó `"Carabobo": ["carabobo fc"]` a
`LISTA_NEGRA_POR_ESTADO` (sin entrada en `_REMAPEO_MUNICIPIO_A_ESTADO`:
no hay a qué estado real redirigir, se descarta directamente, mismo
patrón que "aeropuerto"/"moneda" para Bolívar/Sucre).

**Corrección retroactiva**: se eliminó por completo
`orden_publico::Carabobo::2026-08-02` de `docs/data/noticias.json`,
`data/historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl` y
`data/publicados.json`. La alerta de Lara (correcta) no se tocó.

### 3. Muerte por caída de un árbol en Cumaná (Sucre) se publicaba como "Falla eléctrica" crítica

"Tragedia en Cumaná: colapso de un árbol cobró la vida de una mujer...
luego de que un árbol colapsara y arrastrara postes del tendido
eléctrico" generaba `infraestructura_electrica` (crítico, por
"falleció") solo por la frase "tendido eléctrico". El artículo completo
(descargado y leído en esta sesión) es puramente el relato de un
accidente fatal -- un árbol cayó, mató a una persona e hirió a otras
dos -- sin ninguna mención de corte/interrupción real del servicio
eléctrico para la población. No hay ninguna categoría del sistema que
describa bien este hecho (no es un "colapso_estructural" en el sentido
de edificio/puente/vivienda de `keywords.yaml`).

**Corrección**: nuevo filtro de contexto conflictivo para
`infraestructura_electrica` (`_CONTEXTO_CONFLICTIVO_POR_TIPO`): la
palabra suelta "árbol"/"arboles" sin evidencia fuerte de interrupción
real del servicio (`apagón`, `sin luz`, `sin electricidad`, `falla
eléctrica`, `corte de luz`, ...) descarta el tipo. Se usó la palabra
suelta en vez de una frase fija ("colapso de un árbol") porque la
ventana de proximidad puede recortar el texto justo antes de la frase
completa, dejando solo el orden invertido ("un árbol colapsó") -- un
token suelto es robusto a cualquier orden/conjugación.

**Corrección retroactiva**: se eliminó por completo
`infraestructura_electrica::Sucre::2026-08-01` de
`docs/data/noticias.json`, `data/historico_eventos.jsonl`,
`data/historico_fuentes_texto.jsonl` y `data/publicados.json`.

### 4. Concentración explícitamente pacífica en Maturín (Monagas) se publicaba como "Orden público"

"Oposición se concentró en la Av. Juncal de Maturín... Contamos con una
gran participación de ciudadanos que **acudieron de manera pacífica** a
esta concentración. Agradecemos el respaldo y el **comportamiento
cívico** demostrado" generaba `orden_publico` solo por la palabra
"manifestantes" -- pese a que el propio artículo declara explícitamente
que no hubo ningún incidente.

**Causa raíz**: la aclaración de que fue pacífica aparece varios
párrafos después de la mención de "Monagas" -- fuera de la ventana de
proximidad de `_CONTEXTO_CONFLICTIVO_POR_TIPO` (que solo mira el
fragmento cercano a la ubicación). Por eso este filtro **no** se agregó
ahí (donde no habría funcionado), sino como una señal decisiva sobre el
**artículo completo**, igual que ya existe para
`_es_boletin_estadistico_salud_sin_alarma()`.

**Corrección**: nueva función
`_es_manifestacion_pacifica_sin_evidencia_fuerte()` en `classify.py`,
llamada desde `detectar_tipo()` con `texto_completo_norm` (no la
ventana): si el artículo completo declara explícitamente que la actividad
fue pacífica ("de manera pacífica", "pacíficamente", "comportamiento
cívico") y no hay evidencia fuerte real de disturbio en ningún punto del
artículo, se descarta `orden_publico`.

**Corrección retroactiva**: se eliminó por completo
`orden_publico::Monagas::2026-07-28` de `docs/data/noticias.json`,
`data/historico_eventos.jsonl` y `data/historico_fuentes_texto.jsonl`
(no estaba en `data/publicados.json`, ya había salido de la ventana de
retención).

### Informes narrativos: 2 quedan con referencias desactualizadas, no regenerados en esta sesión

`docs/data/informes/2026-08_general.json` y
`2026-08_infraestructura_electrica.json` todavía mencionan la falla
eléctrica de Sucre ya retractada (hallazgo 3); `docs/data/informes/2026-07_general.json`
y `2026-07_orden_publico.json` todavía mencionan la concentración de
Monagas ya retractada (hallazgo 4). Mismo caso que el 31-07-2026: la
narrativa se genera con Groq y `GROQ_API_KEY` no está disponible en este
entorno, así que no se regeneró a mano. `scripts/build_informes.py`
regenera el informe del mes en curso como máximo una vez al día; la
próxima corrida de producción lo hará automáticamente a partir de los
datos ya corregidos. Confirmado con
`scripts/detectar_inconsistencias.py`, que detectó las 4 referencias a
fuentes muertas correctamente (exactamente los 2 eventos retractados, en
sus informes mensual y general correspondientes) sin que se le pidiera
nada -- funcionando como se esperaba.

### Pendiente de discutir: dos alertas más con el mismo patrón "manifestantes"/"protesta" sueltos, pero SIN señal explícita de que fueran pacíficas ni de que hubiera disturbio

Al investigar el hallazgo 4 aparecieron dos casos más, publicados, que
disparan `orden_publico` únicamente por la palabra "manifestantes" (sin
ninguna palabra de evidencia fuerte de disturbio) pero que **tampoco**
declaran explícitamente que fueron pacíficos -- a diferencia del caso de
Monagas, aquí no hay ninguna señal textual en ningún sentido:

- `orden_publico::Distrito Capital::2026-07-28` -- "Oposición marcha en
  Caracas exigiendo elecciones y el regreso de Machado" (marcha política
  convocada por Vente Venezuela).
- `orden_publico::Distrito Capital::2026-08-01` -- "Sindicalistas exigen
  que diálogo entre chavismo y oposición sea público" (concentración en
  La Carlota exigiendo transparencia en el diálogo).

Ninguno de los dos artículos menciona heridos/detenidos/disturbios/
tiroteos, pero tampoco dicen explícitamente "de manera pacífica" como el
caso de Monagas que sí se corrigió. Hay además un tercer caso con la
misma ambigüedad de fondo pero de naturaleza distinta:
`orden_publico::Bolivar::2026-07-30` ("Continúa tranca en sur del estado
Bolívar. Las protestas por el servicio eléctrico continúan...") -- aquí
sí hay evidencia de una interrupción real (una vía bloqueada, "tranca"),
que podría justificar mantenerlo aunque no tenga palabras de la lista de
evidencia fuerte actual.

**No se corrigió nada en estos 3 casos.** Diseñar un filtro general para
"manifestantes"/"protesta(s)" sueltos sin exigir una señal explícita
(como se hizo para el caso pacífico) tiene un trade-off real: podría
dejar de capturar coberturas iniciales de disturbios genuinos que aún no
mencionan una palabra de evidencia fuerte específica. Y limitarlo a
"marchas/concentraciones por una demanda política sin mención de
confrontación" es una distinción semántica difícil de capturar solo con
palabras clave sin arriesgar falsos negativos futuros. Queda documentado
aquí como pendiente de decisión del usuario, no corregido a ciegas.

### Pruebas

7 casos nuevos en `tests/casos_clasificacion.jsonl` (5 basados en texto
real de los artículos afectados + 2 controles sintéticos): remapeo
Las Mercedes/Baruta con severidad completa, "Carabobo FC" descartado
(con control de un evento real en Carabobo sin ese nombre de equipo),
árbol sin evidencia de apagón descartado (con control de un árbol que sí
deja sin luz a la población), manifestación explícitamente pacífica
descartada (con control de que evidencia fuerte real sigue anulando el
descarte). Regresión completa contra `data/historico_fuentes_texto.jsonl`:
las 3 fuentes de los hallazgos 2-4 cambian de resultado como se esperaba
(consistente con su retracción); ningún otro evento ya publicado se vio
afectado. `python3 -m pytest tests/` → 152 passed, 4 xfailed (conocidos,
sin relación), 1 xpassed -- una fuente nueva ("La Prensa de Monagas", el
caso de Las Mercedes corregido) coincide por casualidad con el mismo
nombre de fuente de una limitación conocida y no relacionada del CCCT
(31-07-2026), sin efecto real (`strict=False`, no rompe la suite).
`python3 scripts/validar_configs.py` → OK.

---

## Auditoría diaria automática (05-08-2026): un sismo en Filipinas publicado dos veces como sismo crítico en Venezuela, un rescate retrospectivo publicado como sismo nuevo, y severidad crítica por animales muertos

Auditoría de rutina de las 13 alertas publicadas entre el 03-08 y el
05-08-2026, comparando cada una contra el texto real de sus fuentes. Se
encontraron y corrigieron 3 errores reales (2 de ellos con la misma causa
raíz); se deja documentado 1 caso ambiguo sin corregir.

### 1 y 2. Un terremoto de magnitud 6.3 en Mindanao, Filipinas -- que el propio artículo aclara "sin causar víctimas" -- se publicó DOS VECES como sismo crítico en Venezuela (Apure y Anzoátegui)

La fuente (Notiapure) es enteramente sobre un sismo en Filipinas: "El
Servicio Geológico de Estados Unidos (USGS) registró este miércoles un
terremoto de magnitud 6,3 en la isla de Mindanao, en el sur de
Filipinas (...) El evento telúrico no provocó daños ni víctimas en las
zonas cercanas al epicentro". Sin embargo se publicaron dos alertas de
sismo **crítico** en Venezuela: una en Apure (municipio "Biruaca") y otra
en Anzoátegui, ambas `APROBADO_IA` (pasaron la verificación de la IA).

**Causa raíz**: la página del artículo termina con un bloque de
"artículos relacionados" bajo el encabezado "También Puedes Leer:" (y
precedido por la frase fija "Si quieres conocer otras noticias parecidas
a X puedes visitar la categoría Y"), con títulos de OTRAS notas sin
relación: "Policía De Apure Detiene A Dos Mujeres... En Biruaca",
"...Ocho Sujetos En Anzoátegui", y "Aumenta A 6.125 La Cifra De
Fallecidos Tras Los Sismos Del 24 De Junio En Venezuela" (sobre el sismo
venezolano real de hace más de un mes, no el de Filipinas). El regex
existente para limpiar este tipo de bloque (`_ARTICULOS_RELACIONADOS_RE`
en `scripts/fetch_rss.py`) solo cubría la variante "Lea también:"/"Lee
también:" (orden de palabras "lea/lee tambien"); esta plantilla de
WordPress usa el orden invertido ("también puedes leer"), así que el
bloque completo -- con "Apure", "Anzoátegui", "Biruaca" y "fallecidos"
de notas ajenas -- pasó intacto al clasificador. Esas mismas palabras
("fallecidos") también hicieron que el filtro determinista de
`_sismo_sin_evidencia_fuerte()` (`scripts/verify_ai.py`) NO descartara el
artículo antes de pasar a la IA, y aparentemente influyeron también en el
propio juicio de la IA.

**Corrección**: `scripts/fetch_rss.py`, `_ARTICULOS_RELACIONADOS_RE` ahora
también cubre `también puedes leer:` y la frase `si quieres conocer
otras noticias parecidas a` (que en la práctica precede siempre a ese
bloque en esta plantilla) -- un mecanismo general para cualquier fuente
que use esta variante, no solo Notiapure.

**Corrección retroactiva**: se eliminaron por completo
`sismo::Apure::2026-08-05::mag6.3` y
`sismo::Anzoategui::2026-08-05::mag6.3` de `docs/data/noticias.json`,
`data/historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl` y
`data/publicados.json`. Se regeneró `docs/data/estadisticas.json`.

### 3. Rescate de cuerpos 41 días después del terremoto de La Guaira se publicó como un sismo NUEVO

La fuente (El Periódico de Monagas) describe la extracción de 4 cuerpos
de un edificio colapsado en Caraballeda, La Guaira, "en el día 41
posterior a los terremotos de magnitudes 7.5 y 7.2... del pasado 24 de
junio" -- una labor de rescate en curso de un sismo de más de un mes de
antigüedad, no un evento sísmico ocurriendo ahora. Se publicó de todas
formas como `sismo::La Guaira::2026-08-04`, `APROBADO_IA`.

**Causa raíz**: el filtro determinista de retrospectiva
(`_PATRON_RETROSPECTIVA` en `scripts/verify_ai.py`) ya cubre "41 días
después de" pero con la unidad de tiempo DESPUÉS del número; este
artículo la pone ANTES ("día 41 posterior a"), una variante de redacción
no cubierta.

**Corrección**: se agregó a `_PATRON_RETROSPECTIVA` la variante `(dia|
dias) N posterior(es) a`, general para cualquier número.

**Corrección retroactiva**: se eliminó por completo
`sismo::La Guaira::2026-08-04` de `docs/data/noticias.json`,
`data/historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl` y
`data/publicados.json`.

### 4. Sequía en la Alta Guajira (Zulia) se publicaba con severidad CRÍTICA solo por "animales muertos"

"Pozos secos y animales muertos: Alta Guajira comienza a sufrir los
estragos de El Niño" -- artículo íntegro sobre mortalidad de ganado/fauna
por sequía (comunidades wayuu, jagüeyes secos), sin ninguna víctima
humana. Se publicó con severidad crítica (`sequia::Zulia::2026-08-05`)
porque "muertos" está en la lista de palabras clave de severidad crítica
sin distinguir si la muerte es humana o animal.

**Corrección**: `scripts/classify.py`, nuevo mecanismo en
`_contiene_palabra_clave_no_negada()`: para las palabras de muerte
ambiguas entre persona/animal ("muerto/a/os/as", "murió", "ahogado/a/os/
as" -- a diferencia de "fallecidos"/"asesinado", que en la prensa
venezolana solo se usan para personas), si la coincidencia está pegada a
una palabra de contexto animal ("animal(es)", "ganado", "reses",
"vacas", etc.) no cuenta como evidencia de severidad crítica. Una
palabra de muerte humana real en otra parte del mismo texto (p.ej.
"falleció", o "murió" sin contexto animal cerca) sigue disparando
severidad crítica con normalidad -- el filtro es por proximidad textual
a la palabra específica, no un descarte del artículo completo.

**Corrección retroactiva**: `sequia::Zulia::2026-08-05` se corrigió de
severidad `critico` a `sin_clasificar` (no hay otra palabra clave de
severidad en el texto) en `docs/data/noticias.json` (`render.
redactar_noticia()` para regenerar el texto de la tarjeta),
`data/historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl` y
`data/publicados.json`. El evento no se eliminó (la ubicación Zulia es
correcta -- el propio artículo aclara que la Alta Guajira "se comparte
entre Colombia y Venezuela por el lado del estado Zulia"). Se regeneró
`docs/data/estadisticas.json`.

### Informes narrativos: 2 quedan con referencias desactualizadas, no regenerados en esta sesión

`docs/data/informes/2026-08_sismo.json` y `2026-08_general.json` todavía
mencionan el rescate de La Guaira ya retractado (hallazgo 3);
`docs/data/informes/2026-08_sequia.json` todavía describe la sequía de
Zulia como "severidad crítica" (hallazgo 4, ahora sin_clasificar). Mismo
caso que sesiones anteriores: la narrativa se genera con Groq y
`GROQ_API_KEY` no está disponible en este entorno. `scripts/
build_informes.py` regenerará el informe del mes en curso en la próxima
corrida de producción, a partir de los datos ya corregidos. Confirmado
con `scripts/detectar_inconsistencias.py`, que detectó correctamente las
2 referencias a la fuente muerta de La Guaira en sus informes mensual y
general (exactamente el evento retractado aquí) sin que se le pidiera
nada.

### Pendiente de discutir: protesta gremial de Sintrasalud Falcón, ¿es un evento de orden público?

`orden_publico::Falcon::2026-08-04` ("Sintrasalud Falcón protesta por ser
excluidos del «bono de vacaciones»") es, leyendo el artículo completo, un
dirigente sindical declarando a la prensa que un grupo de trabajadores de
salud está "concentrado en la entrada del Hospital de Coro" para
reclamar un bono de vacaciones -- sin ninguna mención de cierre de vías,
disturbios, ni tamaño de la concentración. Es el mismo patrón ya
documentado como pendiente el 02-08-2026 (marchas/concentraciones
políticas sin evidencia fuerte de disturbio NI declaración explícita de
que fueron pacíficas): diseñar un filtro que descarte "concentración
gremial sin evidencia de disrupción" arriesga perder coberturas
iniciales de disturbios reales que aún no mencionan una palabra de
evidencia fuerte específica. A diferencia de los casos de Nueva
Esparta (03-08, cierre real de una avenida) y Bolívar (documentado el
02-08, "tranca" real por el servicio eléctrico), aquí no hay ninguna
evidencia de disrupción, solo una declaración de prensa. **No se corrigió
nada en este caso** -- queda documentado como pendiente de decisión del
usuario, no corregido a ciegas.

### Pruebas

6 casos nuevos: 3 en `tests/test_fetch_rss_limpieza.py` (nuevo archivo --
la variante "también puedes leer" real, control de que la variante
original "lea también" sigue funcionando, control de que texto sin
boilerplate no se altera), 1 en `tests/test_verify_ai_filtros.py` (la
variante real "día N posterior a" de retrospectiva), 2 en `tests/
casos_clasificacion.jsonl` (la sequía de Zulia con severidad corregida a
partir del texto real, y un control sintético de que una muerte humana
real cerca de la palabra clave no se descarta aunque el mismo artículo
mencione animales muertos en otra parte). Regresión completa contra
`data/historico_fuentes_texto.jsonl` (ya con las 3 líneas retractadas
eliminadas): sin cambios inesperados, solo los 4 casos ya conocidos y
documentados como limitación (corredor Barinas-Mérida, CCCT/Chacao).
`python3 -m pytest tests/` → 172 passed, 4 xfailed (conocidos, sin
relación), 1 xpassed (conocido, sin efecto real). `python3 scripts/
validar_configs.py` → OK. `python3 scripts/detectar_inconsistencias.py`
→ 4 fuentes muertas detectadas correctamente (2 ya conocidas del
28-07-2026, 2 nuevas de esta sesión, ver arriba); 6 pares de posibles
duplicados sin relación con esta auditoría (preexistentes, por palabras
compartidas en el link).

---

## Auditoría diaria automática (06-08-2026): sin errores nuevos, un caso de duplicado cruzado por tipo pendiente de discutir

Auditoría de rutina de las 11 alertas publicadas dentro de la ventana de
48 horas (03-08 a 06-08-2026), comparando cada una contra el texto real
de sus fuentes. De esas 11, solo el incendio forestal de Trujillo
(`incendio::Trujillo::2026-08-06`) es genuinamente nueva desde la
auditoría anterior (05-08-2026, PR #145); el resto ya había sido
cubierta por esa sesión. No se encontró ningún error de clasificación
nuevo -- se revisaron con especial atención por tener severidad
distinta de `sin_clasificar` o por lucir potencialmente confusas:

- `incendio::Yaracuy::2026-08-05` (severidad `crítico`, dos fallecidos):
  el texto guardado en `historico_fuentes_texto.jsonl` es solo el
  resumen RSS ("Dos hermanos fallecieron este lunes en Barquisimeto...
  en el estado Yaracuy"), que mezcla dos topónimos y podría parecer un
  error de ubicación. Se descargó el artículo completo
  (laprensadelara.com) para confirmarlo: la explosión de la bombona de
  gas ocurrió en el sector El Resbalón, **municipio Manuel Monge,
  estado Yaracuy** (correcto); los hermanos fueron trasladados y
  fallecieron 9 días después en un hospital de Barquisimeto (Lara), que
  es solo el lugar del deceso, no del hecho. Ubicación y severidad
  correctas.
- `inundacion::Apure::2026-08-05` (severidad `alto`, "~2.000
  damnificados"): confirmado con el texto real (notiapure.com.ve) que
  la crecida del río Arauca en la parroquia Urdaneta, municipio Páez,
  es reciente y la cifra de damnificados es la que dispara la severidad
  `alto` vía `config/keywords.yaml`. No hay un evento de inundación
  anterior en Apure en `data/historico_eventos.jsonl` del que esta nota
  sea un duplicado o una nota puramente retrospectiva de mitigación
  antigua.
- `infraestructura_electrica::Monagas::2026-08-05`,
  `infraestructura_electrica::Barinas::2026-08-04`,
  `inundacion::Yaracuy::2026-08-04`: confirmadas contra el texto real,
  clasificación y ubicación (incluyendo la parroquia "Alto de Los
  Godos" de Monagas) correctas.

### Pendiente de discutir: mismo evento de protesta por apagones en Carabobo publicado dos veces, una vez como `infraestructura_electrica` y otra como `orden_publico`

`infraestructura_electrica::Carabobo::2026-08-04` (fuentes:
elperiodicodemonagas.com.ve + primicia.com.ve) y
`orden_publico::Carabobo::2026-08-04` (fuente: elpitazo.net) describen,
leyendo los tres artículos, el mismo hecho real: los cacerolazos y
protestas de la noche del lunes 3 de agosto en el sector El Trigal y
frente a la Quinta Carabobo (residencia del gobernador Rafael Lacava)
por los apagones prolongados en Valencia. Son dos alertas separadas y
visibles al público para lo que es un solo evento.

**Causa raíz identificada (no corregida)**: `clasificar_item()` en
`scripts/classify.py` solo puede asignar UN tipo por item (el primero
detectado en el orden de `config/keywords.yaml`,
`tipo_principal = item["tipos"][0]` en `scripts/verify.py`), y la clave
de deduplicación (`clave_dedup`) incluye el tipo. Como estas tres
notas provienen de tres artículos/fuentes DISTINTOS que cada uno acabó
con un tipo principal distinto (dos con `infraestructura_electrica`,
uno con `orden_publico`), el sistema nunca las considera candidatas a
fusión -- la deduplicación actual solo opera dentro del mismo
`(tipo, ubicación, fecha)`. `scripts/detectar_inconsistencias.py` (el
chequeo de duplicados por palabras compartidas en el link) tampoco lo
detecta, porque los tres links no comparten ninguna palabra no
genérica.

**Por qué no se corrigió a ciegas**: diseñar una fusión automática
cruzando tipos distintos para el mismo `(ubicación, fecha)` tiene un
trade-off real y no trivial -- un incendio real y una protesta real
ocurriendo el mismo día en el mismo estado son eventos genuinamente
distintos y NO deberían fusionarse solo por coincidir en fecha/ubicación;
haría falta alguna señal de similitud de contenido (títulos, resumen,
palabras clave del hecho) para distinguir "mismo evento cubierto por
dos ángulos" de "dos eventos distintos que coinciden en fecha", y ese
diseño no existe todavía en el sistema. Queda documentado aquí como
pendiente de decisión del usuario -- no se fusionó ni se eliminó
ninguna de las dos alertas.

### Pruebas

Ningún cambio de código ni de datos publicados en esta sesión (solo
esta nota de auditoría). `python3 scripts/validar_configs.py` → OK.
`python3 scripts/detectar_inconsistencias.py` → mismos 6 pares de
duplicados por palabras de link ya documentados como falsos positivos
en sesiones anteriores (ninguno corresponde al caso de Carabobo descrito
arriba, que se encontró por lectura manual de los artículos) y las
mismas 2 fuentes muertas en informes de julio ya documentadas el
02-08-2026 (sin `GROQ_API_KEY` en este entorno para regenerarlas).

---

## Auditoría diaria automática (07-08-2026): "La Guaira" y parroquia homónima de otro estado por un bug de proximidad, titular embebido de otra nota, y un anuncio positivo de Corpoelec

Auditoría de rutina de las 15 alertas publicadas entre el 05-08 y el
07-08-2026 (la ventana 05-08/06-08 ya había sido cubierta por las dos
sesiones anteriores). De las 9 alertas genuinamente nuevas desde la
auditoría del 06-08-2026, se encontraron y corrigieron 4 errores reales
(2 de ellos con la misma causa raíz de fondo); no quedó ningún caso
ambiguo pendiente de discutir esta vez.

### 1. `_ventana_cerca()` solo comparaba la PRIMERA PALABRA de un nombre de estado de dos palabras -- "La Guaira" se anclaba a cualquier "la" suelto del texto

Un artículo-resumen nacional de El Periódico de Monagas ("Protestas en
siete estados del país por cortes eléctricos") menciona, en una simple
lista de estados con protestas por apagones ("...Cojedes, Distrito
Capital, La Guaira, Monagas, Zulia"), el nombre "La Guaira" sin ninguna
evidencia real cerca de esa mención específica. Aun así, el sistema
publicó `orden_publico::La Guaira::2026-08-07`.

**Causa raíz**: `_ventana_cerca()` (`scripts/classify.py`) construye la
lista de posiciones candidatas de un estado comparando solo la PRIMERA
PALABRA del nombre normalizado (`t == primera_palabra`) en vez de la
frase completa -- para nombres de un solo token esto es correcto, pero
para "La Guaira" la primera palabra es "la", uno de los artículos más
comunes del español. La función itera esas posiciones en orden y
devuelve la ventana de la PRIMERA que tenga una palabra clave de tipo
cerca -- en este artículo, un "la" cualquiera al inicio del texto
("...protestas la noche del jueves...") calificó antes de llegar a la
mención real de "La Guaira" (al final, en la lista de estados), dándole
al estado una ventana de evidencia que en realidad describe otra parte
del artículo sin relación alguna con La Guaira.

**Corrección**: `_ventana_cerca()` ahora compara la secuencia completa de
tokens del candidato (`tokens[i:i+n] == candidato_tokens`), igual que ya
hacía `_posiciones_de_estados()` para el cálculo de fronteras entre
estados -- corrige el mismo problema latente para cualquier nombre de
estado de más de una palabra ("Nueva Esparta", "Delta Amacuro", "Distrito
Capital"), no solo "La Guaira".

**Corrección retroactiva**: se eliminó por completo
`orden_publico::La Guaira::2026-08-07` de `docs/data/noticias.json`,
`data/historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl` y
`data/publicados.json`.

**Efecto secundario sin impacto en datos publicados**: la misma
corrección le quita a un cluster de inundaciones de Caracas/La Guaira ya
publicado (26-07-2026, `inundacion::Distrito Capital`, fusión de 6
fuentes) la detección aislada de "La Guaira" en 2 de sus fuentes -- esa
detección nunca generó una alerta propia (el evento fusionado siempre se
publicó solo como Distrito Capital) y dependía, a su vez, de que el pie
de página en inglés ("The post ... appeared first on") de una de esas
fuentes NO se estuviera limpiando por un desorden de palabras en
`_BOILERPLATE_RE` (bug preexistente, no introducido ni corregido en esta
sesión, sin ningún caso real conocido que lo dispare hoy -- queda como
posible mejora futura, no bloqueante).

### 2. La misma mención suelta de "Monagas" (el estado vecino) en esa lista se confundía con una parroquia real y homónima dentro de Zulia

El mismo artículo generó, para el evento correctamente ubicado en Zulia
(`orden_publico::Zulia::2026-08-07`), una atribución de "Municipio
Almirante Padilla, Parroquia Monagas" -- Zulia sí tiene, por coincidencia,
un municipio (Almirante Padilla, la isla de Toas) con una parroquia real
llamada "Monagas", única a nivel nacional. La palabra "Monagas" en el
texto nombra al ESTADO vecino (parte de la misma lista de estados con
protestas), no esa parroquia.

**Causa raíz**: `_buscar_parroquia_directa()`/`_buscar_municipio_directo()`
(`scripts/classify.py`) ya excluían una coincidencia si el nombre era
idéntico al del propio estado o al del país ("Venezuela", corregido el
02-08-2026 por el mismo motivo -- ver esa entrada), pero no comprobaban si
el nombre coincidía con el de OTRO estado. Un chequeo del corpus completo
de `config/ubicaciones_detalle.json` confirmó que el problema es
sistémico: 5 combinaciones adicionales de municipio/parroquia son, por
coincidencia, únicas a nivel nacional Y homónimas de un estado distinto
(p.ej. municipio "Aragua" dentro de Anzoátegui, municipio "Anzoátegui"
dentro de Cojedes, parroquias "Anzoátegui"/"Guárico" dentro del municipio
Morán en Lara) -- todas expuestas al mismo riesgo con cualquier artículo
que mencione varios estados a la vez (muy común en coberturas de apagones
o lluvias a nivel nacional).

**Corrección**: nueva función `_nombres_estados_norm()` (con caché) que
devuelve los nombres normalizados de los 24 estados; se excluye como
evidencia de municipio/parroquia cualquier coincidencia con ese conjunto,
en los 3 puntos donde ya se excluía el nombre del propio estado o del
país.

**Corrección retroactiva**: `orden_publico::Zulia::2026-08-07` se
corrigió de "Municipio Almirante Padilla, Parroquia Monagas" a solo
"Zulia" (parroquia `null`) en `docs/data/noticias.json` (`render.
redactar_noticia()` para regenerar título/texto), `data/
historico_eventos.jsonl`. El evento en sí (tipo/ubicación/severidad) NO
se tocó -- la mención de "manifestantes exigen..." cerca de "Zulia" es el
mismo patrón de "manifestantes sueltos sin evidencia fuerte explícita" ya
documentado como zona gris en sesiones anteriores (28-07, 02-08, 04-08),
no algo a decidir a ciegas hoy.

### 3. Titular de OTRA nota embebido, sin punto que lo separe, en medio del cuerpo de un artículo de El Pitazo

Un artículo íntegro de El Pitazo sobre presos políticos en huelga de
hambre en el Fuerte Guaicaipuro (que está en el estado Miranda, jamás
mencionado en el texto) traía embebido, en medio del cuerpo, el titular
de una nota totalmente distinta: "Zulia | Policía encuentra cuerpo de
coronel retirado de la GN con rastros de violencia", pegado directamente
al texto real sin ningún punto que los separe. El sistema publicó
`orden_publico::Zulia::2026-08-06` -- la única mención de "Zulia" en todo
el artículo venía de esa nota ajena.

**Causa raíz**: El Pitazo (y posiblemente otros medios con la misma
plataforma) usa la plantilla fija "Estado | Titular" tanto para el propio
titular de sus notas regionales (siempre al inicio del texto, ej.
"Bolívar | Hombres armados atacan...") como para tarjetas/widgets de
recirculación insertados EN MEDIO del cuerpo del artículo -- un patrón
nuevo de "artículos relacionados" no cubierto por ninguna de las 3
variantes ya filtradas (`_ARTICULOS_RELACIONADOS_RE`, todas ancladas a
una frase tipo "lea también:").

**Corrección**: nuevo regex `_NOMBRE_ESTADO_SEGUIDO_DE_PLECA_RE`
(`scripts/fetch_rss.py`), construido dinámicamente desde
`config/estados.yaml` (nombre canónico + alias), que elimina cualquier
"NombreDeEstado |" en cualquier posición del texto -- se confirmó contra
el corpus real que, cuando esta plantilla es legítima (el titular del
propio artículo), el estado real siempre se repite explícitamente más
adelante en el cuerpo, así que quitar solo la marca "Estado |" (no el
resto del titular, para no sobre-ajustar a un formato que varía nota a
nota) no pierde información real en ningún caso observado.

**Corrección retroactiva**: se eliminó por completo
`orden_publico::Zulia::2026-08-06` de `docs/data/noticias.json`, `data/
historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl` y `data/
publicados.json` (mismo criterio que casos anteriores de ubicación
totalmente infundada: el texto, ya limpio, no menciona ningún estado real
-- no se reasignó a Miranda por no tener evidencia textual explícita de
eso tampoco).

### 4. Variante adicional de "artículos relacionados" encontrada al investigar el hallazgo 3: "Leer también:" (infinitivo) de El Impulso

Al revisar `orden_publico::Distrito Capital::2026-08-07` (El Impulso,
familiares de presos políticos protestando frente a la Cancillería) se
encontró que el texto traía embebidos DOS enlaces "Leer también:" hacia
notas sin relación ("OVP denuncia tres muertes en El Marite y eleva a 51
las víctimas fatales en cárceles venezolanas"), con palabras de severidad
("muertes", "víctimas fatales") de un suceso carcelario completamente
distinto. Esta vez no llegó a cambiar el resultado publicado (severidad
ya era `sin_clasificar`), pero es el mismo riesgo lat­ente ya documentado
para "también puedes leer"/"si quieres conocer otras noticias parecidas
a" (05-08-2026): el infinitivo "Leer también:" no estaba cubierto por
`_ARTICULOS_RELACIONADOS_RE`, que solo reconocía el imperativo "Lea/Lee
también:".

**Corrección**: `_ARTICULOS_RELACIONADOS_RE` (`scripts/fetch_rss.py`)
ahora también cubre "leer también:".

**Corrección retroactiva**: ninguna -- el evento ya publicado
(`orden_publico::Distrito Capital::2026-08-07`) no cambia de resultado
con el texto limpio (se verificó explícitamente). Se corrige de raíz para
prevenir un futuro caso donde la nota embebida sí altere la severidad.

### 5. "corpoelec" como palabra clave suelta de tipo generaba una alerta de falla eléctrica a partir de un anuncio POSITIVO de la empresa

`infraestructura_electrica::Zulia::2026-08-07` (Noticia al Día, Zulia) es
un artículo íntegro sobre el gobernador de Zulia entregando 376
transformadores nuevos "para fortalecer y optimizar el sistema eléctrico"
-- ninguna falla en curso, ningún apagón, ninguna interrupción de
servicio. Se publicó como falla eléctrica porque "Corpoelec" (la empresa
eléctrica estatal, mencionada aquí en un contexto puramente positivo) es
la única palabra clave de tipo presente en `config/keywords.yaml`.

**Causa raíz**: "corpoelec" está en la lista de palabras clave de tipo de
`infraestructura_electrica` sin ninguna señal de que describa una falla
real -- a diferencia de "apagón"/"corte de luz"/"falla eléctrica", el
nombre de la empresa aparece igual de a menudo en coberturas de fallas
reales que en anuncios corporativos, inauguraciones o entregas de
equipos.

**Corrección**: nueva función `_es_anuncio_corpoelec_sin_falla()`
(`scripts/classify.py`, mismo patrón que
`_es_manifestacion_pacifica_sin_evidencia_fuerte()`/`_es_boletin_
estadistico_salud_sin_alarma()`: evaluada sobre el ARTÍCULO COMPLETO, no
solo la ventana de proximidad, porque la mención de "Corpoelec" suele
estar al final del artículo -- voz oficial/atribución -- mientras la
evidencia real de la falla está varios párrafos antes): si "corpoelec" es
la única señal de tipo y ninguna evidencia fuerte de
`infraestructura_electrica` aparece en ningún punto del artículo, se
descarta el tipo. Al implementarlo se descubrió que la lista de
evidencia fuerte existente era demasiado estrecha para el texto real --
rompía 3 casos ya publicados y correctos que sí describían fallas reales
pero con frases no cubiertas ("restablecer el suministro/servicio" en vez
de "apagón" explícito; "fallas en el servicio eléctrico" con "en el
servicio" entre ambas palabras, no adyacentes como en "falla eléctrica";
"sin energía eléctrica" en vez de "sin electricidad") -- se amplió
`_EVIDENCIA_FUERTE_POR_TIPO["infraestructura_electrica"]` con esas 3
variantes antes de dar el fix por bueno.

**Corrección retroactiva**: se eliminó por completo
`infraestructura_electrica::Zulia::2026-08-07` de `docs/data/
noticias.json`, `data/historico_eventos.jsonl`, `data/
historico_fuentes_texto.jsonl` y `data/publicados.json`. Se regeneró
`docs/data/estadisticas.json`.

### Informes narrativos: 2 quedan con referencias a la fuente retractada del hallazgo 3, no regenerados en esta sesión

`docs/data/informes/2026-08_general.json` y `2026-08_orden_publico.json`
todavía listan la fuente de El Pitazo sobre el Fuerte Guaicaipuro
(hallazgo 3, ahora retractada) entre sus fuentes. Mismo caso que sesiones
anteriores: `GROQ_API_KEY` no está disponible en este entorno.
`scripts/build_informes.py` regenerará el informe del mes en curso en la
próxima corrida de producción, a partir de los datos ya corregidos.
Confirmado con `scripts/detectar_inconsistencias.py`.

### Pendiente de discutir (sin corregir, no bloqueante): `orden_publico::Aragua::2026-08-07` y `orden_publico::Zulia::2026-08-07` vienen del mismo artículo

`scripts/detectar_inconsistencias.py` marca este par por palabras
compartidas en el link. A diferencia de los hallazgos 1 y 2 (ubicación
infundada), aquí ambos estados sí tienen evidencia real -- Aragua por "En
San Mateo, Aragua, también protestaron..." y Zulia por la mención en la
lista del OVCS -- son dos eventos separados generados por un mismo
artículo-resumen nacional, el mismo patrón general ya documentado como
pendiente el 06-08-2026 (Carabobo, tipos distintos) y el 02-08/04-08
(varios estados en una sola cobertura). No se fusionó ni se eliminó
ninguna de las dos.

### Pruebas

13 casos nuevos: 4 en `tests/casos_clasificacion.jsonl` para el bug de
`_ventana_cerca()` (el caso real de La Guaira/Zulia, un control de que
"La Guaira" con evidencia genuina cerca sigue funcionando, y el
reemplazo -- vía `xfail` documentado en `test_classify_casos.py`, sin
reescribir la línea original append-only -- de un caso previo del
30-07-2026 cuya ubicación esperada dependía, sin saberlo, del mismo bug),
1 caso del bug de Fuerte Guaicaipuro/Zulia (texto ya limpio), 4 en
`tests/test_fetch_rss_limpieza.py` (el titular embebido real, un control
de que el titular legítimo al inicio del propio artículo sigue
funcionando, un control de que una pleca sin nombre de estado antes no se
toca, y la variante real "leer también:"), 3 en `casos_clasificacion.jsonl`
para "corpoelec" (el caso real sin falla, un control real de evidencia
lejos de la ventana, un control sintético de "restablecer el suministro").
Regresión completa contra las 63 fuentes vigentes de
`data/historico_fuentes_texto.jsonl` (ya con las 3 fuentes retractadas
eliminadas): sin cambios inesperados, solo el efecto secundario sin
impacto en datos publicados descrito en el hallazgo 1 y la pérdida
correspondiente del tipo "incendio" (evidencia lejos de la ventana, mismo
patrón) en la detección aislada -- nunca publicada por separado -- de
Monagas dentro del artículo de cacerolazos del hallazgo 1.
`python3 -m pytest tests/` → 194 passed, 5 xfailed (4 conocidos sin
relación + el nuevo de esta sesión), 1 xpassed (conocido, sin efecto
real). `python3 scripts/validar_configs.py` → OK. `python3 scripts/
detectar_inconsistencias.py` → 9 pares de posibles duplicados (7 ya
documentados en sesiones anteriores + el nuevo del hallazgo pendiente de
discutir arriba), 4 fuentes muertas en informes (2 ya conocidas del
02-08-2026 + 2 nuevas de la retracción del hallazgo 3, ver arriba).

---

## Auditoría diaria automática (08-08-2026): filtro determinista saltado sin GROQ_API_KEY, artículo-tally retrospectivo republicado como 6 alertas nuevas, y 3 falsos positivos adicionales

Auditoría de rutina de las 14 alertas publicadas/actualizadas desde la
auditoría del 07-08-2026, comparando cada una contra el texto real de sus
fuentes (`data/historico_fuentes_texto.jsonl`). Las 9 más recientes
(21:05-22:08 UTC del 08-08) llegaron todas con
`estado_verificacion: PASADO_POR_FALLA_TECNICA` -- sin `GROQ_API_KEY`
configurada en este entorno -- y se revisaron con especial cuidado, como
pide el criterio de esta auditoría. Se encontraron y corrigieron 5 causas
raíz distintas, con 9 alertas retractadas en total; ningún caso quedó
publicado con un cambio sin verificar dos veces.

### 1. El filtro determinista (retrospectiva/vialidad/incendio/deslizamiento/sismo) se saltaba por completo cuando GROQ_API_KEY no está configurada

`verificar_evento_con_ia()` (`scripts/verify_ai.py`) comprobaba
`if not api_key: return _finalizar_evento(evento, grupos_fuentes,
error_sistema=True)` ANTES de calcular `obvios_rechazados` -- el bloque de
filtros deterministas (regex puro, sin ninguna llamada a la IA) vivía
varias líneas más abajo, así que nunca se ejecutaba en este entorno (sin
la clave). El camino paralelo de fallo transitorio de Groq
(`_manejar_falla_temporal`, tras agotar `MAX_CICLOS_ESPERA_GROQ`) sí
aplicaba el filtro correctamente, porque recibe `candidatos` (ya
filtrado), no `grupos_fuentes` -- la inconsistencia era solo entre esos
dos caminos. Esto explica por qué los peores falsos positivos, como ya
advierte el criterio de esta auditoría, se concentran precisamente en
`PASADO_POR_FALLA_TECNICA`: literalmente ningún filtro de plausibilidad
corre en ese caso, ni el de la IA ni el determinista.

**Corrección**: se movió el cálculo de `obvios_rechazados`/`candidatos`
ANTES de la comprobación de `api_key`, y esta última ahora usa
`_finalizar_evento(evento, candidatos, ...)` en vez de `grupos_fuentes` --
igual que ya hacía el camino de fallo transitorio. Un evento cuyas
fuentes sean TODAS descartadas por el filtro determinista ahora retorna
`None` (no se publica) sin importar si Groq está disponible o no.

### 2. El filtro de "evidencia fuerte de daño" para sismo no distinguía la negación -- "NO reportan daños estructurales" contaba como evidencia de daño

Al aplicar la corrección del hallazgo 1, `sismo::Monagas::2026-08-08::mag3.0`
(Maturin News, sismo de magnitud 3,0 en Aguasay) pasó a evaluarse por el
filtro determinista por primera vez -- y se descubrió que
`_sismo_sin_evidencia_fuerte()` NO lo rechazaba pese a que el propio
artículo dice explícitamente: "las autoridades de gestión de riesgo NO
reportan daños estructurales ni personas lesionadas producto de este
sismo de baja magnitud". `_EVIDENCIA_DANO_SISMO_RE.search()` solo
buscaba la frase "daños estructurales" en cualquier parte del texto, sin
mirar la negación "no reportan" justo antes -- un sismo menor SIN ningún
daño real se trataba como si tuviera evidencia fuerte de daño, y con
magnitud 3,0 (por debajo del umbral de 4,0) y sin la frase "se sintió"
tampoco, debía rechazarse igual.

**Corrección**: se reemplazó `_EVIDENCIA_DANO_SISMO_RE.search()` por
`_contiene_palabra_clave_no_negada()` (importada de `classify.py`, ya
usada ahí para el mismo problema con "muerto(s)/animal" del 05-08-2026),
que descarta una coincidencia si está negada a pocas palabras de
distancia. `_EVIDENCIA_DANO_SISMO_RE` se convirtió en una lista de frases
(`_EVIDENCIA_DANO_SISMO`) para poder iterarlas con esa función.

**Corrección retroactiva**: se eliminó por completo
`sismo::Monagas::2026-08-08::mag3.0` de `docs/data/noticias.json`,
`data/historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl` y
`data/publicados.json`.

### 3. Un incendio real en Petare (municipio Sucre, Miranda) se publicaba DOS VECES por la misma laguna ya conocida de "Caracas" como alias de Distrito Capital -- esta vez con Sucre, no con Chacao/Baruta/El Hatillo

Un incendio real de gran magnitud en "tres galpones" de El Llanito,
Petare -- el propio artículo dice explícitamente "municipio Sucre,
Petare, Miranda" -- se publicó también como `incendio::Distrito
Capital::2026-08-08` porque el texto menciona "Bombero de Caracas" (el
cuerpo de bomberos que respondió, no la ubicación del hecho). El cluster
se re-publicó así 4 veces a lo largo del día según se sumaban fuentes
(`El Llanito` fue cubierto también por La Patilla y El Carabobeno desde
la madrugada), todas con la ubicación equivocada -- la versión correcta
(`incendio::Miranda::2026-08-08`, Parroquia Petare) ya estaba publicada
en paralelo con la única fuente que sí resolvía bien.

**Causa raíz**: `LISTA_NEGRA_POR_ESTADO["Distrito Capital"]`
(`scripts/classify.py`) ya cubre este mismo problema para Chacao/Baruta/
El Hatillo (31-07-2026) -- pero Sucre, el quinto municipio real del área
metropolitana de Caracas (donde está Petare), faltaba en la lista.

**Corrección**: se agregó `"municipio sucre"` a
`LISTA_NEGRA_POR_ESTADO["Distrito Capital"]` y su remapeo a Miranda en
`_REMAPEO_MUNICIPIO_A_ESTADO` -- se usa la frase completa "municipio
sucre" (no "sucre" sola) porque Sucre también es el nombre de un estado
distinto, exactamente el mismo motivo por el que Chacao/Baruta/El Hatillo
sí podían usarse solos.

**Corrección retroactiva**: se eliminó `incendio::Distrito
Capital::2026-08-08` de `docs/data/noticias.json`, `data/publicados.json`
y las 4 instantáneas del cluster (mismo evento, re-publicado varias veces
según llegaban fuentes) de `data/historico_eventos.jsonl` y `data/
historico_fuentes_texto.jsonl`. `incendio::Miranda::2026-08-08` (la
versión correcta) no se tocó.

### 4. Un artículo-tally retrospectivo de protestas de toda una semana, reproducido por otro medio, se republicó como 6 alertas nuevas de "hoy"

"Más de una decena de protestas en una semana por cortes de luz a nivel
nacional" (La Prensa de Lara) es un recuento explícito: "**Desde el 31 de
julio hasta el 07 de agosto**, según registros del DIARIO LA PRENSA DE
LARA, se contabilizan al menos... 15 manifestaciones por la crisis
eléctrica en el país" -- cada protesta mencionada trae su propia fecha ya
pasada (03, 04, 05, 06, 07 de agosto). Turimiquire (Sucre) reprodujo el
mismo artículo casi textualmente el 08-08. Entre ambos generaron 6
alertas nuevas el día de la republicación, como si los hechos ocurrieran
ese mismo día: `orden_publico::Lara::2026-08-08` (La Prensa de Lara
directo), `orden_publico::Anzoategui::2026-08-08`, `orden_publico::
Distrito Capital::2026-08-08`, `infraestructura_electrica::
Lara::2026-08-08`, `infraestructura_electrica::Aragua::2026-08-08` e
`infraestructura_electrica::Carabobo::2026-08-08` (los últimos 5, vía
Turimiquire).

**Causa raíz**: ningún filtro existente cubre esta variante -- el
`_PATRON_RETROSPECTIVA` de `verify_ai.py` es específico de aniversarios/
"N días después" de un sismo, y `_ARTICULO_RETROSPECTIVO_LARGA_DURACION`
de `classify.py` (30-07-2026) solo cubre "meses de espera"/"así
aprendieron". Un artículo enmarcado explícitamente como un recuento de un
RANGO de fechas ya transcurrido no es un hecho nuevo de hoy, sin importar
el tipo de emergencia de fondo -- mismo principio que esos dos filtros,
variante de redacción distinta.

**Corrección**: nuevo regex `_RANGO_FECHAS_RETROSPECTIVO_RE` ("desde el D
de MES hasta el D de MES") agregado a
`_es_articulo_retrospectivo_larga_duracion()` (`scripts/classify.py`),
señal decisiva igual que las otras dos (no se anula por evidencia
fuerte). Se verificó contra las 81 fuentes de
`data/historico_fuentes_texto.jsonl` que esta frase, con fechas
variables, no aparece en ningún otro caso real ya publicado -- cero
riesgo de falso positivo nuevo.

**Corrección retroactiva**: se eliminaron las 6 alertas de `docs/data/
noticias.json`, `data/publicados.json`, `data/historico_eventos.jsonl` y
`data/historico_fuentes_texto.jsonl`. Se regeneró `docs/data/
estadisticas.json`.

**Nota**: 3 artículos más de Turimiquire sobre la crisis eléctrica
(`infraestructura_electrica::Bolivar::2026-08-08` -- declaraciones de un
dirigente político sobre riesgo estructural, sin incidente puntual
descrito; `infraestructura_electrica::Distrito
Capital::2026-08-08` -- columna de opinión de un coordinador regional
listando fallas crónicas por parroquia; y la fuente Turimiquire dentro de
`infraestructura_electrica::Merida::2026-08-08`, fusionada con una fuente
de La Patilla que sí describe una protesta real de hoy) NO usan esta
frase de rango de fechas y no se tocaron -- ver sección de pendientes más
abajo.

### 5. Historia de interés humano sobre DOS gatos rescatados de escombros (terremoto de hace más de un mes) disparaba deslizamiento -- el filtro de "gato" (29-07-2026) no cubría el plural

"Félix y Guaira: dos historias gatunas de supervivencia en La Guaira"
(Primicia) -- dos gatos "encontrados entre los escombros" en Caraballeda,
en tratamiento veterinario -- se publicó como `deslizamiento::La
Guaira::2026-08-08`. `_CONTEXTO_CONFLICTIVO_POR_TIPO["deslizamiento"]`
(`scripts/classify.py`) ya excluye "gato"/"mascota"/"perro"/etc. desde el
29-07-2026 (caso real: "Rescatan al gato Noche..."), pero solo en
singular -- "**Los dos gatos** reciben cuidados..." usa el plural, no
cubierto por comparación de palabra completa.

**Corrección**: se agregaron las formas plurales (gatos, gatas, gatitos,
perros, felinos, caninos, etc.) a la lista.

**Corrección retroactiva**: se eliminó `deslizamiento::La
Guaira::2026-08-08` de `docs/data/noticias.json`, `data/publicados.json`,
`data/historico_eventos.jsonl` y `data/historico_fuentes_texto.jsonl`.

### Pendiente de discutir: artículos de opinión/declaración política sobre la crisis eléctrica crónica, sin incidente puntual del día

3 fuentes -- `infraestructura_electrica::Bolivar::2026-08-08` (un
dirigente de Encuentro Ciudadano advirtiendo, en tiempo condicional, que
el déficit estructural "amenaza con un apagón masivo"), la fuente
Turimiquire de `infraestructura_electrica::Distrito
Capital::2026-08-08` (columna de opinión de un coordinador regional de
La Red Verde Caracas listando fallas crónicas por parroquia, con un
llamado a protestar) y la fuente Turimiquire de `infraestructura_
electrica::Merida::2026-08-08` (declaraciones de un dirigente de Primero
Justicia sobre "discriminación eléctrica" territorial) -- son columnas de
opinión/declaraciones políticas sobre la crisis eléctrica en general, sin
describir un corte o incidente concreto ocurrido ese día. Ninguna usa
lenguaje de rango de fechas (hallazgo 4) ni las frases ya cubiertas por
`_es_anuncio_corpoelec_sin_falla()` (07-08-2026). A diferencia de esos
filtros ya existentes, diseñar uno para "declaración política sin
incidente puntual" arriesga descartar coberturas legítimas que citan a un
vocero político junto a un corte real (patrón común en la prensa
venezolana) -- no se corrigió nada, y las 2 primeras fuentes son la ÚNICA
fuente de su alerta (permanecen publicadas); la tercera queda fusionada
con la fuente de La Patilla, que sí describe una protesta real de hoy en
Mérida, así que esa alerta en concreto no depende de la fuente dudosa
para justificarse.

### Pendiente de discutir (ya documentado en sesiones anteriores, mismo patrón): concentración gremial sin evidencia de disrupción

`orden_publico::Lara::2026-08-07` (El Impulso: jubilados y empleados de
la Gobernación de Lara concentrados para exigir el pago de un bono) es el
mismo patrón ya documentado como pendiente el 02-08 (Sintrasalud Falcón)
y el 05-08-2026: una concentración gremial de prensa, sin evidencia de
cierre de vías/disturbios ni declaración explícita de que fue pacífica.
No se corrigió nada -- mismo riesgo ya explicado en esas entradas
(diseñar el filtro arriesga perder coberturas iniciales de disturbios
reales).

### Pruebas

7 casos nuevos: 2 en `tests/test_verify_ai_filtros.py` (el sismo de
Monagas real con la negación, y su control sin negar), 1 más en el mismo
archivo (`test_filtro_deterministico_corre_incluso_sin_groq_api_key`,
que monkeypatchea `GROQ_API_KEY` fuera del entorno y confirma que
`verificar_evento_con_ia()` sigue rechazando un sismo menor obvio), y 4
en `tests/casos_clasificacion.jsonl` (el incendio real de Petare con
Distrito Capital excluido explícitamente, los dos gatos en plural, el
artículo-tally retrospectivo real de La Prensa de Lara, y un control
sintético de que una falla eléctrica puntual de un solo día -- sin rango
de fechas -- se sigue detectando con normalidad). Regresión completa
contra las 69 fuentes vigentes de `data/historico_fuentes_texto.jsonl`
(ya con las 12 líneas retractadas eliminadas -- 9 alertas finales más 3
instantáneas intermedias del cluster de Petare): sin cambios inesperados.
`python3 -m pytest tests/` → 211 passed, 5 xfailed (conocidos, sin
relación), 1 xpassed (conocido, sin efecto real). `python3 scripts/
validar_configs.py` → OK. `python3 scripts/detectar_inconsistencias.py`
→ 10 pares de posibles duplicados (9 ya documentados en sesiones
anteriores + ninguno nuevo relacionado con esta sesión), 6 fuentes
muertas en informes (2 ya conocidas del 02-08-2026 + 2 nuevas de la
retracción del hallazgo 3 de esta sesión, El Llanito/Petare + 2 más ya
conocidas). `GROQ_API_KEY` no disponible en este entorno para regenerar
los informes narrativos con las fuentes retractadas.

---

## A pedido del usuario (10-08-2026): sismo duplicado en 4 estados, incendio sin víctimas que no debía alertar, y un artículo-tally de incendios forestales

El usuario reportó 3 problemas concretos ya publicados y pidió diagnosticar
la causa raíz de cada uno, corregir de forma que no se repitan, y eliminar
las alertas afectadas. Se encontraron y corrigieron 3 causas raíz
independientes, con 6 alertas retractadas (5 por completo, 1 fusionada en
la mejor de sus 4 duplicados).

### 1. Un sismo de magnitud 7.4 en Colombia, sentido en Venezuela, se publicó como 4 alertas separadas (Distrito Capital, Táchira, Zulia, Miranda) en la misma corrida

`sismo::Distrito Capital::2026-08-10::mag7.4`, `sismo::Tachira::2026-08-10::
mag7.4`, `sismo::Zulia::2026-08-10::mag7.4` y `sismo::Miranda::2026-08-10`
se publicaron a los pocos segundos uno del otro (14:34:31 -- 14:34:41 UTC),
todos sobre el mismo sismo real (epicentro San José del Palmar, Chocó,
Colombia, magnitud actualizada de 6.6/6.7 a 7.4).

**Causa raíz 1 (la principal)**: `state.py` ya tiene un mecanismo dedicado
para este caso exacto -- `_mismo_sismo_ya_publicado()` descarta un sismo
si otro con la misma magnitud (o mención cruzada de estados) ya está en
`publicados`. Pero `filtrar_nuevos(eventos, publicados)` nunca escribía en
`publicados` durante su propio bucle -- esa escritura ocurría después, en
`marcar_publicados()`, llamada por separado desde `main.py` una vez
terminado el filtrado completo. Cuando los 4 estados del mismo sismo
llegan juntos en la misma corrida (el caso normal: un solo sismo grande se
detecta a la vez en varias fuentes/estados), cada uno se comparaba solo
contra el estado YA PERSISTIDO de corridas anteriores -- nunca contra los
otros 3 eventos del mismo sismo detectados en la corrida actual -- así que
ninguno se reconocía como duplicado del otro.

**Corrección**: `filtrar_nuevos()` (`scripts/state.py`) ahora registra
cada evento aceptado en `publicados` (se extrajo `_entrada_publicados()`,
reutilizada también por `marcar_publicados()`) inmediatamente dentro del
mismo bucle, no solo al final -- el segundo/tercer estado del mismo sismo,
procesado a continuación en la misma corrida, ya lo encuentra y se
descarta como duplicado. Efecto secundario beneficioso: esto también
corrige el mismo problema para cualquier otro tipo si dos fuentes del
mismo evento llegaran como items separados sin fusionarse en
`verify.agrupar_y_verificar()` (no solo sismo).

**Causa raíz 2 (por qué Miranda no se enganchaba ni con la magnitud ni con
la mención cruzada)**: la fuente de Miranda (La Prensa de Monagas,
"Actualizan magnitud del sismo en Colombia a 7.4...") tiene el texto
"magnitud del sismo en Colombia a 7.4" -- `extraer_magnitud()`
(`scripts/verify.py`) exige "magnitud" seguido DIRECTAMENTE del número
(`magnitud\s+(\d+[.,]\d+)`), así que no encontró ningún valor (a
diferencia de "Magnitud 7.4, profundidad 96 km" en el texto de El Pitazo,
que sí calza). Sin magnitud extraída, y sin que el texto mencionara
explícitamente otro estado venezolano, `_mismo_sismo_ya_publicado()`
tampoco podía correlacionarlo por la vía de mención cruzada. Investigando
esto se encontraron dos bugs más, no relacionados entre sí, que hacían que
esta fuente pareciera un sismo real en Miranda:

- **"tramo Miranda" (segmento vial de la Autopista Regional del Centro,
  ARC) se contaba como evidencia del ESTADO Miranda.** El texto de esta
  fuente trae pegada, sin relación con el sismo, una frase de clima ajena
  ("las intensas lluvias también causaron el colapso de árboles... en el
  tramo Miranda de la Autopista Regional del Centro (ARC)") -- la misma
  frase aparece, de forma legítima, en un artículo real sobre una tormenta
  en Distrito Capital/Miranda (Diario El Tiempo Trujillo), lo que sugiere
  que es contenido sindicado/repetido entre medios ese día. Se agregó
  `"tramo miranda"` a `LISTA_NEGRA_POR_ESTADO["Miranda"]`
  (`scripts/classify.py`) -- se confirmó que el artículo legítimo de la
  tormenta no depende de esta frase para su propia ubicación (tiene
  evidencia independiente: "Los Teques, estado Miranda", "municipio Los
  Salias").
- **"colapso de" (sin objeto) contaba como evidencia FUERTE de daño
  sísmico.** Con "tramo Miranda" ya excluido como ubicación, la misma
  frase ("colapso de árboles") también hacía que el filtro determinista
  `_sismo_sin_evidencia_fuerte()` (`scripts/verify_ai.py`) tratara este
  sismo como si tuviera evidencia fuerte de daño real, pese a que "colapso
  de árboles" por una tormenta no tiene ninguna relación con un sismo. Se
  reemplazó la entrada genérica `"colapso de"` en `_EVIDENCIA_DANO_SISMO`
  por variantes específicas con objeto (`"colapso de vivienda(s)"`,
  `"colapso de edificio(s)"`, `"colapso de estructura(s)"`) -- se verificó
  contra el corpus completo que la versión genérica solo tenía, además de
  este caso, coincidencias igualmente espurias ("colapso de algunos
  sistemas" de drenaje) y ningún caso real de daño sísmico que dependiera
  de ella.

**Corrección retroactiva**: se conservó `sismo::Zulia::2026-08-10::mag7.4`
(la versión más completa: 2 fuentes independientes, confirmado, severidad
media, con detalle real del impacto local en Maracaibo) y se eliminaron
por completo las otras 3 -- `sismo::Distrito Capital::2026-08-10::mag7.4`
y `sismo::Tachira::2026-08-10::mag7.4` (mismo duplicado exacto, misma
única fuente de El Pitazo, sin detalle local propio más allá de "se sintió
en Venezuela") y `sismo::Miranda::2026-08-10` (sin ubicación real tras el
fix de "tramo Miranda") -- de `docs/data/noticias.json`, `data/
historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl` y `data/
publicados.json`.

### 2. Un incendio de tres galpones en Petare, sin heridos ni fallecidos, no debía generar una alerta -- no existía ningún criterio de relevancia para incendio (a diferencia de vialidad, que sí lo tiene)

`incendio::Miranda::2026-08-08` ("Voraz incendio se registra en tres
galpones en Petare", El Periodico de Monagas) nunca menciona heridos ni
fallecidos en ninguna de sus 3 actualizaciones a lo largo de la noche; una
fuente distinta del mismo hecho real (Efecto Cocuyo, no incluida en el
evento publicado) lo confirma explícitamente: "Incendio en El Llanito deja
daños materiales pero **sin víctimas que lamentar**". El usuario señaló
que un incendio sin fallecidos no debería constituir una alerta -- al
revisar el código se encontró que `SYSTEM_PROMPT_TEMPLATE`
(`scripts/verify_ai.py`) ya tiene un criterio explícito de este tipo para
`tipo=vialidad` ("es un accidente de tránsito individual y rutinario...
son casos que atiende tránsito/ambulancia local, no algo que requiera
respuesta de la Cruz Roja"), pero NUNCA existió un criterio equivalente
para `tipo=incendio` -- ni en el prompt de la IA ni en un filtro
determinista de respaldo (que sí existen para vialidad/deslizamiento/
sismo, y para incendio pero solo en su variante vehicular).

**Corrección**:

1. Nuevo párrafo en `SYSTEM_PROMPT_TEMPLATE`, mismo patrón que vialidad:
   un incendio de una sola vivienda/apartamento/vehículo/estructura menor,
   ya sofocado y sin heridos/fallecidos/personas atrapadas o evacuadas, no
   requiere respuesta de la Cruz Roja.
2. Nuevo filtro determinista de respaldo `_incendio_estructura_menor_
   sin_evidencia_fuerte()` (`scripts/verify_ai.py`), mismo patrón que
   `_incendio_vehiculo_sin_evidencia_fuerte()`: solo se activa si el texto
   menciona vivienda/apartamento/galpón (deliberadamente SIN "local
   comercial"/"centro comercial" -- ese rango va de un solo local a un
   centro comercial entero, y ya hay casos reales publicados de incendios
   de centros comerciales sin víctimas explícitas que sí se consideran
   significativos, como el de Los Cedros en Nueva Esparta); descarta la
   fuente si no hay evidencia de heridos/fallecidos/atrapados/evacuados/
   rescatados/intoxicados/afectados por humo.
3. Al construir este filtro se encontró que `_VICTIMAS_INCENDIO_RE` (el
   usado por el filtro vehicular ya existente) tenía el mismo problema de
   negación ya corregido para sismo el 08-08-2026: un texto real de este
   mismo caso dice explícitamente "**No hubo heridos**, pero 5 personas
   resultaron afectadas por el humo" -- un regex simple habría contado
   "heridos" como evidencia pese a la negación. Se convirtió a una lista
   (`_VICTIMAS_INCENDIO`) evaluada con `_contiene_palabra_clave_no_negada()`,
   compartida por ambos filtros (vehicular y estructura menor), y se
   agregaron variantes no cubiertas antes (atrapado/evacuado/rescatado/
   intoxicado/afectado por el humo).

Al aplicar este filtro contra el corpus completo se encontró que
`incendio::Tachira::2026-08-08` ("Sofocan incendio en vivienda de San
Antonio", el mismo caso ya corregido de municipio en la sesión anterior)
también cae bajo el mismo criterio -- un incendio de una sola vivienda,
sin heridos ni fallecidos mencionados en ningún punto del texto.

**Corrección retroactiva**: se eliminaron por completo
`incendio::Miranda::2026-08-08` (las 3 instantáneas del cluster, una de
ellas con las fuentes de Efecto Cocuyo) e `incendio::Tachira::2026-08-08`
de `docs/data/noticias.json`, `data/historico_eventos.jsonl`, `data/
historico_fuentes_texto.jsonl` y `data/publicados.json`. Se verificó
contra el corpus completo que ningún otro incendio actualmente publicado
(centros comerciales, edificios, incendios forestales) cae bajo este
filtro -- el patrón "vivienda/apartamento/galpón sin víctimas" es
exclusivo de estos 2 casos.

### 3. Un artículo-tally de "26 incendios forestales" en Trujillo, ya sofocados, se publicó como si fuera un incendio nuevo de hoy

`incendio::Trujillo::2026-08-09` ("Bomberos sofocan 26 incendios
forestales en Trujillo. Las labores de combate incluyeron la atención de
9 incendios de gran magnitud", Primicia) es un resumen numérico de un
operativo de varios días YA controlado -- el mismo incendio forestal de
Trujillo/Carache que ya se venía cubriendo con actualizaciones puntuales
los días 06 y 07 de agosto (Puesto de Comando, cantidad de efectivos,
parroquias específicas). El titular usa "sofocan" (ya extinguidos) y un
conteo acumulado, no la descripción de un incendio puntual nuevo.

**Causa raíz**: ningún filtro existente cubre esta variante de
retrospectiva -- `_es_retrospectiva_obvia()` (verify_ai.py) es específica
de aniversarios/"N días después"; `_ARTICULO_RETROSPECTIVO_LARGA_DURACION`
y `_RANGO_FECHAS_RETROSPECTIVO_RE` (classify.py, 30-07 y 08-08-2026) cubren
"meses de espera" y un rango explícito de fechas ("desde el D de MES hasta
el D de MES") -- ninguno cubre un resumen numérico de incidentes sin rango
de fechas explícito.

**Corrección**: nuevo `_RESUMEN_TALLY_INCENDIOS_RE` (`scripts/classify.py`),
agregado a `_es_articulo_retrospectivo_larga_duracion()` -- descarta el
artículo completo (todos los tipos, no solo incendio, mismo criterio que
la función ya usa) si el texto menciona 5 o más "incendios" (umbral igual
al ya usado para `_NUMERO_FALLECIDOS_RE` en verify_ai.py, para no
descartar un reporte legítimo de un puñado de incendios simultáneos de
un mismo día). Se verificó contra el corpus completo que "N incendios"
(N>=5) no aparece en ningún otro caso real ya publicado.

**Corrección retroactiva**: se eliminó por completo
`incendio::Trujillo::2026-08-09` de `docs/data/noticias.json`, `data/
historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl` y `data/
publicados.json`. Los incendios forestales de Trujillo/Carache del 06 y
07 de agosto (actualizaciones puntuales del mismo operativo, sin patrón
de resumen numérico) no se tocaron.

### Informes narrativos: 6 fuentes nuevas quedan con referencias a las 3 fuentes retractadas de esta sesión

`docs/data/informes/2026-08_general.json` y `2026-08_incendio.json`
listan las 3 fuentes de incendio retractadas hoy (Diario La Nacion
Tachira, Efecto Cocuyo x2, El Periodico de Monagas, Primicia). Mismo caso
que sesiones anteriores: `GROQ_API_KEY` no disponible en este entorno;
`scripts/build_informes.py` regenerará ambos informes en la próxima
corrida de producción. Confirmado con `scripts/detectar_inconsistencias.py`.

### Pruebas

11 casos nuevos: 2 en `tests/casos_clasificacion.jsonl` para "tramo
Miranda" (el caso real del sismo sin ubicación, y un control real de que
el artículo legítimo de la tormenta Distrito Capital/Miranda no pierde su
propia ubicación), 2 más para el resumen-tally de incendios (el caso real
de Trujillo, y un control sintético de 2 incendios simultáneos por debajo
del umbral), 7 en `tests/test_verify_ai_filtros.py` (2 para "colapso de
árboles" no sísmico + control de "colapso de vivienda", 5 para el filtro
de estructura menor de incendio: galpones real, vivienda real, control
con heridos, control de la trampa de negación "No hubo heridos, pero...
afectadas por el humo", y 2 controles de que centro comercial/edificio no
pasan por este filtro). Regresión completa contra las 70 fuentes vigentes
de `data/historico_fuentes_texto.jsonl` (ya con las 8 instantáneas
retractadas eliminadas): sin cambios inesperados, solo el efecto
esperado en los 2 casos retractados de esta sesión (autocurados al
eliminarse su fuente del historico). `python3 -m pytest tests/` → 225
passed, 5 xfailed (conocidos, sin relación), 1 xpassed (conocido, sin
efecto real). `python3 scripts/validar_configs.py` → OK. `python3
scripts/detectar_inconsistencias.py` → mismos pares de posibles
duplicados que la sesión anterior (sin relación con estos hallazgos), 13
fuentes muertas en 5 informes (7 ya conocidas de sesiones anteriores + 6
nuevas de las retracciones de esta sesión, ver arriba).

---

## Auditoría diaria automática (09-08-2026): "municipio/parroquia ADJETIVO Nombre" rompía tanto la detección de municipio como, en un caso real, la del propio estado

Auditoría de rutina de las alertas publicadas/actualizadas desde la
auditoría del 08-08-2026 (`orden_publico::Sucre::2026-08-08`,
`incendio::Tachira::2026-08-08`; las demás ya publicadas en ese momento --
`incendio::Miranda::2026-08-08`, las 3 fuentes `PASADO_POR_FALLA_TECNICA`
de Merida/Bolivar/Distrito Capital -- ya habían sido revisadas y
documentadas en esa sesión, ver "Nota"/"Pendiente de discutir" ahí). Se
encontró y corrigió 1 causa raíz, con 2 alertas corregidas (1 con dato
retroactivo ajustado, 1 retractada por completo).

### 1. Un adjetivo intercalado entre "municipio"/"parroquia" y el nombre propio ("municipio fronterizo Bolívar") no calzaba con ningún nombre conocido -- y, peor, tampoco se reconocía como mención SUBESTATAL, dejando que "Bolívar" contara como evidencia del ESTADO Bolívar

`incendio::Tachira::2026-08-08` (Diario La Nacion Tachira, incendio en
una vivienda de San Antonio del Táchira) se publicó con
`municipio: "Rafael Urdaneta"`, pese a que el propio artículo dice
explícitamente "en el municipio fronterizo Bolívar" -- "Rafael Urdaneta"
solo aparece como nombre de un BARRIO ("en el barrio Rafael Urdaneta"),
que por coincidencia también es un municipio real de Táchira (distinto,
al otro extremo del estado). Al investigar la causa raíz se encontró un
caso más grave del mismo patrón, ya publicado desde el 29-07-2026:
`infraestructura_electrica::Bolivar::2026-07-29` (Diario La Nacion
Tachira, "Doce horas sin luz viviendas de El Palotal") -- un artículo que
JAMÁS nombra ningún estado explícitamente (ni Táchira ni Bolívar como
estado, solo "el municipio fronterizo Bolívar" y la parroquia El
Palotal), llevaba 11 días publicado como una alerta del estado Bolívar,
a más de 700 km de distancia real del hecho (El Palotal está en Táchira,
frontera con Colombia).

**Causa raíz (dos síntomas del mismo problema)**:

1. `_MUNICIPIO_RE`/`_PARROQUIA_RE` (`scripts/classify.py`) capturan todo
   el texto entre "municipio"/"parroquia" y la puntuación siguiente --
   con `re.IGNORECASE` aplicado a todo el patrón, esto incluye
   adjetivos en minúscula como "fronterizo" ("municipio fronterizo
   Bolívar" capturaba literalmente "fronterizo Bolívar", que no
   coincidía con ningún municipio conocido de Táchira). El sistema caía
   entonces al fallback de búsqueda libre (`_buscar_municipio_directo`),
   que sí encontraba "Rafael Urdaneta" mencionado en el texto (como
   nombre de un barrio) y lo tomaba como el único municipio, en vez del
   municipio Bolívar que el texto nombra explícitamente.
2. `_es_mencion_subestatal()` (usada por `_posiciones_de_estados()` y
   `_ventana_cerca()` para excluir menciones tipo "municipio Sucre" como
   evidencia del estado homónimo "Sucre") solo miraba la palabra
   INMEDIATAMENTE anterior. Con "municipio fronterizo Bolívar", esa
   palabra es "fronterizo", no "municipio" -- la exclusión no se activaba,
   y "Bolívar" se contaba como una mención normal del ESTADO Bolívar.

**Corrección**:

1. Nueva función `_resolver_con_posible_adjetivo()` (`scripts/
   classify.py`): si el candidato capturado por `_MUNICIPIO_RE`/
   `_PARROQUIA_RE` no coincide exacto con ningún nombre conocido, prueba
   si el nombre real es el SUFIJO del candidato (cubre cualquier cantidad
   de palabras intercaladas, no solo un adjetivo) -- solo se acepta si
   exactamente un nombre conocido del estado/municipio calza como sufijo;
   si hay más de uno, no se adivina. Reemplaza el `.get(candidato)` directo
   tanto para municipio como para parroquia en `detectar_municipio_
   parroquia()`.
2. `_es_mencion_subestatal()` ahora también reconoce el calificador dos
   posiciones atrás (`tokens[pos-2]`), además de la inmediatamente
   anterior -- cubre un único adjetivo intercalado ("municipio fronterizo
   X", "parroquia rural X", etc.).

Se confirmó contra las 71 fuentes de `data/historico_fuentes_texto.jsonl`
que "municipio fronterizo Bolívar" (Diario La Nacion Tachira) es la ÚNICA
ocurrencia real en todo el corpus de un adjetivo intercalado entre
"municipio"/"parroquia" y un nombre propio -- las 2 fuentes que lo usan
son, precisamente, las 2 corregidas aquí.

**Corrección retroactiva**:

- `incendio::Tachira::2026-08-08`: `municipio` corregido de "Rafael
  Urdaneta" a "Bolívar" en `docs/data/noticias.json` (`render.
  redactar_noticia()` para regenerar título/texto), `data/
  historico_eventos.jsonl` y `data/publicados.json`. El estado (Tachira),
  tipo y severidad no cambian -- el artículo sí nombra "Táchira"
  explícitamente ("Cuerpo de Bomberos de San Antonio del Táchira"), así
  que la detección de estado no estaba afectada aquí, solo el municipio.
- `infraestructura_electrica::Bolivar::2026-07-29`: se eliminó por
  completo de `docs/data/noticias.json` y `data/historico_eventos.jsonl`
  -- tras el fix, el texto de su única fuente ya no produce NINGUNA
  ubicación (ni estado ni municipio), porque nunca nombra un estado
  venezolano explícitamente; igual que otros casos ya documentados (ver
  hallazgos 2 y 3 del 08-08-2026), no se reasignó a Táchira por
  inferencia -- el sistema solo publica sobre evidencia textual explícita,
  nunca por el nombre del medio ("Diario La Nacion (Tachira)") ni por
  conocimiento externo de qué municipio pertenece a qué estado.
  `data/historico_fuentes_texto.jsonl` conservaba esta misma fuente
  MEZCLADA, en una instantánea anterior (15:31:32 UTC del 29-07), con la
  de un segundo evento real y no relacionado (El Pitazo, hombres armados
  disolviendo una protesta por apagones en Guasipati, sur del estado
  Bolívar -- ese sí correctamente ubicado) -- se editó esa línea para
  quitar solo la fuente de Diario La Nacion Tachira, conservando la de El
  Pitazo (ajustando `num_fuentes` a 1, `score` a 0.75 y `confirmado` a
  `false` en `data/historico_eventos.jsonl`, según su propio peso en
  `config/sources.yaml`) en vez de eliminar la línea completa, para no
  borrar de paso el único rastro histórico de una fuente legítima y sin
  relación con este bug. `data/publicados.json` no tenía ninguna entrada
  para el evento de 2026-07-29 (ya fuera de su ventana reciente de
  deduplicación). Se regeneró `docs/data/estadisticas.json`.

**Nota**: la retracción de `infraestructura_electrica::Bolivar::2026-07-29`
deja 2 fuentes muertas nuevas en `docs/data/informes/2026-07_general.json`
y `2026-07_infraestructura_electrica.json` (Diario La Nacion Tachira, la
fuente retractada). Mismo caso que sesiones anteriores: `GROQ_API_KEY` no
disponible en este entorno; `scripts/build_informes.py` regenerará esos
informes en la próxima corrida de producción. Confirmado con `scripts/
detectar_inconsistencias.py` (4 fuentes muertas en 3 informes: 2 ya
conocidas del 02-08-2026 + las 2 nuevas de esta sesión).

### Pruebas

3 casos nuevos en `tests/casos_clasificacion.jsonl`: el incendio real de
San Antonio del Táchira ("municipio fronterizo Bolívar" -> municipio
Bolívar, no Rafael Urdaneta), el caso real de El Palotal (mismo texto
patrón, sin ningún estado nombrado -> sin ubicación, y explícitamente
`no_debe_aparecer_ubicacion: ["Bolivar"]`), y un control sintético para
el mismo fix aplicado a PARROQUIA ("parroquia rural Palotal, municipio
Bolivar del estado Tachira" -> parroquia Palotal, municipio Bolívar).
Regresión completa contra las 70 fuentes vigentes de `data/
historico_fuentes_texto.jsonl` (ya con la fuente retractada eliminada):
sin cambios inesperados -- la única fuente afectada por el fix es,
precisamente, la corregida en este hallazgo. `python3 -m pytest tests/`
→ 214 passed, 5 xfailed (conocidos, sin relación), 1 xpassed (conocido,
sin efecto real). `python3 scripts/validar_configs.py` → OK. `python3
scripts/detectar_inconsistencias.py` → mismos pares de posibles
duplicados que la sesión anterior (sin relación con este hallazgo), 4
fuentes muertas en informes (2 ya conocidas del 02-08-2026 + 2 nuevas de
esta sesión, ver arriba).

### Revisado sin cambios

`orden_publico::Sucre::2026-08-08` (La Patilla, concentración de Vente
Venezuela en Sucre por precariedad de servicios públicos): severidad y
ubicación consistentes con el texto de la única fuente, sin indicios de
error. `incendio::Miranda::2026-08-08` y las 3 fuentes `PASADO_POR_
FALLA_TECNICA` de Merida/Bolivar/Distrito Capital ya habían sido
revisadas en la auditoría del 08-08-2026 (ver esa entrada) -- sin cambios
desde entonces.

---

## Auditoría diaria automática (10-08-2026): la magnitud preliminar de un sismo ya publicado generaba una segunda alerta duplicada del mismo evento

Auditoría de rutina de las alertas publicadas/actualizadas desde la sesión
"A pedido del usuario (10-08-2026)" (commit `6f6d7f7`, 16:15 UTC), que ya
había corregido el cluster de 4 alertas duplicadas del sismo de Colombia y
2 incendios sin víctimas. Se encontró y corrigió 1 causa raíz, con 1
alerta retractada.

### El mismo sismo de Colombia sentido en Zulia se publicó una segunda vez, más de 3 horas después, con la magnitud preliminar todavía no actualizada

`sismo::Zulia::2026-08-10::mag6.6` (Nuevo Dia de Falcón, "Gobernador
Caldera: el Zulia sin afectaciones por sismo este 10Agos", 17:40:43 UTC)
es el MISMO sismo real que `sismo::Zulia::2026-08-10::mag7.4` (La Verdad
Zulia + El Periodico de Monagas, 14:34:38 UTC, ya conservado como la
versión canónica tras la corrección de las 16:15 UTC) -- mismo estado,
mismo día, mismo epicentro en San José del Palmar (Chocó, Colombia). La
única fuente de esta segunda alerta describe explícitamente "el sismo de
magnitud 6,6 que se registró en Colombia", la magnitud PRELIMINAR del
mismo evento antes de que el Servicio Geológico Colombiano la revisara a
7.4 (ver la fuente de El Periodico de Monagas en el hallazgo de las 16:15
UTC de hoy) -- no un sismo distinto.

**Causa raíz**: `_clave_evento()` (`scripts/state.py`) agrega la magnitud
a la clave de dedup de sismo (`sismo::Zulia::2026-08-10::mag7.4` vs
`::mag6.6`) precisamente para no fusionar dos sismos genuinamente
distintos el mismo día en el mismo estado. Pero un sismo real casi
siempre se reporta primero con una magnitud preliminar y después con la
definitiva -- eso hace que la clave cambie aunque sea el mismo evento.
`_mismo_sismo_ya_publicado()` (el mecanismo dedicado a detectar el mismo
sismo bajo otra ubicación, corregido hoy mismo a las 16:15 UTC para el
caso de MISMA magnitud/mención cruzada en ESTADOS distintos) tenía un
`continue` explícito que SALTABA la comparación precisamente cuando
`otra_ubicacion == evento["ubicacion"]` -- es decir, el caso del MISMO
estado, el único donde `_clave_evento()` podía producir una clave
distinta por la magnitud, quedaba sin cubrir. Y como `sismo` está
excluido de la ventana de "mismo evento" de `_resolver_clave()` (ver
`TIPOS_SIN_VENTANA_MISMO_EVENTO`), tampoco había ningún otro mecanismo de
respaldo que lo detectara.

**Corrección**: en `_mismo_sismo_ya_publicado()` (`scripts/state.py`), el
caso `otra_ubicacion == evento["ubicacion"]` ahora retorna `True`
directamente (mismo estado, mismo día calendario, tipo sismo → se
descarta como duplicado) en vez de `continue` -- sin importar si la
magnitud coincide o no. Se verificó que esto no afecta el caso de dos
sismos genuinamente distintos el mismo día en estados DISTINTOS (ese
camino sigue exigiendo magnitud coincidente o mención cruzada explícita,
sin cambios).

**Corrección retroactiva**: se eliminó por completo
`sismo::Zulia::2026-08-10::mag6.6` de `docs/data/noticias.json`, `data/
historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl` y `data/
publicados.json`. `sismo::Zulia::2026-08-10::mag7.4` (la versión
canónica, ya corregida a las 16:15 UTC) no se tocó. Se regeneró
`docs/data/estadisticas.json`.

### Revisado sin cambios

`vialidad::Barinas::2026-08-09` (motorizado fallecido en colisión
múltiple, severidad crítico): consistente con el texto de la fuente.
`infraestructura_electrica::Miranda::2026-08-10` e
`infraestructura_electrica::Distrito Capital::2026-08-10` (misma tormenta
del 09/10-08, dos estados realmente afectados con evidencia propia de
ubicación en cada uno -- Altos Mirandinos/Los Salias para Miranda, Los
Chaguaramos/parroquia San Pedro para Distrito Capital): no son
duplicados entre sí, cada uno tiene evidencia textual propia de su
estado. `inundacion::Aragua::2026-08-10` (Las Tejerías, onda tropical):
consistente. `orden_publico::Distrito Capital::2026-08-10` (El Pitazo,
concentración de simpatizantes frente a la residencia de Perkins Rocha
exigiendo su libertad, sin indicios de disturbios/heridos/detenidos en el
texto): mismo patrón ya documentado como "Pendiente de discutir" en las
sesiones del 02-08, 05-08 y 08-08-2026 (concentración/gremial sin
evidencia de disrupción, sin marcador explícito de que fue pacífica) --
no se corrigió nada, mismo riesgo ya explicado en esas entradas (diseñar
un filtro para este patrón arriesga perder coberturas legítimas de
disturbios reales en su fase inicial).

### Pruebas

2 casos nuevos en `tests/test_state.py`: el caso real de Zulia (mismo
sismo, mismo estado, magnitud revisada de 7.4 a 6.6 preliminar → la
segunda alerta se descarta) y un control de que un sismo distinto (otra
magnitud) en un estado DISTINTO el mismo día sigue contando como alerta
nueva. `python3 -m pytest tests/` → 230 passed, 5 xfailed (conocidos, sin
relación), 1 xpassed (conocido, sin efecto real). `python3
scripts/validar_configs.py` → OK.

---

## Auditoría diaria automática (11-08-2026): un sismo real en Colombia (mag 7.4, 10-08-2026) generó 5 alertas falsas en Venezuela por 4 causas raíz distintas, incluyendo un bug de truncamiento RSS que ocultaba texto clave en el 28% del corpus histórico

Auditoría de rutina de las alertas publicadas/actualizadas desde la
auditoría del 10-08-2026 (`sismo::Zulia::2026-08-10::mag7.4`, ya corregido
ese día). Se encontraron y corrigieron 4 causas raíz distintas, todas
relacionadas con la cobertura mediática del mismo terremoto real ocurrido
en Colombia (magnitud 7.4, epicentro en San José del Palmar/Risaralda, 10
de agosto), con 5 alertas retractadas por completo.

### 1. `_TRUNCADO_RE` (fetch_rss.py) nunca reconocía el patrón de truncamiento "[…]" (corchetes + carácter único de elipsis) -- 33 de 118 fuentes históricas (28%) nunca obtuvieron su texto completo

El regex original (`r"(…|\[\s*\.\.\.\s*\]|\.\.\.\s*$)\s*$"`) solo cubre
"…" sola (sin corchetes) o "[...]" (tres puntos literales dentro de
corchetes) -- ninguna de las dos coincide con "[…]" (corchetes
envolviendo el carácter Unicode de elipsis único), una plantilla de
truncamiento muy común en WordPress. Esto significaba que
`_obtener_texto_completo()` nunca se disparaba para estas fuentes, y el
clasificador solo veía el resumen truncado del RSS, sin los detalles
clave que a veces solo aparecen más adelante en el artículo completo. Se
verificó contra las 118 fuentes de `data/historico_fuentes_texto.jsonl`
que 33 (28%) terminan en este patrón exacto sin haber obtenido nunca su
texto completo -- una fracción sustancial del corpus, aunque solo se
confirmó impacto real en el hallazgo 2 de abajo.

**Corrección**: `_TRUNCADO_RE` ahora también reconoce `\[\s*(?:\.\.\.|…)\s*\]`
(corchetes con tres puntos O el carácter de elipsis), además de los dos
patrones ya cubiertos.

### 2. Dos artículos sobre venezolanos residentes EN COLOMBIA que "recuerdan el desastre de La Guaira" (comparación con un sismo local de hace casi 2 meses) generaban 2 alertas falsas de sismo en el estado La Guaira, y un tercero sobre la misma comparación generaba una alerta falsa de deslizamiento

`sismo::La Guaira::2026-08-10` (confirmado, crítico, El Impulso + El
Carabobeño) y `sismo::La Guaira::2026-08-11` (El Carabobeño) citan
artículos titulados "Venezolanos en Colombia sobreviven al terremoto y
recuerdan el desastre de La Guaira: «Me removió todo»" -- el terremoto
descrito es 100% extranjero ("el terremoto que azotó al sur del país [Colombia]
y deja al menos 71 muertos", "Pereira, Cali, Manizales, Quibdó y Armenia
concentran las situaciones más críticas"). La ÚNICA mención de "La
Guaira" en ambos artículos es la comparación retrospectiva del titular,
no evidencia de que el sismo de hoy haya ocurrido en Venezuela.

Un tercer artículo del mismo día (`deslizamiento::La Guaira::2026-08-11`,
Runrun.es, "Rodríguez ofrece rescatistas a Colombia mientras en La Guaira
buscan personas bajo los escombros") generaba una alerta falsa de
deslizamiento con el mismo patrón, pero más sutil: el resumen RSS
almacenado terminaba truncado en "…que sufrió el vecino país la mañana
de este lunes, […]" (el bug del hallazgo 1) -- se verificó el artículo
completo (vía fetch directo) y confirma que "buscan personas bajo los
escombros… en La Guaira" se refiere explícitamente a labores de rescate
"a casi dos meses del doble terremoto" de La Guaira/Vargas (el sismo
local ya cubierto y ya sujeto a los filtros de retrospectiva de
`verify_ai.py`, ver 05-08 y 08-08-2026) -- no a un derrumbe nuevo de hoy,
y mucho menos relacionado con el sismo de Colombia mencionado en la misma
oración solo como motivo de la oferta de ayuda humanitaria de Delcy
Rodríguez.

**Causa raíz (dos síntomas relacionados)**:

1. Ninguna frase de comparación retrospectiva ("recuerdan el desastre
   de X") estaba en `LISTA_NEGRA_POR_ESTADO` para La Guaira.
2. El filtro determinista de retrospectiva (`_PATRON_RETROSPECTIVA`,
   `verify_ai.py`) exige que el número siga inmediatamente a "a"/"al
   cumplirse" -- "a **casi** dos meses del doble terremoto" no
   coincidía porque "casi" se interpone. Además, la variante "doble
   terremoto" (usada por Runrun.es) no estaba cubierta, solo "doble
   sismo"/"doblete sísmico". Este segundo bug solo se pudo confirmar
   porque el fix del hallazgo 1 permite ahora obtener el texto completo
   del artículo de Runrun.es en corridas futuras.

**Corrección**:

1. Nueva entrada `LISTA_NEGRA_POR_ESTADO["La Guaira"]` (`scripts/classify.py`):
   `"desastre de la guaira"`, `"tragedia de la guaira"`, `"desastre de
   vargas"`, `"tragedia de vargas"` -- se verificó contra el corpus
   completo que estas frases son exclusivas de los 2 artículos
   retractados (3 instantáneas).
2. `_PATRON_RETROSPECTIVA` (`scripts/verify_ai.py`) ahora acepta un
   calificador opcional (`"casi"`, `"cerca de"`, `"alrededor de"`) entre
   "a"/"al cumplirse" y el número, y se agregó `"doble terremoto"`/
   `"terremoto doble"` junto a las variantes de "sismo" ya cubiertas.

**Corrección retroactiva**: se eliminaron por completo
`sismo::La Guaira::2026-08-10`, `sismo::La Guaira::2026-08-11` y
`deslizamiento::La Guaira::2026-08-11` de `docs/data/noticias.json`,
`data/historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl` y
`data/publicados.json`. Se regeneró `docs/data/estadisticas.json`.

### 3. Dos venezolanos migrantes fallecidos en Pereira, Colombia (colapso de vivienda por el mismo terremoto) generaban una alerta de sismo CRÍTICO en Táchira, su pueblo natal -- no el lugar del hecho

`sismo::Tachira::2026-08-11` (Nuevo Día de Falcón + El Periódico de
Monagas, municipio Pedro María Ureña, severidad crítico) describe a "una
pareja de venezolanos oriunda del municipio Pedro María Ureña, en el
estado Táchira" que "perdieron la vida en Pereira, Colombia" cuando "la
vivienda donde habitaban colapsara a causa de un fuerte terremoto
registrado en el departamento de Risaralda" -- el hecho (colapso,
fallecimiento) ocurrió enteramente en Colombia; Táchira solo identifica
el pueblo natal de las víctimas, mencionado porque residían allí antes de
emigrar. El mecanismo ya existente para eventos extranjeros
(`_es_evento_extranjero_sin_municipio`, ver 01-08-2026) no cubre este
caso porque exige la AUSENCIA de un municipio venezolano detectado -- aquí
sí se detecta un municipio real (Pedro María Ureña), solo que es el
origen de las víctimas, no la ubicación del hecho, y Pereira/Risaralda no
están en `FRONTERA_EXTRANJERA_POR_ESTADO["Tachira"]` (ese mecanismo cubre
municipios fronterizos como Cúcuta, no ciudades del interior de Colombia).

**Corrección**: nueva función `_es_fallecimiento_migrante_en_extranjero()`
(`scripts/classify.py`): si el texto contiene "oriundo/a de(l)"/"natural
de(l)" y, dentro de una ventana de 300 caracteres después, tanto un verbo
de fallecimiento ("murió", "fallecieron", "perdieron la vida"...) como la
palabra "Colombia", se descarta la ubicación para ese ítem -- se verificó
contra el corpus completo que esta combinación es exclusiva de las 2
fuentes de este hallazgo.

**Corrección retroactiva**: se eliminó por completo
`sismo::Tachira::2026-08-11` de `docs/data/noticias.json`, `data/
historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl` y `data/
publicados.json`.

### 4. El mismo sismo de Zulia (mag 7.4, 10-08-2026) se publicó una TERCERA vez un día después porque `_mismo_sismo_ya_publicado()` exigía el mismo día calendario exacto

`sismo::Zulia::2026-08-11::mag7.4` (Notiapure, "Habitantes de Maracaibo
evacuaron preventivamente edificios tras sismo en Colombia", PASADO_POR_
FALLA_TECNICA) describe el mismo sismo de magnitud 7.4 ya publicado el
día anterior como `sismo::Zulia::2026-08-10::mag7.4` ("el sismo de
magnitud 7.4 que sacudió Colombia **este lunes**" -- el artículo es del
martes 11, reaccionando un día después). Mismo estado, misma magnitud,
mismo sismo real -- pero como la fuente de Notiapure se publicó al día
calendario siguiente, `_mismo_sismo_ya_publicado()` (corregida el
10-08-2026 para el caso de mismo día) no lo detectaba: comparaba
`partes[2] != fecha_dia` de forma exacta, sin tolerancia de días.

**Corrección**: `_mismo_sismo_ya_publicado()` (`scripts/state.py`) ahora
tolera +/-1 día calendario entre el evento nuevo y cualquier entrada
previa de tipo sismo en `publicados`, en vez de exigir el día exacto. Se
verificó que un sismo genuinamente distinto en el mismo estado, separado
por más de 1 día, sigue contando como alerta nueva (ver test de control).

**Corrección retroactiva**: se eliminó por completo
`sismo::Zulia::2026-08-11::mag7.4` de `docs/data/noticias.json`, `data/
historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl` y `data/
publicados.json`. `sismo::Zulia::2026-08-10::mag7.4` (la versión
canónica) no se tocó. Se regeneró `docs/data/estadisticas.json`.

### Revisado sin cambios

`orden_publico::Anzoategui::2026-08-10` (El Tiempo de Anzoátegui,
protesta pacífica en Cantaura por falta de agua, sin evidencia de
disrupción): mismo patrón ya documentado como "Pendiente de discutir" en
sesiones anteriores (02-08, 05-08, 08-08, 10-08-2026) -- no se corrigió
nada, mismo riesgo ya explicado en esas entradas.
`infraestructura_electrica::Anzoategui::2026-08-11` (Noticias de Aquí,
cierre de autopista en Boca de Uchire por fallas eléctricas): consistente
con el texto de la fuente, sin indicios de error.

### Informes narrativos: 3 fuentes nuevas quedan con referencias a las 3 fuentes retractadas del hallazgo 2

`docs/data/informes/2026-08_general.json`, `2026-08_sismo.json` y
`2026-08_deslizamiento.json` listan las 3 fuentes de La Guaira retractadas
hoy (El Carabobeño, El Impulso de Lara, Runrun.es). Mismo caso que
sesiones anteriores: `GROQ_API_KEY` no disponible en este entorno;
`scripts/build_informes.py` regenerará los informes afectados en la
próxima corrida de producción. Confirmado con
`scripts/detectar_inconsistencias.py` (9 fuentes muertas en 6 informes: 6
ya conocidas de sesiones anteriores + 3 nuevas de esta sesión).

### Pruebas

11 casos nuevos: 4 en `tests/casos_clasificacion.jsonl` (el caso real de
"desastre de la guaira" + control de inundación real en La Guaira sin esa
frase; el caso real del migrante fallecido en Colombia + control de sismo
real en Táchira sin ese patrón), 4 en `tests/test_verify_ai_filtros.py`
("a casi dos meses" + "doble terremoto" + control del patrón original sin
calificador, ya cubierto antes del cambio), 4 en
`tests/test_fetch_rss_limpieza.py` (el caso real de "[…]" + controles de
que "[...]"/"…" sola/texto no truncado siguen funcionando), 2 en
`tests/test_state.py` (el caso real de Zulia un día después + control de
un sismo distinto muy separado en el tiempo). Regresión completa contra
las 74 fuentes vigentes de `data/historico_fuentes_texto.jsonl` (ya con
las 5 instantáneas retractadas eliminadas): sin cambios inesperados.
`python3 -m pytest tests/` → 244 passed, 5 xfailed (conocidos, sin
relación), 1 xpassed (conocido, sin efecto real). `python3
scripts/validar_configs.py` → OK. `python3
scripts/detectar_inconsistencias.py` → mismos pares de posibles
duplicados que sesiones anteriores (sin relación con estos hallazgos), 9
fuentes muertas en 6 informes (ver arriba).

---

## Auditoría diaria automática (13-08-2026): un mismo artículo generó 2 ubicaciones falsas por procedencia de manifestantes, un titular sensacionalista de "artefacto explosivo" resultó ser un cartucho lacrimógeno, una convocatoria a protesta futura se publicó como corte eléctrico y disturbio ya en curso, y un pie de página legal contaminó un municipio

Auditoría de rutina de las 21 alertas publicadas/actualizadas desde la
auditoría del 11-08-2026 (`sismo::Zulia::2026-08-11::mag7.4`, último
hallazgo corregido ese día). Se encontraron y corrigieron 4 causas raíz
distintas, con 4 alertas retractadas por completo y 1 corregida
retroactivamente (municipio).

### 1. Un artículo sobre jubilados petroleros protestando en Caracas generó 2 alertas falsas de orden público en Falcón y Zulia por procedencia de manifestantes, no por ubicación del hecho

`orden_publico::Falcon::2026-08-11` y `orden_publico::Zulia::2026-08-11`
(El Pitazo, "Jubilados petroleros cumplen segundo día de protesta en La
Campiña") describen una protesta de jubilados petroleros frente a la sede
de Pdvsa La Campiña (Caracas) -- el artículo nunca describe ningún hecho
ocurrido en Falcón ni en Zulia. Ambos estados solo se mencionan como la
PROCEDENCIA de manifestantes presentes en esa protesta: "la presencia de
manifestantes de Oriente, Falcón y Caracas" (día 1, ya pasado) y
"jubilados petroleros de Zulia" cuyo autobús fue retenido por la Guardia
Nacional "en peaje de Tazón" en su vía de regreso a Zulia.

**Causa raíz**: `detectar_ubicacion()`/`_ventana_cerca()` (`scripts/
classify.py`) confirman un estado como ubicación del hecho si hay una
palabra clave de tipo (aquí "manifestantes"/"protesta") dentro de la
ventana de proximidad, sin distinguir si esa palabra describe un hecho
ocurriendo EN ese estado o solo identifica el origen/gentilicio de
personas presentes en un hecho que ocurre en otro lugar.

**Corrección**: nuevas entradas `LISTA_NEGRA_POR_ESTADO["Falcon"]` y
`["Zulia"]` (`scripts/classify.py`) con las frases literales exactas de
procedencia de este artículo ("manifestantes de oriente, falcon y
caracas", "jubilados petroleros de zulia en peaje de tazon"). Se verificó
contra las 94 fuentes de `data/historico_fuentes_texto.jsonl` que ambas
frases son exclusivas de este artículo (2 instantáneas).

**Corrección retroactiva**: se eliminaron por completo
`orden_publico::Falcon::2026-08-11` y `orden_publico::Zulia::2026-08-11`
de `docs/data/noticias.json`, `data/historico_eventos.jsonl`, `data/
historico_fuentes_texto.jsonl` y `data/publicados.json`.

### 2. Un titular de "artefacto explosivo en centro comercial" resultó ser, según el propio texto, un cartucho lacrimógeno sin víctimas

`explosion::Miranda::2026-08-12` (El Periódico de Monagas, "Artefacto
explosivo en centro comercial de Baruta") se publicó con tipo=explosion
por la palabra clave "artefacto explosivo" del titular, pero el cuerpo
del artículo aclara varios párrafos después que "se registró la
activación de un cartucho lacrimógeno dentro del establecimiento", que
"el incidente fue totalmente controlado" y que "no se reportaron personas
afectadas durante el suceso". Un cartucho lacrimógeno no es un explosivo
real.

**Causa raíz**: la aclaración ("cartucho lacrimógeno") está fuera de la
ventana de proximidad a la ubicación (35 palabras), así que
`_CONTEXTO_CONFLICTIVO_POR_TIPO` (que solo mira esa ventana) no la
detecta -- mismo patrón ya resuelto antes para boletines de salud sin
alarma, manifestaciones pacíficas y anuncios de Corpoelec sin falla real,
todos evaluados sobre el ARTÍCULO COMPLETO en vez de la ventana.

**Corrección**: nueva función `_es_cartucho_lacrimogeno_sin_explosivo_real()`
(`scripts/classify.py`), evaluada sobre el texto completo igual que las
anteriores: si el texto menciona "cartucho(s) lacrimógeno(s)" y no hay
evidencia fuerte de explosión real (heridos, fallecidos, explosión
accidental...), se descarta el tipo=explosion para ese artículo. Se
verificó contra el corpus completo que la frase es exclusiva de este
artículo, y que un caso de control con explosión real y heridos (sin
mención de cartucho lacrimógeno) sigue clasificando correctamente.

**Corrección retroactiva**: se eliminó por completo
`explosion::Miranda::2026-08-12` de `docs/data/noticias.json`, `data/
historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl` y `data/
publicados.json` (el artículo no genera ningún otro tipo válido).

### 3. La adhesión de un dirigente político a una protesta FUTURA convocada por apagones nacionales se publicó como corte eléctrico Y disturbio ya en curso en Bolívar (PASADO_POR_FALLA_TECNICA)

`infraestructura_electrica::Bolivar::2026-08-12` (El Impulso de Lara,
"Andrés Velásquez se suma llamado a manifestar este viernes por apagones
y elecciones presidenciales") describe únicamente que "el exgobernador
del estado Bolívar... ha expresado su respaldo a la 'Gran Protesta
Nacional' convocada en rechazo a los constantes cortes eléctricos que
afectan a Venezuela" -- ningún corte eléctrico ni disturbio ocurriendo en
Bolívar en particular, solo la adhesión de un dirigente a una protesta
CONVOCADA para el viernes siguiente (todavía no ocurrida). "Bolívar" solo
identifica el cargo político PASADO del dirigente citado, no la ubicación
de ningún hecho.

**Causa raíz**: `detectar_tipo()` disparaba tanto tipo=infraestructura_
electrica (por "apagones") como tipo=orden_publico (por "manifestar"/
"protesta"), y en ambos casos "apagones" también aparece en
`_EVIDENCIA_FUERTE_POR_TIPO["infraestructura_electrica"]` -- ahí es la
RAZÓN citada del llamado a protestar, no evidencia de un corte real en
curso, así que ningún mecanismo existente lo distinguía.

**Corrección**: nueva función
`_es_convocatoria_protesta_futura_sin_hecho_actual()` (`scripts/
classify.py`), evaluada sobre el artículo completo (como
`_es_articulo_retrospectivo_larga_duracion`, aplicada a CUALQUIER tipo):
si el texto contiene un marcador de convocatoria a protesta futura
("llamado a manifestar", "gran protesta nacional") y no hay evidencia
fuerte de un corte eléctrico o disturbio YA en curso (usando una lista
propia de evidencia fuerte que excluye deliberadamente "apagón"/
"apagones", ya que esa es precisamente la palabra ambigua a descartar
aquí), se descartan TODOS los tipos para ese artículo. Se verificó contra
el corpus completo que ambas frases son exclusivas de este artículo, y
con 2 casos de control (un apagón real con "sin luz" en Bolívar, y el
caso ya cubierto de manifestación pacífica) que la evidencia fuerte real
sigue funcionando.

**Corrección retroactiva**: se eliminó por completo
`infraestructura_electrica::Bolivar::2026-08-12` de `docs/data/
noticias.json`, `data/historico_eventos.jsonl`, `data/
historico_fuentes_texto.jsonl` y `data/publicados.json`.

### 4. El pie de página legal de un medio ("Editorial Torbes CA J-070059680") se coló como municipio real de Táchira

`infraestructura_electrica::Tachira::2026-08-12` (Diario La Nación
Táchira, "Cámara de Licoreros denuncia crisis eléctrica") se publicó con
`municipio: "Torbes"`, pero el texto nunca describe ningún hecho en ese
municipio -- CALITA "emitió un pronunciamiento en San Cristóbal" sobre una
crisis que afecta, según el propio texto, "los 29 municipios de la
entidad andina" por igual. La única mención de "Torbes" en todo el texto
es "Editorial Torbes CA J-070059680" -- el nombre legal de la empresa
editora del medio (Diario La Nación) junto a su RIF, en el pie de
página/menú del sitio, que quedó pegado al cuerpo del artículo.

**Causa raíz**: `_obtener_texto_completo()` (`scripts/fetch_rss.py`) cae
al documento HTML completo (todos los `<p>`) cuando no encuentra un
`<article>`/`div.content` reconocible, arrastrando pie de página y menú de
navegación del sitio -- mismo problema de fondo ya resuelto antes para
"Lea también:"/"También puedes leer:"/pie de página de WordPress, pero
para una plantilla de pie legal distinta ("Editorial NOMBRE CA J-RIF") no
cubierta hasta ahora. `_buscar_municipio_directo()` no exige la palabra
"municipio" delante de un nombre único a nivel nacional, así que "Torbes"
suelto bastó como evidencia directa.

**Corrección**: nuevo regex `_PIE_LEGAL_EDITORIAL_RE` (`scripts/
fetch_rss.py`, wireado en `_limpiar_texto()`) que recorta desde "Editorial
NOMBRE C.A. J-RIF" hasta el final del texto -- mismo mecanismo que
`_BOILERPLATE_RE`/`_ARTICULOS_RELACIONADOS_RE`. Con el pie legal fuera,
`detectar_municipio_parroquia()` ahora encuentra correctamente "San
Cristóbal" (mencionado explícitamente en el texto real) en vez de
"Torbes".

**Corrección retroactiva**: se corrigió `municipio` de "Torbes" a "San
Cristóbal" en `docs/data/noticias.json` (título y texto del mensaje
incluidos), `data/historico_eventos.jsonl` y `data/publicados.json`. La
misma fuente (`lanacionweb.com`) también generó, ese mismo día, la fuente
única de `infraestructura_electrica::Barinas::2026-08-12` (máquinas de
diálisis del Hospital Razetti) -- se verificó que ese ítem no se vio
afectado porque "Torbes" no es un municipio válido de Barinas.

### Revisado sin cambios

`orden_publico::Anzoategui::2026-08-10` e `infraestructura_electrica::
Anzoategui::2026-08-11`: ya revisados en la auditoría del 11-08-2026 (ver
esa entrada), sin cambios desde entonces. `salud_publica::Lara::2026-08-12`
(OVP denuncia 3 reclusos fallecidos en Carabobo/Miranda/Lara por
custodia estatal, severidad crítica en Lara): consistente con el texto --
"Adrián Felipe" falleció en el Centro Penitenciario Fénix Lara por
deshidratación severa; el hecho de que el mismo artículo no haya generado
alertas equivalentes para Carabobo/Miranda (la evidencia de tipo cae fuera
de la ventana de proximidad de esos estados) es una limitación de
cobertura ya conocida, no una ubicación falsa. `infraestructura_electrica::
Yaracuy::2026-08-11`, `salud_publica::Monagas::2026-08-11` (brote de
dengue en San Félix de Cantalicio, municipio Cedeño), `orden_publico::
Nueva Esparta::2026-08-11`, `orden_publico::Distrito Capital::2026-08-12`
(2 fuentes, protesta de la Coalición Sindical frente al hotel Meliá),
`infraestructura_electrica::Barinas/Carabobo/Distrito Capital/Zulia/
Lara::2026-08-12` (bajón eléctrico multiestado con evidencia propia por
estado: "Valencia, estado Carabobo", "Los Palos Grandes, El Valle y
Miraflores" en Caracas, "Lara y Zulia"), `inundacion::Apure::2026-08-11`
(desbordamiento del río Arauca, parroquia Urdaneta), `orden_publico::
Apure::2026-08-12` (familiares de militares detenidos, San Fernando) y
`sismo::Lara::2026-08-13` (3 sismos menores sin afectaciones, según el
propio texto): todos consistentes con el texto de sus fuentes.

`infraestructura_electrica::Aragua::2026-08-13` (Credicard, fallas en
pagos con tarjeta de débito por fluctuación eléctrica, con Aragua
mencionado solo dentro de una lista genérica de 9 estados "entre otros"
que "denuncian que Corpoelec aumentó el racionamiento"): la ubicación SÍ
está respaldada textualmente (habitantes de Aragua sí denuncian
racionamiento), pero es una mención de tendencia genérica compartida por
9 estados, no un hecho puntual del día -- de los 9, solo Aragua y Lara
caen dentro de la ventana de proximidad de 35 palabras al verbo
"denuncian", una atribución algo arbitraria por posición en la lista más
que por relevancia real. **Pendiente de discutir**: no se corrigió (el
texto sí lo respalda, y filtrar "listas de estados afectados" arriesga
perder coberturas legítimas de racionamiento generalizado ya cubiertas
antes), pero se deja documentado como un patrón de evidencia débil que
podría revisarse si se repite.

### Pruebas

10 casos nuevos: 6 en `tests/casos_clasificacion.jsonl` (el caso real de
Falcón/Zulia por procedencia + control de protesta real en Zulia; el caso
real del cartucho lacrimógeno + control de explosión real con heridos; el
caso real de la convocatoria de Bolívar + control de apagón real con "sin
luz"), 2 en `tests/test_fetch_rss_limpieza.py` (el caso real del pie legal
"Editorial Torbes CA" + control de que "Editorial" en otro sentido no se
toca). Regresión completa contra las 90 fuentes vigentes de `data/
historico_fuentes_texto.jsonl` (ya con las 4 instantáneas retractadas
eliminadas): sin cambios inesperados -- las únicas fuentes afectadas por
los fixes son, precisamente, las corregidas en esta sesión. `python3 -m
pytest tests/` → 269 passed, 5 xfailed (conocidos, sin relación), 1
xpassed (conocido, sin efecto real). `python3 scripts/validar_configs.py`
→ OK. `python3 scripts/detectar_inconsistencias.py` → mismos pares de
posibles duplicados que sesiones anteriores más los 4 pares del bajón
eléctrico multiestado del 12-08 (ya revisados arriba, evidencia propia por
estado, no duplicados reales), 10 fuentes muertas en 7 informes (7 ya
conocidas de sesiones anteriores + 3 nuevas de esta sesión: `GROQ_API_KEY`
no disponible en este entorno, `scripts/build_informes.py` regenerará los
informes afectados en la próxima corrida de producción).

## Auditoría diaria automática (14-08-2026): un sismo real de Colombia se publicó como magnitud 7.4 en Barinas, el nombre institucional del SSATV disparó un tsunami en un estado sin costa, y dos avenidas homónimas ("Carabobo", "Vargas") duplicaron fallas eléctricas de Barquisimeto en otros estados

Auditoría de rutina de las 25 alertas publicadas/actualizadas el
14-08-2026 (la mayoría `PASADO_POR_FALLA_TECNICA`, sin verificación de
IA). Se encontraron y corrigieron 7 causas raíz distintas, con 7 alertas
retractadas por completo y 2 corregidas retroactivamente (municipio).

### 1. Un terremoto real de magnitud 7.4 en Cali, Colombia, se publicó como sismo crítico en Barinas porque el estado solo nombra la procedencia de las víctimas

`sismo::Barinas::2026-08-14::mag7.4` (El Tiempo de Anzoátegui, "Confirman
el fallecimiento de familia venezolana por el colapso de edificio en
Cali") describe el hallazgo de los cuerpos de tres venezolanos
"procedentes de Barinas" que quedaron atrapados bajo los escombros del
edificio Vanessa en Cali, "tras el terremoto de magnitud 7,4 registrado
en Colombia el lunes 10 de agosto". El sismo ocurrió enteramente en
Colombia; Barinas es solo el estado de origen de las víctimas.

**Causa raíz**: el patrón ya existente para este tipo de caso
(`_es_fallecimiento_migrante_en_extranjero()`, `scripts/classify.py`,
agregado el 11-08-2026 para un caso casi idéntico) solo reconocía
"oriundo/a de(l)"/"natural de(l)" como frase de procedencia y una lista
fija de verbos de fallecimiento ("murió", "falleció", "perdieron la
vida"...) -- esta fuente usa una redacción distinta ("procedentes de",
"hallados sin vida") que ninguna de las dos listas cubría.

**Corrección**: se amplió `_ORIGEN_MIGRANTE_RE` para incluir
"procedentes?/procedente de(l)" y `_MUERTE_MIGRANTE_EXTRANJERO` para
incluir "hallado(s)/hallada(s) sin vida" y "encontrado(s)/encontrada(s)
sin vida" (`scripts/classify.py`). Se verificó contra las 122 fuentes de
`data/historico_fuentes_texto.jsonl` que ambas frases nuevas son
exclusivas de este artículo, y con un caso de control (desplazados
"procedentes de Barinas" dentro de Venezuela, sin muerte ni Colombia) que
un sismo real sigue publicándose sin problema.

**Corrección retroactiva**: se eliminó por completo
`sismo::Barinas::2026-08-14::mag7.4` de `docs/data/noticias.json`,
`data/historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl` y
`data/publicados.json`.

### 2. El nombre oficial de la división de Funvisis que emite boletines sismicos ("Servicio Sismológico y de Alerta de Tsunami Venezolano") disparó una alerta de tsunami en Táchira, un estado sin costa

`tsunami::Tachira::2026-08-14` (Ciudad MCY, "Funvisis reportó un total de
122 movimientos telúricos registrados en el país durante la última
semana") es un resumen semanal rutinario de sismicidad menor (122 eventos
entre magnitud 1.5 y 4.2), sin ninguna ola ni evacuación costera. La
única mención de "tsunami" en todo el artículo es parte del nombre
oficial de la división de Funvisis que firma el boletín: "el Servicio
Sismológico y de Alerta de Tsunami Venezolano (Ssatv)". Táchira es un
estado sin costa; se mencionaba solo porque un sismo de magnitud 2.8 (sin
relevancia) se registró cerca de La Fría.

**Causa raíz**: "alerta de tsunami" es palabra clave de
`tipo=tsunami` (`config/keywords.yaml`) -- ningún mecanismo existente
distinguía el uso de esa frase como nombre propio de una institución del
uso real (una alerta de tsunami efectivamente emitida).

**Corrección**: nueva función
`_es_nombre_institucional_tsunami_sin_evidencia_real()` (`scripts/
classify.py`), evaluada sobre el ARTÍCULO COMPLETO: si el texto contiene
la frase institucional completa "servicio sismológico y de alerta de
tsunami" y no hay evidencia fuerte de un tsunami real (ola gigante,
maremoto, evacuación costera), se descarta el tipo. Se verificó contra el
corpus completo que la frase institucional es exclusiva de este artículo,
y con un caso de control (una alerta de tsunami real, con "ola gigante" y
evacuación costera, sin la frase institucional) que sigue publicándose
sin problema.

**Corrección retroactiva**: se eliminó por completo
`tsunami::Tachira::2026-08-14` de `docs/data/noticias.json`, `data/
historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl` y `data/
publicados.json`.

### 3. Un artículo sobre la reactivación turística de La Guaira, semanas después del sismo de junio ya cubierto, generó una alerta de sismo nueva como si hubiera ocurrido hoy

`sismo::La Guaira::2026-08-14` (El Impulso, "La Guaira coordina la
reactivación gradual del turismo playero tras los sismos de junio")
describe únicamente la coordinación entre autoridades para reactivar el
turismo playero, "luego de las afectaciones causadas por el evento
sísmico registrado el pasado 24 de junio" -- casi dos meses antes de la
publicación, sin ningún desarrollo sísmico nuevo el día de publicación.

**Causa raíz**: el filtro existente para boletines retrospectivos
(`_es_correccion_epicentro_retrospectiva()`) solo cubre el caso específico
de una entidad "ajustando"/"corrigiendo" un epicentro ya conocido -- no
cubre una referencia genérica a la fecha de un sismo ya ocurrido.

**Corrección**: nueva función `_es_referencia_sismo_fecha_pasada()`
(`scripts/classify.py`), decisiva igual que la corrección de epicentro
(no se anula por evidencia fuerte de sismo, porque esa evidencia describe
el sismo original, no uno nuevo): un regex que busca "sismo"/"sísmico"/
"terremoto" cerca (60 caracteres) de "el pasado", en cualquier orden. Se
verificó con un caso de control (un sismo real reportado el mismo día,
donde "el pasado" aparece en otro sentido -- "el pasado gobernador" --
lejos de cualquier mención de sismo) que un sismo real sigue publicándose
sin problema.

**Corrección retroactiva**: se eliminó por completo `sismo::La
Guaira::2026-08-14` de `docs/data/noticias.json`, `data/
historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl` y `data/
publicados.json`.

### 4. Una nota sobre un comedor de Cáritas para adultos mayores, fundado "en tiempos de la pandemia de Covid-19", disparó una alerta de salud pública sin ninguna emergencia sanitaria real

`salud_publica::Sucre::2026-08-14` (Turimiquire, "Los abuelos de Santa
Rosa en Carúpano cuentan con un espacio Cáritas") describe la
inauguración de una casa parroquial/comedor para adultos mayores en
Carúpano -- una nota de servicio comunitario positiva, sin ningún caso ni
alarma sanitaria. La palabra "pandemia" aparece una sola vez, como
referencia histórica al origen del programa: "una dependencia que nació
en tiempos de la pandemia de Covid-19".

**Causa raíz**: "pandemia" es palabra clave de `tipo=salud_publica`
(`config/keywords.yaml`) sin distinguir su uso como referencia temporal
retrospectiva (muy común en notas de programas sociales fundados durante
2020-2021) de una pandemia activa.

**Corrección**: se amplió `_CONTEXTO_CONFLICTIVO_POR_TIPO["salud_
publica"]` (`scripts/classify.py`) con "tiempos de la pandemia",
"durante la pandemia", "desde la pandemia" y "época de la pandemia" --
mismo mecanismo ya usado para "totalmente controlada"/"prevenir
enfermedades": si aparecen cerca de la ubicación y no hay evidencia
fuerte de una emergencia sanitaria real (brote confirmado, casos
confirmados, declaró emergencia sanitaria, cuarentena, hospitalizados),
se descarta el tipo. Se verificó con un caso de control (una pandemia
activa real, con "declaró emergencia sanitaria" y hospitalizados) que
sigue publicándose sin problema.

**Corrección retroactiva**: se eliminó por completo `salud_publica::
Sucre::2026-08-14` de `docs/data/noticias.json`, `data/
historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl` y `data/
publicados.json`.

### 5. Dos avenidas homónimas de Barquisimeto ("Avenida Carabobo", "Av. Vargas") duplicaron las protestas por cortes eléctricos de Lara como alertas falsas en los estados Carabobo y La Guaira

Dos artículos reales sobre marchas por cortes eléctricos EN BARQUISIMETO
(estado Lara) generaban alertas duplicadas en otros estados porque
mencionan avenidas locales homónimas de esos estados:

- `infraestructura_electrica::Carabobo::2026-08-14` (El Impulso, La
  Prensa de Lara): ambos artículos describen manifestantes marchando
  "por la avenida Carabobo" hasta la sede de Corpoelec en Barquisimeto --
  "Avenida Carabobo" es una vía muy común en ciudades venezolanas, sin
  relación con el estado Carabobo (que el artículo nunca menciona).
- `infraestructura_electrica::La Guaira::2026-08-14` (El Impulso): "con
  rumbo a la sede de Corpoelec en la Av. Vargas con Carrera 24" -- "Av.
  Vargas" es una calle local de Barquisimeto. "Vargas" es alias directo
  del estado La Guaira en `estados.yaml` (su nombre histórico), y el
  único municipio de La Guaira se llama, además, "Vargas" -- una doble
  coincidencia que producía tanto el estado como el municipio falsos.

**Causa raíz**: ningún mecanismo distinguía el nombre de una avenida del
nombre del estado/alias homónimo -- mismo patrón de fondo ya cubierto
antes para "avenida Bolívar" (30-07-2026) y "Carabobo FC" (02-08-2026),
pero "avenida Carabobo" y "avenida/Av. Vargas" no estaban cubiertas.

**Corrección**: se agregaron "avenida carabobo"/"avenidas carabobo"/"av.
carabobo"/"av carabobo" a `LISTA_NEGRA_POR_ESTADO["Carabobo"]`, y
"avenida vargas"/"avenidas vargas"/"av. vargas"/"av vargas" a
`LISTA_NEGRA_POR_ESTADO["La Guaira"]` (`scripts/classify.py`) -- mismo
mecanismo que "avenida bolívar". Se verificó con casos de control (un
corte eléctrico real y explícito en "estado Carabobo"/"estado La Guaira",
sin nombre de avenida) que ambos estados siguen detectándose con
normalidad cuando sí son la ubicación real del hecho.

**Corrección retroactiva**: se eliminó por completo
`infraestructura_electrica::Carabobo::2026-08-14` e `infraestructura_
electrica::La Guaira::2026-08-14` de `docs/data/noticias.json`, `data/
historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl` y `data/
publicados.json`.

### 6. "Municipio Cajigal del estado Sucre" (sin coma) se capturaba como "Cajigal del estado Sucre" completo, que por casualidad terminaba en el nombre de otro municipio real del mismo estado

`infraestructura_electrica::Sucre::2026-08-14` y `orden_publico::
Sucre::2026-08-14` (dos fuentes distintas -- Turimiquire y El Tiempo de
Anzoátegui -- sobre el mismo hecho real: protestas por cortes eléctricos
en Yaguaraparo) se publicaron con `municipio: "Sucre"`, pero ambos
artículos dicen explícitamente "Yaguaraparo, en el municipio Cajigal del
estado Sucre".

**Causa raíz**: `_MUNICIPIO_RE` (`scripts/classify.py`) solo detenía su
captura en puntuación o fin de texto -- sin coma antes de "del estado",
capturaba "Cajigal del estado Sucre" completo en vez de solo "Cajigal".
Ese candidato inválido no calzaba por nombre exacto con ningún municipio
de Sucre, pero SÍ por el mecanismo de sufijo de
`_resolver_con_posible_adjetivo()` (diseñado para "municipio fronterizo
Bolívar", ver auditoría del 09-08-2026), porque "estado Sucre" termina en
"sucre" -- que además es, por coincidencia, el nombre de OTRO municipio
real del mismo estado (el municipio Sucre, sede Cumaná).

**Corrección**: se agregaron "del estado"/"del edo" como delimitadores
adicionales del lookahead de `_MUNICIPIO_RE`, y "del estado"/"del edo"/
"del municipio" al de `_PARROQUIA_RE` (mismo problema potencial), sin
tocar el comportamiento con coma ni el caso ya cubierto de "municipio
fronterizo Bolívar" (`scripts/classify.py`). Se verificó con un caso de
control ("municipio X, estado Y" con coma) que sigue capturando solo el
nombre del municipio.

**Corrección retroactiva**: se corrigió `municipio` de "Sucre" a
"Cajigal" en `docs/data/noticias.json` (título y texto del mensaje
incluidos), `data/historico_eventos.jsonl` y `data/publicados.json`,
para ambos eventos.

### 7. Un párrafo de contexto sobre un incendio DISTINTO y ya resuelto ("un hecho similar ocurrió... en Petare, estado Miranda") duplicó un incendio de Caracas como alerta falsa en Miranda

`incendio::Miranda::2026-08-14` (El Pitazo, "Incendio en avenida Los
Ilustres genera congestión vial hacia Plaza Venezuela") es, en realidad,
el mismo incendio ya publicado correctamente como `incendio::Distrito
Capital::2026-08-14` (municipio Libertador, parroquia San Pedro, vía otra
fuente) -- el propio artículo dice "avenida Los Ilustres, del municipio
Libertador, en Caracas". Al final, agrega un párrafo de contexto sobre un
incendio distinto y ya resuelto: "Un hecho similar ocurrió durante la
noche del pasado 7 de agosto... en el sector El Llanito, en Petare,
estado Miranda" -- ese incendio de hace una semana bastaba para generar
una alerta duplicada en Miranda.

**Causa raíz**: ningún mecanismo distinguía una mención de "Miranda"
dentro de un párrafo de comparación con un hecho distinto y ya resuelto
de una mención real del estado.

**Corrección**: se agregó la frase completa "el llanito, en petare,
estado miranda" a `LISTA_NEGRA_POR_ESTADO["Miranda"]` (`scripts/
classify.py`) -- frase específica y verificada como exclusiva de este
artículo (no la palabra suelta "Petare", que sí es evidencia legítima en
artículos reales sobre hechos actuales en ese municipio). Se verificó con
un caso de control (un incendio real y actual en Petare, estado Miranda,
sin la frase de comparación completa) que sigue publicándose con
normalidad.

**Corrección retroactiva**: se eliminó por completo `incendio::
Miranda::2026-08-14` de `docs/data/noticias.json`, `data/
historico_eventos.jsonl`, `data/historico_fuentes_texto.jsonl` y `data/
publicados.json`.

### Revisado sin cambios

`infraestructura_electrica::Distrito Capital/Lara/Bolivar/Zulia::
2026-08-14`: consistentes con el texto de sus fuentes -- protestas
específicas frente a sedes de Corpoelec (El Marqués en Caracas, Barquisimeto
en Lara), una denuncia formal de PJ Bolívar ante la Defensoría del Pueblo,
y testimonios directos de residentes de Lagunillas/El Danto (Zulia).
`incendio::Nueva Esparta::2026-08-14` (reserva de la laguna en playa La
Caracola, municipio Mariño) y `sequia::Trujillo::2026-08-14` (Fedecámaras
Trujillo, impacto cuantificado de El Niño en la producción agrícola
estadal): consistentes con el texto. `sequia::Guarico::2026-08-14`
(productores de maíz, parroquia El Socorro, entre varias localidades
citadas por nombre con el mismo riesgo): consistente con el texto.

### Pendiente de discutir

**`orden_publico::Distrito Capital::2026-08-14`** (Turimiquire,
presentación de un libro sobre la represión poselectoral de 2024, que
menciona de paso una protesta de familiares de presos políticos frente al
Ministerio Público "un día después" -- es decir, 3 días antes de la
publicación): el hecho real (la protesta) sí ocurrió, pero ya había
terminado varios días antes, y el artículo lo menciona solo como contexto
secundario de la presentación del libro. No se corrigió a ciegas: no está
claro si el sistema debería tratar una protesta de días atrás,
mencionada de pasada en un artículo de otro tema, como un hecho de "hoy"
en Distrito Capital, o si eso merece un filtro general de "protesta ya
finalizada mencionada como contexto". Queda pendiente de decisión.

**`infraestructura_electrica::Anzoategui/Miranda/Nueva Esparta::
2026-08-14`** (Reporte Confidencial, mapa de Primero Justicia con una
lista genérica de 9-12 estados "sometidos a apagones"/"más perjudicados",
sin ningún detalle local específico de esos 3 estados en particular): este
es el mismo patrón de evidencia débil ya documentado como pendiente en la
auditoría del 13-08-2026 (`infraestructura_electrica::Aragua::2026-08-13`)
-- y, tal como se anticipó ahí, se repitió, ahora con 3 estados a la vez
del mismo artículo. El texto sí respalda la ubicación (los estados
aparecen nombrados explícitamente), pero como parte de una lista genérica
compartida por 9-12 estados, no de un hecho puntual verificable para cada
uno. Sigue sin corregirse por el mismo motivo (filtrar "listas de estados
afectados" arriesga perder coberturas legítimas de racionamiento
generalizado), pero dado que ya recurrió como se predijo, se notifica al
usuario para decidir si conviene diseñar un filtro (p.ej. exigir alguna
mención local específica -- un municipio, una cita textual, una denuncia
formal -- además de aparecer en la lista) o dejarlo como está.

### Pruebas

18 casos nuevos en `tests/casos_clasificacion.jsonl` (7 reales + 7
controles de los hallazgos 1-5 y 7, más 2 reales + 1 control del hallazgo
6 -- uno de los reales verifica directamente el campo `municipio`).
Regresión completa contra las 106 fuentes vigentes de `data/
historico_fuentes_texto.jsonl` (ya con las 7 instantáneas retractadas
eliminadas): sin cambios inesperados -- las únicas fuentes afectadas por
los fixes son, precisamente, las corregidas en esta sesión. `python3 -m
pytest tests/` → 306 passed, 5 xfailed (conocidos, sin relación), 1
xpassed (conocido, sin efecto real). `python3 scripts/validar_configs.py`
→ OK. `python3 scripts/build_dashboard.py` → `docs/data/estadisticas.json`
regenerado. `python3 scripts/detectar_inconsistencias.py` → mismos pares
de posibles duplicados y fuentes muertas ya conocidos de sesiones
anteriores, sin novedades en las alertas del 14-08-2026.

## A pedido del usuario (14-08-2026): filtro general contra notas-resumen de terceros (mapas/reclamos de partidos u ONG) que enumeran muchos estados bajo la misma condición genérica, sin evidencia local

Tras la auditoría diaria automática del mismo día (ver entrada anterior),
el usuario planteó una preocupación de diseño sobre uno de los 2
hallazgos dejados pendientes: prefiere que las alertas se generen a
partir de prensa regional/local, no de notas-resumen que narran una
misma situación repartida entre varias entidades a la vez, porque esas
notas-resumen "no suelen ser exactas". Se diseñó y construyó un filtro
general (no un parche puntual) para esta clase de artículo.

### Diseño

El caso concreto (`infraestructura_electrica::Anzoategui/Miranda/Nueva
Esparta::2026-08-14`, ver entrada anterior) proviene de un mapa de
Primero Justicia, difundido por Reporte Confidencial: "difundió una
serie de mapas detallando la incidencia de los cortes eléctricos en los
distintos estados... según el reclamo de Primero Justicia, los estados
Anzoátegui, Apure, Lara... están siendo sometidos a apagones diarios de
entre 5 y 8 horas" -- 12 estados enumerados bajo la misma cifra genérica,
sin ningún detalle local de la mayoría.

La primera versión del filtro (descartar CUALQUIER mención de estado si
el ARTÍCULO COMPLETO contiene alguna de estas frases) rompía un caso real
distinto: "Andrés Velásquez: Apagones se deben a la corrupción..." abre
con una protesta real y puntual ("al menos veinte personas protestó...
a las afueras de la sede de la Corporación Eléctrica Nacional en
Caracas") y solo mucho más adelante, en un párrafo totalmente aparte,
resume el mismo mapa de PJ -- descartar el artículo entero por contener
la frase del mapa en algún lugar habría perdido esa cobertura real de
Distrito Capital.

**Corrección final**: la señal se ancla por PROXIMIDAD a la mención
puntual de cada estado (misma ventana de 35 palabras que ya usa
`_ventana_cerca` para el tipo de emergencia), no a "el artículo contiene
la frase en algún lado". Tres piezas nuevas en `scripts/classify.py`:

1. `_es_articulo_resumen_multiestado_de_terceros()`: el artículo
   completo debe contener un marcador de reclamo/mapa de un tercero
   ("compartió un mapa", "difundió una serie de mapas", "según el
   reclamo de", "entidades más perjudicadas") Y mencionar 5+ estados
   distintos -- un chequeo barato para saber si vale la pena aplicar el
   resto del filtro.
2. `_ventana_cerca_con_posicion()` (nueva variante de `_ventana_cerca`
   que además devuelve la posición de la mención puntual que generó la
   ventana) + `_mencion_cerca_de_marcador()`: la mención de ESE estado en
   particular debe estar a 35 palabras o menos de alguno de los
   marcadores -- si está más lejos (como "Caracas" en el caso de
   Andrés Velásquez, a 176 palabras de la cita del mapa), no se
   considera parte de la lista genérica.
3. `_ventana_sin_evidencia_local_especifica()`: aun estando cerca de un
   marcador, si la ventana SÍ nombra un municipio/parroquia específico
   (p.ej. "comunidades del municipio Libertador de Caracas denuncian
   fallas eléctricas", en el mismo artículo del mapa de PJ), no se
   descarta -- eso ya es evidencia local real, no la mera pertenencia a
   la lista.

Si el primer alias probado de un estado (p.ej. "Caracas") se descarta por
este filtro, se prueban los demás alias del mismo estado (p.ej.
"Distrito Capital") antes de abandonar ese estado por completo -- un
estado con múltiples nombres puede tener evidencia real bajo un alias
distinto al que disparó el descarte.

### Verificación

Contra las 102 fuentes vigentes de `data/historico_fuentes_texto.jsonl`,
solo 3 artículos activan el chequeo de "resumen multiestado" (el mapa de
PJ citado por Reporte Confidencial y por La Prensa de Lara, y el propio
artículo de Andrés Velásquez) -- en los tres casos el resultado final es
el esperado: se descartan las menciones sin evidencia local (Anzoátegui,
Miranda, Nueva Esparta, Apure, Mérida...) y se conserva todo lo que sí
la tiene (Distrito Capital vía "municipio Libertador"; Bolívar vía su
propio párrafo sobre la reactivación de Tocoma, a más de 35 palabras del
mapa). 4 casos nuevos en `tests/casos_clasificacion.jsonl` (el caso real
del mapa de PJ + 3 controles: evidencia local dentro del mismo artículo
del mapa, evidencia local lejos del mapa en otro artículo, y un artículo
sin ningún marcador de tercero).

**Corrección retroactiva**: se eliminaron por completo
`infraestructura_electrica::Anzoategui::2026-08-14`, `infraestructura_
electrica::Miranda::2026-08-14` e `infraestructura_electrica::Nueva
Esparta::2026-08-14` (cada una respaldada únicamente por el mapa de PJ)
de `docs/data/noticias.json`, `data/historico_eventos.jsonl`, `data/
historico_fuentes_texto.jsonl` y `data/publicados.json`.
`infraestructura_electrica::Zulia::2026-08-14` (respaldada además por El
Pitazo con evidencia local real de Maracaibo) se corrigió en vez de
eliminarse: se quitó únicamente la fuente Reporte Confidencial de su
lista de fuentes (`num_fuentes` 2→1, `score` 1.35→0.75 según el peso de
El Pitazo en `config/sources.yaml`), conservando el evento.

`python3 -m pytest tests/` → 306 passed, 5 xfailed (conocidos), 1 xpassed
(conocido). `python3 scripts/validar_configs.py` → OK. `python3
scripts/build_dashboard.py` → `docs/data/estadisticas.json` regenerado.
`python3 scripts/detectar_inconsistencias.py` → sin novedades.

El otro hallazgo pendiente de la auditoría del mismo día (`orden_publico::
Distrito Capital::2026-08-14`, protesta ya finalizada mencionada de paso
en un artículo sobre otro tema) sigue sin corregirse -- el usuario pidió
afinar primero este filtro; ese caso queda para una iteración posterior.
