"""Extraccion segura de reportes de filiales de la Cruz Roja adjuntos a
correos institucionales (ver docs/roadmap_evolucion.md, seccion "Acuerdo de
criterios para adjuntos de correo con datos personales sensibles").

Los adjuntos reales observados (.docx/.pptx de filiales) mezclan datos
personales de personas desplazadas -- nombres, cedulas, telefonos,
direcciones exactas, diagnosticos medicos individuales -- con un bloque de
cifras consolidadas (familias/personas por edad y sexo) y, a veces, una
seccion de necesidades. La politica acordada con el usuario es tajante: "De
ninguna manera deben publicarse datos personales. Solo interesa el numero
consolidado por edad y sexo, lugar de procedencia de los desplazados,
condicion general de las personas, y parroquia, municipio y estado donde
estan albergados."

Por eso este modulo NUNCA expone el texto crudo del documento fuera de si
mismo: solo extrae, mediante anclas estrictas (palabras clave especificas +
un numero inmediatamente adyacente), los pares etiqueta/numero de la seccion
de totales, mas la ubicacion (estado/municipio/parroquia, reutilizando la
deteccion de classify.py) y la fecha del documento. Con eso arma un texto
SINTETICO nuevo -- el unico que llega a clasificar_item()/Groq/el sitio
publico -- que nunca contiene un nombre, cedula, telefono o direccion,
porque nunca se copia texto libre del documento original, solo los valores
ya validados. Si no se puede determinar con confianza una ubicacion Y al
menos una cifra consolidada, se descarta el adjunto por completo (fail
closed) en vez de arriesgar publicar datos parciales o mal interpretados.
"""

import io
import re
import zipfile
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from dateutil import parser as dateparser
from pypdf import PdfReader

from classify import _normalizar, detectar_municipio_parroquia
from config_loader import load_estados

ZONA_VENEZUELA = ZoneInfo("America/Caracas")

EXTENSIONES_SOPORTADAS = (".docx", ".pptx", ".pdf")


def _texto_docx(contenido):
    """Extrae el texto de un .docx leyendo directamente el XML del documento
    principal, en vez de usar python-docx -- una muestra real de filial trae
    una imagen incrustada con el CRC roto, que hace que python-docx (y
    cualquier libreria que valide el zip completo) falle con BadZipFile,
    pese a que el propio documento (word/document.xml) es perfectamente
    legible."""
    try:
        with zipfile.ZipFile(io.BytesIO(contenido)) as z:
            xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[WARN] No se pudo leer el .docx adjunto: {e}")
        return None
    texto = re.sub(r"<w:p[ >]", "\n", xml)
    texto = re.sub(r"<w:tab\s*/>", "\t", texto)
    texto = re.sub(r"<[^>]+>", "", texto)
    import html
    texto = html.unescape(texto)
    return re.sub(r"[ \t]+", " ", texto).strip()


def _texto_pptx(contenido):
    try:
        with zipfile.ZipFile(io.BytesIO(contenido)) as z:
            nombres_slides = sorted(
                n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)
            )
            partes = []
            for nombre in nombres_slides:
                xml = z.read(nombre).decode("utf-8", errors="replace")
                texto = re.sub(r"</a:p>", "\n", xml)
                texto = re.sub(r"<[^>]+>", "", texto)
                partes.append(texto)
    except Exception as e:
        print(f"[WARN] No se pudo leer el .pptx adjunto: {e}")
        return None
    import html
    texto = html.unescape("\n".join(partes))
    return re.sub(r"[ \t]+", " ", texto).strip()


def _texto_pdf(contenido):
    try:
        lector = PdfReader(io.BytesIO(contenido))
        paginas = [pagina.extract_text() or "" for pagina in lector.pages]
    except Exception as e:
        print(f"[WARN] No se pudo leer el .pdf adjunto: {e}")
        return None
    texto = "\n".join(paginas).strip()
    return texto or None


