# Plan de confiabilidad de clasificación: suite de regresión + IA de respaldo

Este documento nace de una pregunta directa del usuario el 30/07/2026: tras
revisar la evolución del sistema (ver `docs/roadmap_evolucion.md`), ¿los
errores que se van encontrando se resuelven eficientemente, o son la misma
debilidad de fondo repitiéndose en formas nuevas?

**Conclusión de esa evaluación** (resumida aquí porque motiva las dos
decisiones de este plan; el análisis completo quedó en la conversación, no
en un archivo): la disciplina de cada corrección es sólida (causa raíz,
prueba, regresión manual, corrección retroactiva, documentación), pero el
*ritmo* de descubrimiento de bugs no baja con los días. La mayoría de los
"errores nuevos" de cada auditoría son manifestaciones nuevas de un puñado
de debilidades estructurales que se repiten:

- **Ambigüedad de nombres de ubicación** (municipio = nombre del propio
  estado, parroquia = nombre del país, apellido de una persona citada =
  nombre de un estado...) — la familia más recurrente, con instancias el
  26/07, 27/07 (varias), 28/07 (varias) y 29/07.
- **Palabra clave de tipo demasiado genérica** ("derrumbe", "escombros",
  "manifestaciones"...) que colisiona con un uso idiomático o un contexto
  no relacionado.
- **Artículo retrospectivo tratado como evento nuevo** (aniversarios,
  boletines de corrección técnica sobre un hecho de hace semanas) — 3
  instancias documentadas, la más reciente el 29/07/2026.

Cuando el sistema atacó la causa **estructural** en vez de un síntoma
puntual (la jerarquía real municipio→parroquia del INE, o el fix de
deduplicación entre corridas), esa familia completa dejó de aparecer. El
resto sigue creciendo lista por lista, filtro por filtro — sostenible hoy,
pero sin techo visible.

Este plan ataca esa brecha con dos mecanismos, complementarios y
desacoplados entre sí:

- **Mecanismo A** (diseño, pendiente de decisión del usuario): un
  proveedor de IA de respaldo, para que la verificación de Groq deje de
  ser el eslabón más frágil del pipeline — la mayoría de los falsos
  positivos de las últimas semanas son casos que la propia IA
  probablemente habría rechazado si hubiera llegado a evaluarlos.
- **Mecanismo B** (implementado en esta sesión, ver más abajo): una suite
  de regresión persistente y ejecutable en CI, que reemplaza la práctica
  actual de re-derivar y re-correr casos de prueba a mano en cada sesión
  de auditoría.

---

## Mecanismo A: proveedor de IA de respaldo — **decidido: no proceder por ahora (30-07-2026)**

**Decisión del usuario**: no implementar este mecanismo mientras la única
vía disponible dependa de una tarjeta de crédito o cuenta personal. Razón
explícita: *"no quiero pagar eso con mi tarjeta de crédito porque si me
voy de la CRV el sistema colapsaría"* — un riesgo de continuidad
organizacional más importante que el problema técnico que este mecanismo
resuelve. Si la disponibilidad de la IA de verificación depende de un
método de pago o una cuenta atada a una persona en particular, el sistema
hereda el mismo punto único de falla que ya tiene con `GROQ_API_KEY` hoy,
solo que duplicado — no lo resuelve.

Esto también descarta, por la misma razón, la opción de "subir de plan en
Groq" (necesita tarjeta igual que cualquier proveedor pago) y matiza la
opción de un segundo proveedor gratuito: aunque el nivel gratuito de
varios proveedores (Gemini incluido) no exige tarjeta, seguiría
dependiendo de una cuenta personal del usuario salvo que se cree bajo una
cuenta institucional de la CRV — no evaluado en esta sesión, y no es
una decisión que corresponda tomar sin que la organización tenga esa
cuenta.

