DIAPOSITIVA 1 — AlertaCRV
=========================

Sistema de monitoreo automático de emergencias en Venezuela.


DIAPOSITIVA 2 — Objetivo
=========================

AlertaCRV revisa medios de comunicación venezolanos las 24 horas y
detecta reportes de emergencias apenas se publican. Cruza varias
fuentes entre sí antes de dar algo por confirmado, y lo publica en
Telegram y en un sitio web para que la información llegue rápido y
verificada, sin que nadie tenga que revisar decenas de portales de
noticias de forma manual.

El sistema informa lo que ya está ocurriendo y ha sido reportado. No
predice ni mide directamente los eventos.


DIAPOSITIVA 3 — Tipos de emergencia y sus palabras clave
==========================================================

Sismo
Sismo, temblor, terremoto, réplica, movimiento telúrico, movimiento
sísmico

Incendio
Incendio, incendio forestal, conato de incendio, llamas, quema,
explosión de gas, fuga de gas, gas licuado, onda expansiva

Inundación
Inundación, desbordamiento, crecida, anegado, vaguada, desborde de
quebrada, desborde de río, viviendas anegadas

Deslizamiento
Deslizamiento, derrumbe, alud, deslave, escombro, desprendimiento de
tierra, desprendimiento de rocas, socavamiento

Falla eléctrica
Apagón, falla eléctrica, colapso eléctrico, tendido eléctrico, corte de
luz, Corpoelec, bajón, subestación eléctrica, transformador explotado

Falla de agua
Falla de agua, corte de agua, sin agua, Hidrocapital, hidrológica

Vialidad
Colapso vial, vía colapsada, accidente vial, choque, colisión,
volcamiento

Orden público
Disturbio, protesta, saqueo, manifestantes, manifestación violenta,
manifestación callejera, marcha de protesta, marcha opositora, hecho
de violencia, tiroteo, barricada, gases lacrimógenos, ola de violencia,
focos de violencia

Salud pública
Brote, epidemia, alerta sanitaria, intoxicación masiva, enfermedad,
pandemia, cuarentena, aislamiento sanitario, emergencia epidemiológica,
alerta epidemiológica, brote epidémico, contagio masivo

Tsunami
Tsunami, maremoto, alerta de tsunami, ola gigante, retiro del mar, tren
de olas

Tormenta eléctrica
Tormenta eléctrica, impacto de rayo, caída de rayo, fulminado por un
rayo, alcanzado por un rayo, descarga eléctrica atmosférica, centella

Derrame petrolero
Derrame petrolero, derrame de petróleo, derrame de crudo, derrame de
hidrocarburos, marea negra, mancha de petróleo, contaminación por
hidrocarburos

Explosión
Explosión industrial, explosión en fábrica, artefacto explosivo, coche
bomba, explosivo detonado, estallido de explosivo, explosión de
tubería, explosión de caldera

Sequía
Sequía, escasez prolongada de agua, desabastecimiento de agua potable,
crisis de agua potable, niveles críticos del embalse, racionamiento de
agua

Colapso estructural
Colapso estructural, colapso de puente, colapso de edificación,
colapso de vivienda, desplome de estructura, desplome de edificación,
desplome de puente

Crisis migratoria
Crisis migratoria, éxodo masivo, desplazamiento masivo, oleada
migratoria, migración masiva, ola migratoria, desplazados, familias
desplazadas

Escasez de combustible
Escasez de combustible, escasez de gasolina, colas de gasolina, crisis
de combustible, desabastecimiento de gasolina

Motín carcelario
Motín carcelario, motín en cárcel, amotinamiento, riña carcelaria, fuga
masiva de reclusos, toma de rehenes en cárcel

Accidente de transporte
Accidente aéreo, caída de avión, avión accidentado, naufragio,
hundimiento de embarcación, accidente marítimo, choque de trenes,
descarrilamiento, accidente de tren

Ataque armado
Guerrilla, paramilitar, atentado, ataque armado, terrorismo, célula
terrorista, grupo armado organizado, masacre

