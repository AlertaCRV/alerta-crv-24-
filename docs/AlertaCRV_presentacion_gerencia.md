# AlertaCRV — Sistema de monitoreo automático de emergencias
### Documento de apoyo para presentación a Gerencia de Seguridad y Gestión del Riesgo

---

## 1. Objetivo del sistema

AlertaCRV es una herramienta que **monitorea automáticamente medios de
comunicación venezolanos las 24 horas** para detectar reportes de
emergencias — sismos, incendios, inundaciones, fallas de infraestructura,
disturbios, brotes de salud, entre otros —, verificarlos cruzando varias
fuentes independientes, y publicarlos casi en tiempo real (cada 10
minutos) en un canal de Telegram y en un sitio web.

**No es** un sistema de predicción ni un sensor físico (no mide sismos
como un sismógrafo, no mide caudal de un río). **Es** un sistema de
vigilancia mediática automatizada: convierte cientos de artículos de
prensa dispersos en un flujo único, clasificado y verificado, sin que
nadie tenga que revisar manualmente decenas de portales de noticias todo
el día.

**Propósito humanitario, no operativo (todavía)**: hoy informa al público
y sirve como fuente de referencia. No está conectado a decisiones de
despacho de recursos ni sustituye ningún canal oficial de reporte —
ese es un paso posterior, deliberadamente no dado aún (ver sección 7).

---

## 2. Cómo funciona (en términos simples)

1. **Recolección**: cada 10 minutos, el sistema revisa automáticamente
   decenas de fuentes de noticias venezolanas (RSS de medios nacionales y
   regionales) buscando artículos nuevos.
2. **Clasificación**: cada artículo se analiza buscando palabras y frases
   asociadas a 18 tipos de emergencia distintos, y se le asigna un nivel
   de severidad (crítico, alto, medio, bajo, o "sin clasificar" si no hay
   suficiente evidencia).
3. **Verificación cruzada**: el sistema no publica con una sola fuente
   dudosa. Cada medio tiene un "peso" de confiabilidad (evaluado con una
   metodología documentada — gobernanza institucional, verificabilidad,
   historial de precisión). Un evento se marca como **confirmado** solo
   si la suma de pesos de las fuentes que lo reportan supera un umbral;
   si no, se publica igual pero etiquetado como **sin confirmar**, para
   no ocultar información pero sin fingir una certeza que no existe.
4. **Segunda revisión por IA**: antes de publicar, un modelo de lenguaje
   (IA) revisa cada evento agrupado y evalúa si es plausible como
   emergencia real (filtra, por ejemplo, artículos retrospectivos o
   ambiguos que las reglas por sí solas no distinguen bien).
5. **Publicación**: el evento verificado se redacta con una plantilla fija
   (sin texto generado libremente por IA en lo que se publica) y se envía
   a Telegram y al sitio web.

**Costo operativo: cero.** Corre sobre infraestructura gratuita
(GitHub Actions y GitHub Pages), sin depender de presupuesto para
servidores.

---

## 3. Cómo se construyó (no es "entrenamiento" de un modelo de IA)

Es importante aclarar esto porque suele generar una expectativa
equivocada: **AlertaCRV no es un modelo de inteligencia artificial
entrenado con datos históricos**, del tipo que "aprende" patrones de
forma autónoma. Es un **sistema de reglas explícitas**, construido y
refinado a mano, línea por línea, contra casos reales.

El proceso de construcción fue iterativo:

1. Se definió una lista de palabras y frases por tipo de emergencia
   (ej. "sismo", "temblor", "réplica" → tipo sismo) y por nivel de
   severidad (ej. "fallecido", "hospitalizado" → crítico/alto).
2. Cada vez que el sistema clasificaba mal un caso real (un falso
   positivo o una alerta que quedaba sin clasificar debiendo tenerla), se
   investigaba la causa exacta, se corregía la regla, y **se agregaba
   una prueba automatizada permanente** que verifica que ese caso —y
   otros similares— se sigan clasificando bien en el futuro, aunque el
   sistema siga creciendo.
3. Hoy existe una batería de más de 100 pruebas automáticas que corren
   cada vez que se modifica una palabra clave o una regla, antes de que
   el cambio se aplique — para asegurar que una corrección nueva no
   rompa silenciosamente una corrección anterior.

