"""Envía un webhook firmado de prueba al receptor (demo local).

Uso:
    python tools/send_webhook.py              # firma válida   -> 202
    python tools/send_webhook.py --invalid    # firma alterada -> 401

La clave HMAC se toma de ``VULCANO_WEBHOOK_SECRET`` (con el mismo default de
desarrollo que el receptor) o de ``--secret``.
"""

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_SECRET = os.getenv("VULCANO_WEBHOOK_SECRET", "vulcano-dev-secret-2026")


def build_signature(secret: str, timestamp: int, payload: bytes) -> str:
    """HMAC-SHA256 sobre ``"{timestamp}." + payload``, igual que ``webhook_crypto``."""
    return hmac.new(secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256).hexdigest()


def main() -> int:
    """Firma el payload de ejemplo, lo envía e imprime el código y el cuerpo de la respuesta."""
    parser = argparse.ArgumentParser(description="Envía un webhook firmado de prueba")
    parser.add_argument("--url", default="http://127.0.0.1:8000/webhook")
    parser.add_argument("--secret", default=DEFAULT_SECRET)
    parser.add_argument("--invalid", action="store_true", help="Envía una firma inválida (espera 401)")
    args = parser.parse_args()

    payload = json.dumps({"event": "payment_completed", "amount": 1500}, separators=(",", ":")).encode()
    timestamp = int(time.time())
    signature = "0" * 64 if args.invalid else build_signature(args.secret, timestamp, payload)

    request = urllib.request.Request(
        args.url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": f"t={timestamp},v1={signature}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            print(response.status, response.read().decode())
    except urllib.error.HTTPError as error:
        print(error.code, error.read().decode())
    except urllib.error.URLError as error:
        print(f"No se pudo conectar con {args.url}: {error.reason}. ¿Está corriendo start-receiver?")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