def _texto_de_adjunto(nombre_archivo, contenido):
    nombre_norm = (nombre_archivo or "").lower()
    if nombre_norm.endswith(".docx"):
        return _texto_docx(contenido)
    if nombre_norm.endswith(".pptx"):
        return _texto_pptx(contenido)
    if nombre_norm.endswith(".pdf"):
        return _texto_pdf(contenido)
    # .doc/.ppt (formato binario legado) no tienen un parser seguro
    # disponible aqui -- se descartan explicitamente en vez de intentar una
    # extraccion best-effort que podria mezclar bytes binarios con el texto.
    print(f"[WARN] Formato de adjunto no soportado, se omite: {nombre_archivo}")
    return None


_FECHA_DOCUMENTO_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")


def _fecha_documento(texto):
    """Busca una fecha DD/MM/AAAA en los primeros ~300 caracteres del
    documento -- las plantillas de las filiales la traen justo debajo del
    encabezado ("Cruz Roja venezolana / Filial X / 28/07/2026"). Devuelve la
    fecha a mediodia hora Venezuela (convertida a UTC), o None si no se
    encuentra u la fecha no es valida."""
    m = _FECHA_DOCUMENTO_RE.search(texto[:300])
    if not m:
        return None
    try:
        fecha = dateparser.parse(m.group(0), dayfirst=True)
    except (ValueError, OverflowError):
        return None
    fecha = fecha.replace(hour=12, minute=0, second=0, microsecond=0, tzinfo=ZONA_VENEZUELA)
    return fecha.astimezone(timezone.utc)


_FILIAL_RE = re.compile(r"\bfilial\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\s]{1,30}?)(?=[\n.,;:]|$)")


def _nombre_filial(texto):
    m = _FILIAL_RE.search(texto)
    return m.group(1).strip() if m else None


# Etiquetas de la seccion de cifras consolidadas. A proposito solo se usan
# formas PLURALES ("femeninas", "ninos", "adultos mayores"...) -- en las
# muestras reales, la seccion de totales siempre usa el plural ("Masculinos:
# 6", "Adultos mayores: 9"), mientras que las filas individuales de cada
# familia (las que traen datos personales) usan el singular ("Femenina",
# "Adulto mayor de 74 anos"). Esa distincion gramatical es lo que evita que
# la edad de una persona especifica ("33" junto a "Femenina") se confunda
# con una cifra consolidada real.
ETIQUETAS_CONTEO = {
    "numero de familias": "Número de familias",
    "numero de personas": "Número de personas",
    "total de familias": "Total de familias",
    "total del grupo familiar": "Total de personas (grupo familiar)",
    "grupo familiar": "Personas (grupo familiar)",
    "familias": "Familias",
    "personas": "Personas",
    "masculinos": "Masculinos",
    "femeninas": "Femeninas",
    "adultos mayores": "Adultos mayores",
    "adultos": "Adultos",
    "ninos lactantes": "Niños lactantes",
    "ninos": "Niños",
    "ninas": "Niñas",
    "adolescentes": "Adolescentes",
    "mujeres embarazadas": "Mujeres embarazadas",
}
_ETIQUETAS_ALT = "|".join(re.escape(e) for e in sorted(ETIQUETAS_CONTEO, key=len, reverse=True))
# El separador entre etiqueta y numero NO puede cruzar un salto de linea: en
# la plantilla de la filial ("Femeninas: 4"), etiqueta y numero comparten
# linea; permitir "\s*" (que incluye "\n") aqui hacia que, en el formato de
# la plantilla que pone el NUMERO en una linea y la etiqueta en la
# siguiente ("91\nFamilias\n187\ngrupo familiar"), la etiqueta de un campo
# "robara" por error el numero del campo siguiente.
_SEP_MISMA_LINEA = r"[ \t]*:?[ \t]*"
_SEP_LINEA_SIGUIENTE = r"[ \t]*\n?[ \t]*"
_CONTEO_ANTES_RE = re.compile(rf"\b({_ETIQUETAS_ALT})\b{_SEP_MISMA_LINEA}(\d+)\b")
_CONTEO_DESPUES_RE = re.compile(rf"\b(\d+)\b{_SEP_LINEA_SIGUIENTE}({_ETIQUETAS_ALT})\b")


