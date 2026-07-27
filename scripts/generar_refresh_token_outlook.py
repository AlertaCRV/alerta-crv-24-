"""Herramienta de uso manual/interactivo (NO se ejecuta en el workflow
automatico) para obtener un refresh_token nuevo de Microsoft Graph, la
primera vez que se configura el acceso al correo institucional o cuando
el refresh_token guardado en los secretos de GitHub deja de funcionar.

Requiere que YA exista un App Registration en Azure AD/Entra ID con:
  - Tipo de cuenta soportada: segun el tenant institucional (single-tenant
    normalmente).
  - Plataforma "Mobile and desktop applications" habilitada (cliente
    publico, sin client secret).
  - Permiso delegado "Mail.Read" (API Microsoft Graph), con consentimiento
    de administrador otorgado si el tenant lo exige.

Uso:
  1. Definir OUTLOOK_CLIENT_ID y OUTLOOK_TENANT_ID como variables de
     entorno (los mismos valores que ya estan en los secretos de GitHub).
  2. Ejecutar: python3 scripts/generar_refresh_token_outlook.py
  3. Seguir las instrucciones en pantalla: abrir la URL indicada en un
     navegador, iniciar sesion con la cuenta que tiene acceso al correo
     institucional (o una cuenta delegada con permiso sobre ese buzon), e
     ingresar el codigo que se muestra.
  4. El script imprime el refresh_token obtenido. Copiarlo y actualizar el
     secreto OUTLOOK_REFRESH_TOKEN en GitHub (Settings > Secrets and
     variables > Actions) -- nunca commitear este valor al repositorio.
"""

import os
import sys

import msal

SCOPES = ["Mail.Read"]


def main():
    client_id = os.environ.get("OUTLOOK_CLIENT_ID")
    tenant_id = os.environ.get("OUTLOOK_TENANT_ID")
    if not client_id or not tenant_id:
        print(
            "Faltan OUTLOOK_CLIENT_ID y/o OUTLOOK_TENANT_ID en el entorno. "
            "Definilos antes de ejecutar este script (los mismos valores "
            "que ya estan en los secretos de GitHub)."
        )
        sys.exit(1)

    app = msal.PublicClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
    )

    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        print(f"No se pudo iniciar el flujo de autenticacion: {flow}")
        sys.exit(1)

    print(flow["message"])
    result = app.acquire_token_by_device_flow(flow)

    if "refresh_token" not in result:
        print(f"No se obtuvo refresh_token. Respuesta completa: {result}")
        sys.exit(1)

    print("\nAutenticacion exitosa.")
    print("\nNuevo refresh_token (actualizar el secreto OUTLOOK_REFRESH_TOKEN en GitHub):\n")
    print(result["refresh_token"])


if __name__ == "__main__":
    main()