**Queda como diseño de referencia** (secciones de abajo, sin tocar) para
si en el futuro la CRV dispone de una cuenta/método de pago
institucional propio, no personal — en ese caso el diseño técnico ya
está listo para retomarse sin rehacer el análisis.

### Problema que ataca

De las ~47 correcciones documentadas en el roadmap, una fracción
significativa (los casos con `estado_verificacion: PASADO_POR_FALLA_TECNICA`)
comparten la misma causa de fondo, ya señalada explícitamente en el propio
roadmap más de una vez: *"son casos que la IA (Groq) muy probablemente
habría rechazado o corregido de haber podido evaluarlas"*. El problema no
es que los filtros deterministas sean insuficientes — es que **Groq no
está disponible con la frecuencia necesaria** (límite de tasa agotado a
media corrida) y la política actual, tras agotar `MAX_CICLOS_ESPERA_GROQ`
(2 ciclos, ~20-30 min), termina publicando sin confirmar como red de
seguridad.

**Importante — qué NO propone cambiar este mecanismo**: la política de
"publicar sin confirmar tras agotar los reintentos" es una decisión de
diseño ya conversada y acordada con el usuario (preferir publicar sin
confirmar a perder un evento real cuando la IA no está disponible por
tiempo prolongado). Este mecanismo no la revierte — la vuelve necesaria
con mucha menos frecuencia, atacando la causa (disponibilidad de la IA),
no el síntoma (qué hacer cuando falla).

### Diseño propuesto

1. **Abstraer la llamada a "un proveedor de LLM"** en `verify_ai.py` detrás
   de una función `_llamar_llm(prompt, system_prompt)` que hoy solo
   conoce Groq, en vez de que `GROQ_URL`/`GROQ_MODEL` estén hardcodeados
   en el cuerpo de `verificar_evento_con_ia()`.
2. **Lista ordenada de proveedores**, cada uno con su URL/modelo/variable
   de entorno de API key, probados en orden dentro del mismo ciclo de
   reintentos que ya existe (`MAX_REINTENTOS_GROQ`): el proveedor de
   respaldo solo se intenta **después** de agotar los reintentos del
   primario, no en paralelo ni como primera opción — mantiene el costo de
   IA igual que hoy en el caso normal (Groq disponible), y solo lo
   incrementa marginalmente durante una degradación.
3. **Mismo contrato de prompt/respuesta para todos los proveedores**: el
   prompt actual ya pide una respuesta JSON estructurada (veredictos +
   municipio/parroquia inferido); mientras el proveedor de respaldo hable
   un dialecto compatible con la API de OpenAI (la mayoría de los
   proveedores de inferencia lo son, incluyendo el propio Groq), el resto
   del pipeline (`_parsear_veredictos_json`, el chequeo de anclaje
   textual que ya impide que la IA alucine ubicación) no necesita ningún
   cambio — ese chequeo de anclaje es precisamente el motivo por el que
   agregar un segundo proveedor es seguro: ninguno de los dos puede
   inventar un dato que no esté en el texto real, se valide con el modelo
   que se valide.
4. **Nunca reemplaza a Groq como primario**: la variable de entorno del
   proveedor de respaldo es opcional, igual que hoy `GROQ_API_KEY` — si no
   está configurada, el comportamiento es idéntico al actual (reintentos
   de Groq y, si se agotan, la política de retención/publicación ya
   acordada).

### Opciones de proveedor a evaluar (pendiente de decisión del usuario)

No se elige uno en este documento — depende de qué cuenta/API key el
usuario pueda conseguir y de sus propias condiciones de costo/límite de
tasa, información que esta sesión no tiene. Candidatos con API compatible
con el formato de OpenAI (mínimo cambio de código):

