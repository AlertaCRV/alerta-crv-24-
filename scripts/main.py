from fetch_rss import fetch_rss_items
from fetch_telegram import fetch_telegram_items
from classify import clasificar_item, es_relevante
from verify import agrupar_y_verificar
from verify_ai import verificar_evento_con_ia
from render import redactar_noticia
from state import cargar_publicados, guardar_publicados, filtrar_nuevos, marcar_publicados
from historico import registrar_historico
from historico_fuentes import registrar_texto_fuentes
from publish_telegram import publicar_en_telegram
from build_site import actualizar_datos_sitio
from build_dashboard import actualizar_dashboard
from build_informes import actualizar_informes
from config_loader import load_settings


def main():
    settings = load_settings()["busqueda"]
    ventana = settings["ventana_horas_fuentes"]

    print("Recolectando RSS...")
    items = fetch_rss_items(ventana)
    print(f"  {len(items)} items de RSS")
    # Captura por correo (alertacrv.reportes@gmail.com) desactivada: era un
    # experimento para que las filiales reportaran por correo, pero resultó
    # desordenado y asistemático. Reemplazado por un sistema de captura
    # estandarizado (ver docs/roadmap_evolucion.md).

    # print("Recolectando Telegram...")
    # items += fetch_telegram_items(ventana)
    print(f"  {len(items)} items totales")

    # clasificar_item devuelve una lista: normalmente 1 item, pero un
    # articulo que menciona varios estados con evidencia clara cerca de
    # cada uno genera un item por estado (ver classify.py).
    items = [nuevo for i in items for nuevo in clasificar_item(i)]
    items = [i for i in items if es_relevante(i)]
    print(f"  {len(items)} items relevantes (con tipo + ubicación detectados)")

    eventos = agrupar_y_verificar(items)
    print(f"  {len(eventos)} eventos agrupados")

    eventos = [verificar_evento_con_ia(e) for e in eventos]
    eventos = [e for e in eventos if e is not None]
    print(f"  {len(eventos)} eventos tras verificación de plausibilidad (IA)")

    publicados = cargar_publicados()
    eventos_nuevos = filtrar_nuevos(eventos, publicados)
    print(f"  {len(eventos_nuevos)} eventos nuevos o actualizados para publicar")

    # Debe ir ANTES de redactar_noticia(): extrae y borra el texto completo
    # de las fuentes de cada evento (usado solo para informes narrativos),
    # para que ese texto nunca llegue al JSON publico del sitio.
    registrar_texto_fuentes(eventos_nuevos)

    noticias = [redactar_noticia(e) for e in eventos_nuevos]

    if noticias:
        publicar_en_telegram(noticias)
        actualizar_datos_sitio(noticias)
        registrar_historico(eventos_nuevos)
        actualizar_dashboard()

    publicados = marcar_publicados(eventos_nuevos, publicados)
    guardar_publicados(publicados)

    # Los informes narrativos se generan/regeneran como mucho una vez al dia
    # (ver build_informes.py) -- se llama en cada corrida, pero la funcion
    # decide internamente si hace falta trabajo real o no.
    actualizar_informes()

    print("Listo.")


if __name__ == "__main__":
    main()
