import asyncio
import os
import uvicorn
from app.main import app

async def main():
    cert_path = "app/certs/cert.pem"
    key_path = "app/certs/key.pem"

    tasks = []

    # 1. Plain HTTP on 8080
    config_http = uvicorn.Config(app, host="0.0.0.0", port=8080, log_level="info")
    server_http = uvicorn.Server(config_http)
    tasks.append(server_http.serve())

    # 2. Secure HTTPS on 8443 (Unlocks iOS Safari Web Speech and Microphone APIs)
    if os.path.exists(cert_path) and os.path.exists(key_path):
        config_https = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=8443,
            ssl_certfile=cert_path,
            ssl_keyfile=key_path,
            log_level="info"
        )
        server_https = uvicorn.Server(config_https)
        tasks.append(server_https.serve())
        print(f"✨ Dual Server Active: HTTP on port 8080 & HTTPS on port 8443 (certs loaded from {cert_path})")
    else:
        print("⚠️ SSL certs not found, running HTTP only on port 8080.")

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