| Opción | Ventaja | Riesgo/costo |
|---|---|---|
| Segunda cuenta/API key de Groq | Cero cambio de código más allá de la lista de proveedores | Mismo proveedor: un incidente de disponibilidad de Groq en general afecta a ambas cuentas por igual |
| Otro proveedor de inferencia con capa gratuita (p.ej. Cerebras, OpenRouter, Google AI Studio) | Proveedor distinto → un límite de tasa agotado en Groq no correlaciona con el otro | Cada uno tiene su propio formato de límites/cuotas que hay que probar en la práctica, no solo leer en la documentación |
| Subir de plan en Groq (cuota paga) | Ataca la causa raíz real (falta de cuota) sin sumar un proveedor nuevo que mantener | Es una decisión de costo recurrente, no de código — corresponde al usuario, no a esta sesión |

### Qué falta para implementar (no hecho en esta sesión)

1. Que el usuario elija proveedor (o decida subir de plan en Groq en su
   lugar) y consiga la API key correspondiente.
2. Refactor de `verify_ai.py` descrito arriba (abstracción + lista de
   proveedores).
3. Agregar el secreto nuevo a `.github/workflows/monitor.yml`.
4. Probar el flujo de fallback con la clave primaria deliberadamente
   inválida (simulando agotamiento de cuota), verificando que el segundo
   proveedor responde y el chequeo de anclaje textual se sigue aplicando
   igual sobre su respuesta.

---

## Mecanismo B: suite de regresión persistente (implementado en esta sesión)

### Problema que ataca

Hasta hoy, cada corrección se validaba con un script de Python de un solo
uso, escrito dentro de la sesión de auditoría, que releía
`data/historico_fuentes_texto.jsonl` y comparaba resultados a mano — la
frase *"se corrió una regresión completa contra las N fuentes ya
publicadas, ningún otro evento cambió"* aparece en casi cada entrada del
roadmap desde el 27/07/2026. Funciona, pero:

- No queda nada persistido: la próxima sesión repite el mismo trabajo de
  cero.
- No corre en CI: nada impide que una corrección futura rompa
  silenciosamente un fix de hace semanas, salvo que alguien se acuerde de
  volver a correr la regresión a mano.
- Los ~47 casos reales/de control ya identificados en el roadmap solo
  existen como prosa — no como algo ejecutable.

### Diseño implementado

Carpeta nueva `tests/`, tres piezas:

1. **`tests/casos_clasificacion.jsonl`** — casos curados a mano, uno por
   línea (JSON Lines), **append-only** (nunca se reescribe una línea
   existente, solo se agregan nuevas al final — mismo espíritu que
   `docs/roadmap_evolucion.md`). Cada caso trae:
   - `id`: identificador único y descriptivo.
   - `descripcion`: qué bug/comportamiento protege, en una frase.
   - `origen`: `"real -- <medio>, <fecha>"` si es texto real de una fuente
     ya publicada, o `"sintetico (control)"` si es un caso construido a
     propósito para probar un límite del filtro (ambos estilos ya convivían
     en el roadmap; aquí quedan explícitos).
   - `roadmap`: el título de la sección del roadmap donde se documentó el
     hallazgo, para poder ir a leer el contexto completo.
   - `texto`: el texto exacto a clasificar.
   - `esperado`: lista de aserciones, una por ubicación esperada en el
     resultado de `clasificar_item()` — soporta `tipos` (lista exacta),
     `tipos_incluye` (un tipo debe estar presente, sin exigir que sea la
     lista completa), `relevante` (booleano, resultado de `es_relevante()`),
     `municipio`/`parroquia`/`severidad` (valor exacto).
   - `no_debe_aparecer_ubicacion` (opcional): lista de ubicaciones que **no
     deben aparecer en absoluto** en el resultado — para el caso donde el
     bug era que se detectaba una ubicación que no debía existir (el caso
     de hoy, "Bolívar" por el apellido de un vocero citado).

   Sembrado inicial: los 7 casos reales encontrados y corregidos hoy
   (30/07/2026) más sus 5 controles correspondientes.