def _extraer_totales(texto_norm):
    """Devuelve un dict {etiqueta_canonica: numero}, buscando SOLO pares
    etiqueta+numero adyacentes (en cualquier orden) -- nunca se copia texto
    libre alrededor, asi que cualquier detalle extra pegado al numero en el
    documento original (p.ej. "1(24 semanas)") queda descartado, no solo
    "oculto"."""
    totales = {}
    for patron in (_CONTEO_ANTES_RE, _CONTEO_DESPUES_RE):
        for m in patron.finditer(texto_norm):
            grupos = m.groups()
            etiqueta, numero = (grupos[0], grupos[1]) if not grupos[0].isdigit() else (grupos[1], grupos[0])
            canonico = ETIQUETAS_CONTEO[etiqueta]
            totales.setdefault(canonico, numero)
    return totales


_NECESIDADES_ANCLA_RE = re.compile(r"necesidades\s+identificadas\s*:?", re.IGNORECASE)
_NECESIDADES_STOP_RE = re.compile(
    r"\b(nota|observacion|observación|punto focal|revisado por|fuente|tel[eé]fono|c[eé]dula)\b",
    re.IGNORECASE,
)
_PATRON_TELEFONO_O_CORREO = re.compile(r"\d{6,}|@")
MAX_LINEAS_NECESIDADES = 12


def _extraer_necesidades(texto):
    m = _NECESIDADES_ANCLA_RE.search(texto)
    if not m:
        return []
    resto = texto[m.end():].splitlines()
    necesidades = []
    blancos_seguidos = 0
    for linea in resto:
        linea = linea.strip(" \t.")
        if not linea:
            blancos_seguidos += 1
            if blancos_seguidos >= 2:
                break
            continue
        blancos_seguidos = 0
        if _NECESIDADES_STOP_RE.search(linea) or _PATRON_TELEFONO_O_CORREO.search(linea):
            break
        necesidades.append(linea)
        if len(necesidades) >= MAX_LINEAS_NECESIDADES:
            break
    return necesidades


_ORIGEN_RE = re.compile(
    r"\b(provenientes?|procedentes?)\s+(?:del?|de la)\s+estado\b", re.IGNORECASE
)
_DESTINO_RE = re.compile(
    r"\b(localizacion|localización|localizados?|ubicados?|albergad\w*|"
    r"acogida|traslad\w*)\b",
    re.IGNORECASE,
)


def _posiciones_estados(texto_norm):
    """Lista de (nombre_estado, posicion) para cada estado con al menos una
    mencion textual, en la posicion de su PRIMERA mencion."""
    resultado = []
    for nombre_estado, alias in load_estados().items():
        candidatos = {_normalizar(a) for a in alias} | {_normalizar(nombre_estado)}
        mejor = None
        for candidato in candidatos:
            m = re.search(r"\b" + re.escape(candidato) + r"\b", texto_norm)
            if m and (mejor is None or m.start() < mejor):
                mejor = m.start()
        if mejor is not None:
            resultado.append((nombre_estado, mejor))
    return sorted(resultado, key=lambda x: x[1])


def _estado_por_municipio(municipio_norm, excluir_estado=None):
    """Busca a que estado pertenece un municipio mencionado por nombre
    (usado cuando el documento no nombra el estado destino explicitamente,
    solo el municipio -- ver caso real: reportes que dicen "municipio
    Colina" sin repetir "estado Falcon"). Solo se acepta si el nombre
    identifica a un unico estado (sin ambiguedad)."""
    from config_loader import load_ubicaciones_detalle
    candidatos = []
    for estado, detalle in load_ubicaciones_detalle().items():
        if estado == excluir_estado:
            continue
        for municipio in detalle.get("municipios", {}):
            if _normalizar(municipio) == municipio_norm:
                candidatos.append(estado)
                break
    return candidatos[0] if len(candidatos) == 1 else None


_MUNICIPIO_MENCION_RE = re.compile(r"municipio\s+([a-záéíóúñ][\wà-ÿ' ]{2,30})", re.IGNORECASE)


