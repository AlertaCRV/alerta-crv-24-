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
