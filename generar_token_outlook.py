import msal

client_id = input("Ingresa tu Application (client) ID: ")
tenant_id = input("Ingresa tu Directory (tenant) ID: ")

app = msal.PublicClientApplication(
    client_id,
    authority=f"https://login.microsoftonline.com/{tenant_id}",
)

flow = app.initiate_device_flow(scopes=["Mail.Read"])
if "user_code" not in flow:
    raise Exception("No se pudo iniciar el flujo: " + str(flow))

print(flow["message"])

result = app.acquire_token_by_device_flow(flow)

if "refresh_token" in result:
    print("\n\nTU REFRESH TOKEN (guárdalo, es secreto):\n")
    print(result["refresh_token"])
else:
    print("Error:", result.get("error"), result.get("error_description"))