def _destino_por_municipio_mencionado(texto, excluir_estado=None):
    """Busca el primer "municipio X" mencionado en el texto que pertenezca,
    sin ambiguedad, a un estado distinto de `excluir_estado`, y devuelve ese
    estado -- fallback para reportes que solo nombran el municipio destino
    sin repetir el nombre del estado (caso real: "casa de acogida... del
    municipio colina", sin mencionar nunca "Falcon" explicitamente)."""
    for m in _MUNICIPIO_MENCION_RE.finditer(texto):
        municipio_norm = _normalizar(m.group(1).strip())
        estado = _estado_por_municipio(municipio_norm, excluir_estado=excluir_estado)
        if estado:
            return estado
    return None


def _origen_y_destino(texto):
    """Devuelve (origen_estado_o_None, destino_estado_o_None). Nunca
    devuelve texto libre del documento -- solo un nombre de estado ya
    validado contra config/estados.yaml (nunca es informacion personal)."""
    texto_norm = _normalizar(texto)
    estados_encontrados = _posiciones_estados(texto_norm)
    m_origen = _ORIGEN_RE.search(texto)
    m_destino = _DESTINO_RE.search(texto)

    if not estados_encontrados:
        return None, None

    if len(estados_encontrados) == 1:
        unico = estados_encontrados[0][0]
        # Si el unico estado mencionado aparece junto a una pista de
        # PROCEDENCIA (y ninguna de destino), es el origen, no el destino
        # -- caso real: un reporte que solo nombra el estado de donde
        # salieron las familias ("provenientes del Estado La Guaira") y
        # nunca nombra el estado destino, solo su municipio.
        if m_origen and not m_destino:
            destino = _destino_por_municipio_mencionado(texto, excluir_estado=unico)
            return unico, destino
        return None, unico

    origen = None
    if m_origen:
        pos_norm = len(_normalizar(texto[:m_origen.end()]))
        origen = min(estados_encontrados, key=lambda e: abs(e[1] - pos_norm))[0]

    restantes = [e for e in estados_encontrados if e[0] != origen]
    if not restantes:
        return origen, None

    destino = None
    if m_destino:
        pos_norm = len(_normalizar(texto[:m_destino.end()]))
        destino = min(restantes, key=lambda e: abs(e[1] - pos_norm))[0]
    else:
        destino = restantes[0][0]

    return origen, destino


def _resolver_ubicacion(texto):
    """Determina la ubicacion destino (donde estan albergadas las
    familias): estado, y municipio/parroquia si se puede determinar con
    certeza (reutilizando la misma logica ya probada de classify.py).
    Devuelve (origen, destino, municipio, parroquia); destino es None si no
    se pudo determinar ninguna ubicacion (el llamador debe descartar el
    adjunto en ese caso)."""
    origen, destino = _origen_y_destino(texto)

    if destino is None:
        # El documento nombra un solo estado y ademas coincide con el que
        # se identifico como "origen" (p.ej. solo aparece el estado de
        # procedencia, sin decir a donde fueron trasladados) -- no hay
        # ubicacion destino segura que publicar.
        return origen, None, None, None

    # Si detectar_municipio_parroquia() no logra determinar el municipio
    # (p.ej. el documento menciona varios municipios distintos sin poder
    # atribuir la cifra consolidada a uno solo), se deja en None: es
    # preferible publicar solo a nivel estado que arriesgar un municipio
    # incorrecto.
    municipio, parroquia = detectar_municipio_parroquia(texto, destino)

    return origen, destino, municipio, parroquia