2. **`tests/test_classify_regresion_historico.py`** — a diferencia del
   archivo anterior, **no** tiene casos escritos a mano: lee en vivo
   `data/historico_fuentes_texto.jsonl` (el archivo real que ya se usa en
   producción) y genera un caso de prueba por cada fuente de cada evento
   ya publicado, afirmando que su tipo conocido sigue detectándose para su
   ubicación conocida. Esto **automatiza exactamente el paso manual que ya
   se hacía cada sesión** — y crece solo, sin ningún trabajo de migración,
   a medida que el sistema sigue publicando y esta auditoría (u otras
   futuras) van depurando el histórico. Los casos con una limitación ya
   conocida y documentada (hoy: un caso de la fusión de "Barinas-Mérida"
   como corredor, ver comentario en el archivo) se marcan `xfail` en vez de
   ignorarse, para que seguir sin resolverse no rompa la suite pero
   tampoco desaparezca de la vista.

3. **`tests/test_verify_ai_filtros.py`** — prueba directa de los filtros
   deterministas de `verify_ai.py` (vialidad, incendio vehicular,
   deslizamiento-vs-colapso-estructural-viejo, ruido de sismos menores,
   retrospectiva obvia) — son funciones puras de texto, no necesitan mock
   de la API de Groq. Un caso real + su contraparte de control por cada
   filtro ya documentado.

`tests/conftest.py` agrega `scripts/` al `sys.path` (no es un paquete
instalable), para que los tests importen `classify`/`verify_ai`
directamente, igual que ya hacía cada script de validación manual dentro
de una sesión.

**Integración a CI**: `.github/workflows/validar.yml` corre
`python -m pytest tests/ -v` después de `validar_configs.py`, con
`pytest==8.3.4` fijado en `requirements-dev.txt` (dependencia de
desarrollo, no se agrega a `requirements.txt` — el monitoreo en
producción no necesita pytest).

**Estado actual**: 80 pruebas, 79 pasan, 1 `xfail` esperado (limitación
conocida y documentada, no un bug nuevo).

### Cómo se usa hacia adelante

- **Cada corrección de código nueva** (el mismo patrón "causa raíz → fix →
  prueba → regresión → corrección retroactiva → documentación" que ya se
  sigue) agrega su caso real + su control a
  `tests/casos_clasificacion.jsonl`, en vez de (o adicionalmente a)
  describirlo solo en prosa en el roadmap. La prosa del roadmap sigue
  siendo el lugar para el *porqué* y la narrativa de la investigación;
  el archivo de casos es el *qué debe seguir siendo cierto*, ejecutable.
- **`tests/test_classify_regresion_historico.py` no necesita mantenimiento
  manual** — crece con el histórico real automáticamente. Si algún día se
  decide rotar/archivar `data/historico_fuentes_texto.jsonl` (mencionado
  como posibilidad en la sección de analítica histórica del roadmap), esta
  prueba seguirá funcionando sobre lo que quede vigente en ese archivo.
- **Pendiente, no implementado en esta sesión**: portar hacia atrás los
  ~40 casos históricos restantes (anteriores a hoy) que solo existen como
  prosa en `docs/roadmap_evolucion.md`, como `tests/casos_clasificacion.jsonl`
  curados. No es bloqueante — la suite ya protege contra que el histórico
  real (mecanismo de regresión automática) se rompa; migrar la prosa
  histórica a casos curados es trabajo de backfill que se puede hacer
  incrementalmente, sesión por sesión, sin prisa.

### Cómo correrla localmente

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

---

## Próximos pasos

1. **Mecanismo B**: ya en producción (PR #102, fusionado 30-07-2026) — sin
   acción pendiente salvo el backfill incremental de casos históricos (no
   bloqueante).
2. **Mecanismo A**: decidido no proceder por ahora (30-07-2026) — no
   depender de una tarjeta/cuenta personal para la confiabilidad del
   sistema. Sin una cuenta o método de pago institucional de la CRV, no
   hay siguiente paso de código razonable; el diseño queda listo para
   retomarse si esa condición cambia.
