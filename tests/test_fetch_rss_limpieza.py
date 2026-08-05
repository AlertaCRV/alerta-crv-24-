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