Emergencia del Metro
Metro paralizado, falla en el metro, varados en el metro, atrapados en
el metro, incendio en el metro, colapso del servicio del metro,
descarrilamiento del metro, choque de trenes del metro, teleférico de
Caracas, falla en el teleférico, varados en el teleférico


DIAPOSITIVA 4 — Niveles de severidad y sus palabras clave
============================================================

Crítico
Fallecido, muerto, murió, ahogado, perdió la vida, víctimas fatales,
desaparecidos, colapso total, emergencia nacional, emergencia
regional, asesinado, herida mortal, muerte violenta, cuerpo
carbonizado, cuerpo sin vida, hallado muerto, deceso

Alto
Herido, lesionado, hospitalizado, evacuación, daños severos, alerta
roja, inhalación de monóxido de carbono, intoxicado por humo, desalojo
preventivo, intoxicación por gases tóxicos, damnificado, estado
crítico, unidad de cuidados intensivos, incomunicados

Medio
Daños materiales, alerta naranja, devorado por las llamas, consumido
por las llamas

Bajo
Alerta amarilla, precaución, sin heridos, sin novedad, sin pérdidas
humanas, sin víctimas graves, descartado el brote


DIAPOSITIVA 5 — Confiabilidad: el sistema de score
=====================================================

Cada medio de comunicación tiene un puntaje de confiabilidad, entre 0.5
y 0.9, calculado antes de incorporarlo al sistema.

El puntaje parte de una base de 0.5 y sube según criterios evaluados
para cada medio: si es un organismo oficial o un medio con comité
editorial, si sus notas se respaldan en documentos o citas directas, si
tiene historial libre de bulos o desmentidos públicos, y si sus notas
son precisas en fecha y lugar. Baja si el sitio está saturado de
publicidad agresiva, una señal típica de portales de baja calidad.

Antes de asignar un puntaje se revisa también, en vivo y de forma
técnica, que el medio funcione realmente: que su fuente de noticias
esté activa, que devuelva artículos reales y que el contenido
corresponda a Venezuela.

Cuando varios medios reportan el mismo hecho, sus puntajes se suman.
Solo cuando esa suma supera un umbral definido, el evento se marca
como confirmado. Si no lo alcanza, se publica igual pero identificado
como sin confirmar, para que la información llegue de todas formas con
el nivel de certeza que realmente tiene.

Un medio local recibe además un pequeño bono cuando reporta sobre su
propia zona, porque su cercanía al hecho le da un valor adicional en
ese caso puntual.


DIAPOSITIVA 6 — Limitación principal
=======================================

El sistema depende por completo de que un medio de comunicación
reporte el hecho.

En zonas donde la cobertura de prensa es escasa, como el estado
Amazonas, el sistema puede no registrar emergencias reales que sí
están ocurriendo, simplemente porque nadie las publicó. La calidad de
la clasificación no cambia nada en esos casos: el punto de partida es
siempre lo que un medio decidió cubrir.

Otras limitaciones existen —cobertura de redes sociales, dependencia
de un proveedor externo de inteligencia artificial, ausencia de
seguimiento sobre si una falla ya se resolvió— pero son de menor peso
frente a esta.


DIAPOSITIVA 7 — Hacia dónde puede crecer
===========================================

Panel de tendencias históricas
Con los datos que el sistema ya genera en cada evento, es posible
construir un panel público que muestre la evolución de las emergencias
por estado y por tipo a lo largo del tiempo. Venezuela hoy no cuenta
con una fuente así, sistemática y consultable, para muchos de estos
temas.

Canal de reporte ciudadano
Incorporar un canal donde cualquier persona pueda reportar una
emergencia directamente ampliaría la cobertura hacia zonas donde la
prensa no llega, como Amazonas. Ese reporte pasaría por el mismo
proceso de verificación cruzada que ya aplica a los medios, para
mantener el mismo estándar de confiabilidad.


DIAPOSITIVA 8 — Cierre
=========================

AlertaCRV convierte información dispersa en un flujo único, verificado
y consultable. Es una herramienta informativa hoy, con espacio real
para crecer en cobertura y en profundidad.
