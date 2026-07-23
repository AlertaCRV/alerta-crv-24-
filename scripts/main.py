from fetch_email import fetch_email_items
from fetch_rss import fetch_rss_items
from fetch_telegram import fetch_telegram_items
from classify import clasificar_item, es_relevante
from verify import agrupar_y_verificar
from verify_ai import parece_emergencia_actual
from render import redactar_noticia
from state import cargar_publicados, guardar_publicados, filtrar_nuevos, marcar_publicados
from publish_telegram import publicar_en_telegram
from build_site import actualizar_datos_sitio
from config_loader import load_settings


def main():
    settings = load_settings()["busqueda"]
    ventana = settings["ventana_horas_fuentes"]

    print("Recolectando RSS...")
    items = fetch_rss_items(ventana)
    print(f"  {len(items)} items de RSS")
    print("Recolectando correos institucionales...")
    items += fetch_email_items(ventana)

    # print("Recolectando Telegram...")
    # items += fetch_telegram_items(ventana)
    print(f"  {len(items)} items totales")

    items = [clasificar_item(i) for i in items]
    items = [i for i in items if es_relevante(i)]
    print(f"  {len(items)} items relevantes (con tipo + ubicación detectados)")

    eventos = agrupar_y_verificar(items)
    print(f"  {len(eventos)} eventos agrupados")

    eventos = [e for e in eventos if parece_emergencia_actual(e)]
    print(f"  {len(eventos)} eventos tras verificación de plausibilidad (IA)")

    publicados = cargar_publicados()
    eventos_nuevos = filtrar_nuevos(eventos, publicados)
    print(f"  {len(eventos_nuevos)} eventos nuevos o actualizados para publicar")

    noticias = [redactar_noticia(e) for e in eventos_nuevos]

    if noticias:
        publicar_en_telegram(noticias)
        actualizar_datos_sitio(noticias)

    publicados = marcar_publicados(eventos_nuevos, publicados)
    guardar_publicados(publicados)

    print("Listo.")


if __name__ == "__main__":
    main()