def extraer_item_filial(nombre_archivo, contenido, fecha_email, remitente_email, message_id):
    """Procesa un adjunto de correo institucional y devuelve un item listo
    para clasificar_item(), o None si el adjunto no trae suficiente
    informacion segura y consolidada (fail closed: nunca se publica a
    partir de un adjunto que no se pudo interpretar con confianza)."""
    texto_crudo = _texto_de_adjunto(nombre_archivo, contenido)
    if not texto_crudo:
        return None

    origen, destino, municipio, parroquia = _resolver_ubicacion(texto_crudo)
    if destino is None:
        print(f"[WARN] Adjunto '{nombre_archivo}': no se pudo determinar la ubicación destino, se descarta")
        return None

    totales = _extraer_totales(_normalizar(texto_crudo))
    if not totales:
        print(f"[WARN] Adjunto '{nombre_archivo}': no se encontró una sección de cifras consolidadas, se descarta")
        return None

    necesidades = _extraer_necesidades(texto_crudo)
    fecha_doc = _fecha_documento(texto_crudo) or fecha_email
    nombre_filial = _nombre_filial(texto_crudo)

    partes_ubicacion_destino = [f"estado {destino}"]
    if municipio:
        partes_ubicacion_destino.insert(0, f"municipio {municipio}")
    if parroquia:
        partes_ubicacion_destino.insert(0, f"parroquia {parroquia}")
    destino_texto = ", ".join(partes_ubicacion_destino)

    totales_texto = "; ".join(f"{etiqueta}: {numero}" for etiqueta, numero in totales.items())

    # Texto sintetico: nunca se copia una sola palabra del documento
    # original salvo nombres de estado/municipio/parroquia (ya validados
    # contra config/estados.yaml) y los pares etiqueta/numero ya
    # extraidos -- es el unico texto que llega a clasificar_item()/Groq, asi
    # que debe ser seguro por construccion, no por filtrado posterior.
    #
    # El orden importa: la palabra clave "personas desplazadas" debe quedar
    # DESPUES de la mencion del estado DESTINO, nunca antes -- classify.py
    # acota la ventana de proximidad de un estado en la mencion del OTRO
    # estado mas cercano, pero esa cota solo protege el lado que va DESPUES
    # de esa mencion. Si la palabra clave apareciera entre el origen y el
    # destino (p.ej. "...estado La Guaira. Reporte de personas desplazadas
    # en estado Falcon"), quedaria dentro de la ventana del origen tambien
    # (su cota derecha es la posicion de "Falcon", que viene DESPUES de la
    # palabra clave) y el origen terminaria generando su propia alerta de
    # crisis migratoria -- bug real detectado al probar con texto
    # sintetico durante el diseño de esta funcion.
    partes_texto = []
    if origen:
        partes_texto.append(
            f"Familias que salieron de su lugar de origen en el estado {origen} "
            f"se encuentran ahora en {destino_texto}, como personas desplazadas."
        )
    else:
        partes_texto.append(
            f"Reporte de personas desplazadas: familias desplazadas albergadas en {destino_texto}."
        )
    partes_texto.append(f"Resumen consolidado: {totales_texto}.")
    if necesidades:
        partes_texto.append("Necesidades identificadas: " + ", ".join(necesidades) + ".")
    texto_sintetico = " ".join(partes_texto)

    resumen_lineas = [f"👥 {etiqueta}: {numero}" for etiqueta, numero in totales.items()]
    if origen:
        resumen_lineas.insert(0, f"📍 Procedencia: Estado {origen}")
    resumen_lineas.insert(0 if not origen else 1, f"🏠 Albergados en: {destino_texto}")
    if necesidades:
        resumen_lineas.append("🆘 Necesidades: " + ", ".join(necesidades))
    resumen_consolidado = "\n".join(resumen_lineas)

    # La fecha del documento se agrega al nombre de la fuente para que dos
    # reportes sucesivos de la MISMA filial (un reporte inicial y una
    # "actualizacion" posterior, con cifras distintas) no colisionen como
    # si fueran la misma fuente en agrupar_y_verificar() -- de lo
    # contrario, al enviar ambos correos en la misma corrida (como va a
    # probar el usuario reenviando todo su historial pendiente), el mas
    # antiguo descartaria silenciosamente al mas reciente (o viceversa) en
    # vez de contarse como dos reportes distintos del mismo hecho.
    fecha_doc_str = fecha_doc.astimezone(ZONA_VENEZUELA).strftime("%d/%m/%Y")
    nombre_base = f"Filial {nombre_filial}" if nombre_filial else f"Reporte de filial ({remitente_email or 'desconocido'})"
    fuente_nombre = f"{nombre_base} ({fecha_doc_str})"

    return {
        "fuente_nombre": fuente_nombre,
        "fuente_tipo": "correo",
        "peso": 1.5,
        "texto": texto_sintetico,
        "resumen_consolidado": resumen_consolidado,
        "es_reporte_filial": True,
        "link": (
            f"https://mail.google.com/mail/u/0/#search/rfc822msgid:{message_id}"
            if message_id else ""
        ),
        "fecha": fecha_doc.isoformat(),
    }
