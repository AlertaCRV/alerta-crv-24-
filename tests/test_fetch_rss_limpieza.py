"""Pruebas de _limpiar_texto() (fetch_rss.py) -- limpieza de boilerplate de
plantillas de WordPress (pie de pagina, "articulos relacionados") que puede
contaminar el texto que ve el clasificador con ubicaciones/palabras clave
de OTRAS notas sin relacion con el articulo real.

Cada caso reproduce un hallazgo real ya documentado en
docs/roadmap_evolucion.md.
"""

from fetch_rss import _limpiar_texto


def test_tambien_puedes_leer_se_elimina():
    # Caso real (05-08-2026, notiapure.com.ve): un articulo sobre un sismo
    # de magnitud 6.3 en Mindanao, Filipinas -- "sin causar victimas" --
    # generaba DOS alertas falsas de sismo critico en Venezuela (Apure y
    # Anzoategui) porque el pie de "Tambien Puedes Leer:" enlazaba titulos
    # de otras notas locales sin relacion con el hecho real.
    texto = (
        "Terremoto De 6,3 Azota La Isla De Mindanao En Filipinas Sin Causar "
        "Victimas. El USGS registro este miercoles un terremoto de magnitud "
        "6,3 en la isla de Mindanao, en el sur de Filipinas. "
        "Si quieres conocer otras noticias parecidas a Terremoto De 6,3 "
        "Azota La Isla De Mindanao En Filipinas puedes visitar la categoria "
        "Sucesos . Tambien Puedes Leer: Policia De Apure Detiene A Dos "
        "Mujeres Por Lesiones Reciprocas En Biruaca Aumenta A 6.125 La "
        "Cifra De Fallecidos Tras Los Sismos Del 24 De Junio En Venezuela"
    )
    limpio = _limpiar_texto(texto)
    assert "apure" not in limpio.lower()
    assert "biruaca" not in limpio.lower()
    assert "fallecidos" not in limpio.lower()
    assert "mindanao" in limpio.lower()


def test_leer_tambien_infinitivo_se_elimina():
    # Caso real (07-08-2026, El Impulso): "Leer tambien:" (infinitivo, a
    # diferencia del imperativo "Lea/Lee tambien:" ya cubierto) enlazaba un
    # suceso carcelario totalmente distinto ("tres muertes", "51 victimas
    # fatales" en El Marite) dentro de un articulo sobre una protesta de
    # familiares de presos politicos en Caracas.
    texto = (
        "Familiares protestan frente a la Cancilleria en Caracas para exigir "
        "la excarcelacion de sus allegados. Leer tambien: OVP denuncia tres "
        "muertes en El Marite y eleva a 51 las victimas fatales en carceles "
        "venezolanas."
    )
    limpio = _limpiar_texto(texto)
    assert "muertes" not in limpio.lower()
    assert "victimas fatales" not in limpio.lower()
    assert "cancilleria" in limpio.lower()


def test_lea_tambien_original_sigue_funcionando():
    # Variante original ya cubierta desde antes (27-07-2026): no debe
    # romperse con el cambio de regex.
    texto = (
        "Donan utiles escolares a una escuela de La Guaira. Lea tambien: "
        "Tres incendios en menos de un mes registra la ciudad de Maturin."
    )
    limpio = _limpiar_texto(texto)
    assert "incendio" not in limpio.lower()
    assert "maturin" not in limpio.lower()
    assert "la guaira" in limpio.lower()


def test_texto_sin_boilerplate_no_se_altera():
    texto = "Un incendio forestal afecto varias hectareas en el estado Monagas."
    assert _limpiar_texto(texto) == texto


def test_estado_seguido_de_pleca_embebido_se_elimina():
    # Caso real (07-08-2026, El Pitazo): un articulo integro sobre presos
    # politicos en huelga de hambre en el Fuerte Guaicaipuro (estado
    # Miranda, nunca mencionado en el texto) generaba una alerta de
    # orden_publico en Zulia solo porque el texto traia embebido, sin
    # relacion alguna ni punto que lo separe del resto, el titular de OTRA
    # nota: "Zulia | Policia encuentra cuerpo de coronel retirado de la GN
    # con rastros de violencia".
    texto = (
        "declaro Johanna Chirinos, tia de dos presos politicos. Zulia | "
        "Policia encuentra cuerpo de coronel retirado de la GN con rastros "
        "de violencia Detallaron que la protesta tambien seria una "
        "exigencia para su liberacion."
    )
    limpio = _limpiar_texto(texto)
    assert "zulia" not in limpio.lower()
    assert "detallaron que la protesta" in limpio.lower()


def test_estado_seguido_de_pleca_al_inicio_del_titular_propio_tambien_se_elimina():
    # La misma plantilla "Estado | Titular" tambien aparece, de forma
    # legitima, como el titular del propio articulo (siempre al inicio).
    # Se elimina igual (no se pierde informacion real: el estado real
    # siempre se repite mas adelante en el cuerpo del articulo real de
    # El Pitazo, ver el estado explicito unas frases despues).
    texto = (
        "Bolivar | Hombres armados atacan con disparos protesta por "
        "apagones en Guasipati Ciudad Guayana.- Una protesta fue disuelta "
        "la noche del martes al sureste de Bolivar."
    )
    limpio = _limpiar_texto(texto)
    assert limpio.lower().startswith("hombres armados atacan")
    assert "bolivar" in limpio.lower()  # se repite mas adelante en el cuerpo


def test_pleca_sin_nombre_de_estado_antes_no_se_toca():
    texto = "Publicado el 2026-08-07 | Seccion Sucesos. Un incendio afecto una vivienda."
    assert _limpiar_texto(texto) == texto
