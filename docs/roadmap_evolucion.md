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