Esto es una decisión de diseño deliberada, no una limitación por
descuido: un sistema de reglas es **auditable y explicable** ("se
clasificó como crítico porque el texto dice 'X'"), algo que un modelo de
IA de caja negra no ofrece con la misma claridad — un valor central para
un contexto humanitario donde cada alerta debe poder justificarse.

---

## 4. Tipos de emergencia y niveles de severidad

**18 tipos de emergencia** cubiertos hoy: sismo, incendio, inundación,
deslizamiento, falla de infraestructura eléctrica, falla de
infraestructura de agua, vialidad (accidentes/colapso vial), orden
público (disturbios/protestas), salud pública (brotes/epidemias),
tsunami, tormenta eléctrica, derrame petrolero, explosión, sequía,
colapso estructural, crisis migratoria, escasez de combustible, motín
carcelario, y emergencias del sistema Metro de Caracas.

**4 niveles de severidad + "sin clasificar"**:
- **Crítico**: hay evidencia de muertes, desapariciones, o colapso
  total.
- **Alto**: heridos, hospitalizados, evacuados, daños severos.
- **Medio**: daños materiales sin víctimas ni propagación.
- **Bajo**: situación controlada, sin daños relevantes, alertas
  preventivas.
- **Sin clasificar**: el sistema detectó el tipo de emergencia pero el
  texto no trae suficiente información para asignar un nivel de
  severidad — se publica igual, sin inventar un nivel que no está
  respaldado por el texto.

Cada tipo y cada nivel se define por palabras/frases específicas, no
genéricas — por ejemplo, deliberadamente **no** se usa la palabra suelta
"explosión" (colisiona con usos idiomáticos como "explosión de alegría")
sino frases concretas como "explosión de gas" o "artefacto explosivo".
Este nivel de cuidado —evitar palabras ambiguas— es el trabajo central
de calibración del sistema, y sigue en curso.

---

## 5. Confiabilidad: qué tan seguro es lo que publica

Tres mecanismos, en capas, para reducir errores:

1. **Verificación cruzada de fuentes** (sección 2, paso 3): reduce el
   riesgo de publicar un rumor de una sola fuente poco confiable.
2. **Revisión por IA antes de publicar**: una segunda capa de juicio
   semántico que las reglas por sí solas no logran (distinguir, por
   ejemplo, un reportaje sobre una crisis vieja de un hecho nuevo).
3. **Suite de pruebas de regresión**: más de 100 casos reales y de
   control, documentados y ejecutables, que corren automáticamente
   antes de cada cambio.

**Punto de honestidad importante para esta audiencia**: el sistema
documenta públicamente cada error encontrado y cómo se corrigió (hay un
registro interno de más de 40 correcciones desde julio de 2026). Esto no
es evidencia de que el sistema sea poco confiable — es la evidencia de
que **cada error se investiga hasta la causa raíz, se corrige, se prueba,
y no se repite**. Un sistema que no muestra ningún historial de errores
o bien es demasiado nuevo para haberlos encontrado, o no los está
documentando.

---

## 6. Limitaciones — qué el sistema NO hace hoy

Ser explícito aquí es más útil que optimismo. Limitaciones vigentes:

- **No es un sensor**: depende de que un medio de comunicación reporte
  el hecho. Si no hay cobertura de prensa de una zona (ej. Amazonas,
  zona con vacío de medios detectado), el sistema no ve nada, sin
  importar cuán bien clasifique lo que sí le llega.
- **No cubre redes sociales** (X/Twitter) — solo RSS de medios y, de
  forma limitada, Telegram.
- **Puede tener falsos positivos y falsos negativos**, como cualquier
  sistema basado en reglas de texto. Se minimizan activamente, pero no
  se eliminan a cero.
- **Depende de un proveedor externo de IA** (Groq, gratuito) para la
  segunda capa de verificación; si ese servicio no está disponible
  temporalmente, el sistema prioriza no perder un evento real y publica
  sin esa verificación adicional, marcado explícitamente como tal.
- **No mide ni resuelve**: solo detecta el reporte de una emergencia, no
  su evolución ni su cierre (no sabe si una falla eléctrica ya se
  resolvió).
- **No está integrado a ningún flujo operativo de despacho de recursos**
  — es informativo, no una herramienta de decisión operativa (todavía).

---

## 7. Sistemas de alerta similares en el mundo — dónde se ubica AlertaCRV

| Sistema | Qué hace | Diferencia con AlertaCRV |
|---|---|---|
| **GDACS** (ONU + Comisión Europea, desde 2004) | Monitor multi-amenaza (sismos, tsunamis, inundaciones, ciclones) que combina datos de sensores oficiales con análisis de impacto poblacional; notifica por correo/SMS a la comunidad de respuesta a desastres. | Usa datos de sensores científicos directos, no prensa. Es una alerta técnica internacional, no de cobertura mediática local. |
| **Ushahidi** (plataforma abierta, usada en 30+ países) | Mapeo colaborativo de crisis: cualquier persona reporta por SMS, web o redes, y se visualiza en un mapa. Usado en Haití, elecciones, derechos humanos. | Se basa en reportes ciudadanos directos, no en prensa ya publicada — mayor cobertura potencial, pero también mayor riesgo de reportes falsos sin verificación previa. |
| **USGS ShakeAlert** (EE.UU.) | Alerta sísmica temprana basada en sensores físicos, con segundos de anticipación antes de que llegue la sacudida. | Es un sistema de sensores en tiempo real, de un solo tipo de amenaza — no aplicable sin la red de sismógrafos que lo sostiene. |
| **AlertaCRV** | Monitoreo automático de **medios de comunicación ya publicados**, con verificación cruzada entre fuentes y revisión por IA. | Su fortaleza específica: cobertura amplia de **18 tipos de emergencia a la vez**, con costo cero, sin depender de infraestructura de sensores ni de que la ciudadanía reporte activamente. Su límite específico: depende enteramente de que la prensa cubra el hecho. |

**Conclusión honesta para esta audiencia**: AlertaCRV no reemplaza un
sistema de sensores (GDACS, ShakeAlert) ni un canal de reporte ciudadano
directo (Ushahidi) — es un sistema complementario, más liviano, centrado
en **agregación y verificación automática de lo que ya reportan los
medios**, un problema real y no resuelto hoy en Venezuela: no hay una
fuente única, verificada y actualizada de emergencias del país.

---

## 8. Potencial y hoja de ruta (lo que falta para mejorar)

En orden de qué tan alcanzable es cada paso, no de importancia:

1. **Panel público de tendencias históricas** (ya implementado): permite
   ver, por ejemplo, cuántas fallas eléctricas confirmadas tuvo un
   estado en un mes — un dato hoy inexistente de forma sistemática y
   auditable para Venezuela.
2. **Ampliar tipos y afinar palabras clave**: proceso continuo; cada tipo
   nuevo requiere su propio período de calibración contra casos reales
   (el mismo patrón ya aplicado a sismo, vialidad, incendios).
3. **Canal de reporte ciudadano** (no implementado): permitiría cubrir
   zonas sin prensa, tratado como una fuente más dentro del mismo
   pipeline de verificación — el principal riesgo es la moderación de
   reportes anónimos sin historial de confiabilidad.
4. **Proveedor de IA de respaldo** (diseñado, no implementado): reduce la
   dependencia de un solo proveedor gratuito de IA. Pendiente de que la
   organización cuente con una cuenta institucional propia (se descartó
   depender de una tarjeta de crédito personal, por continuidad
   institucional).
5. **Integración operativa directa** (no implementado, mayor
   responsabilidad): conectar el sistema a decisiones reales de
   despacho requeriría una tasa de error aún más baja que la aceptable
   para informar al público — es un paso posterior, no el estado actual.

---

## Guion de charla (puntos clave por sección, no leer textual)

**Apertura (1-2 min)**
- "Vengo a presentar una herramienta que construí para resolver un
  problema concreto: hoy no existe una fuente única y verificada de
  emergencias en Venezuela — solo prensa dispersa que hay que revisar
  manualmente."
- Aclarar de entrada: no es IA "mágica", es un sistema de reglas
  auditable, con una capa de IA como revisor adicional, no como
  autoridad final.

**Al llegar a "cómo funciona" — anticipar la primera objeción**
- Alguien va a preguntar "¿y si la fuente miente o se equivoca?" —
  responder ANTES con la sección 2, paso 3 (verificación cruzada + peso
  de confiabilidad por medio) y la metodología de evaluación de medios
  (documento aparte, citarlo si preguntan detalles).

**Al llegar a limitaciones — no minimizar**
- Nombrar explícitamente el vacío de Amazonas y la dependencia de la
  cobertura de prensa. Es más creíble admitir el límite que dejar que lo
  descubran preguntando.
- Frase sugerida: "Este sistema es tan bueno como la prensa venezolana
  que lo alimenta. Donde no hay prensa, no hay alerta — eso no lo
  resuelve la tecnología, lo resolvería un canal de reporte ciudadano,
  que es un paso futuro, no algo que exista hoy."

**Si preguntan "¿por qué no usar IA para todo, en vez de palabras
clave?"**
- Explicar la decisión de diseño: las reglas son auditables ("se marcó
  crítico porque el texto dice 'fallecido'"); una IA de punta a punta
  sería más difícl de justificar caso por caso ante una auditoría o un
  cuestionamiento externo — importante en un contexto humanitario.

**Si preguntan por comparación con otros países**
- Usar la tabla de la sección 7: no compite con sistemas de sensores
  (GDACS, ShakeAlert) — es un problema distinto (agregación de prensa),
  más cercano en espíritu a Ushahidi pero con fuentes ya establecidas en
  vez de reportes ciudadanos sin verificar.

**Cierre — sin pedir nada concreto (dado el objetivo de hoy)**
- "Hoy vengo a informar y abrir la conversación, no a pedir un recurso
  específico. Quiero su criterio como expertos en riesgo: ¿qué tipo de
  emergencia o qué zona del país les preocupa que hoy no esté bien
  cubierta? Eso definiría el siguiente paso a priorizar."

---

*Documento preparado como apoyo para la presentación. Fuentes técnicas:
`README.md`, `docs/roadmap_evolucion.md`, `docs/plan_confiabilidad_clasificacion.md`
y `docs/metodologia_evaluacion_medios.md` del repositorio del sistema.*
