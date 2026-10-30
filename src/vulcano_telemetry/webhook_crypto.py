"""Módulo de seguridad criptográfica para Webhooks de Vulcano Event Engine.

Responsable: Rene Chumacero (Dev C)
"""

import hmac
import hashlib
import time
from typing import Tuple

try:
    from vulcano_telemetry.exceptions import (
        WebhookSignatureError,
        WebhookTimestampError,
    )
except ImportError:
    # Excepciones fallback si no está instalado el paquete localmente aún
    class VulcanoError(Exception):
        """Excepción base del sistema Vulcano."""
        pass

    class WebhookSignatureError(VulcanoError):
        """Firma HMAC-SHA256 ausente, malformada o inválida."""
        pass

    class WebhookTimestampError(VulcanoError):
        """Timestamp fuera de la ventana de tolerancia (anti-replay)."""
        pass


def generate_signature(secret: str, timestamp: int | str, payload_bytes: bytes) -> str:
    """Genera una firma HMAC-SHA256 codificada en hexadecimal sobre el timestamp y el payload.

    Formato firmado: f"{timestamp}.".encode("utf-8") + payload_bytes
    """
    secret_bytes = secret.encode("utf-8")
    prefix = f"{timestamp}.".encode("utf-8")
    signed_payload = prefix + payload_bytes

    signature = hmac.new(
        secret_bytes,
        signed_payload,
        hashlib.sha256
    ).hexdigest()

    return signature


def _parse_header(header_value: str) -> Tuple[int, str]:
    """Extrae el timestamp (t) y la firma (v1) del encabezado X-Webhook-Signature.

    Formato esperado: "t=1700000000,v1=a1b2c3d4..."
    """
    if not header_value:
        raise WebhookSignatureError("Encabezado X-Webhook-Signature ausente o vacío.")

    parts = {}
    try:
        for item in header_value.split(","):
            if "=" in item:
                k, v = item.strip().split("=", 1)
                parts[k] = v

        if "t" not in parts or "v1" not in parts:
            raise WebhookSignatureError("Encabezado X-Webhook-Signature malformado.")

        timestamp = int(parts["t"])
        signature = parts["v1"]
        return timestamp, signature
    except ValueError as exc:
        raise WebhookSignatureError("Timestamp inválido en el encabezado de la firma.") from exc


def verify_signature(
    secret: str,
    header_value: str,
    payload_bytes: bytes,
    tolerance_sec: int = 300
) -> bool:
    """Verifica la firma HMAC-SHA256 y la ventana de tolerancia del timestamp (anti-replay).

    Lanza WebhookSignatureError si la firma es inválida o el header está malformado.
    Lanza WebhookTimestampError si el timestamp supera la ventana de tolerancia.
    """
    timestamp, received_signature = _parse_header(header_value)

    # Protección Anti-Replay: validar ventana de tiempo (+/- tolerance_sec)
    current_time = int(time.time())
    if abs(current_time - timestamp) > tolerance_sec:
        raise WebhookTimestampError(
            f"Timestamp fuera de la ventana de tolerancia ({abs(current_time - timestamp)}s > {tolerance_sec}s)."
        )

    # Recalcular firma esperada
    expected_signature = generate_signature(secret, timestamp, payload_bytes)

    # Comparación en tiempo constante (Anti Timing Attack)
    if not hmac.compare_digest(expected_signature, received_signature):
        raise WebhookSignatureError("La firma HMAC enviada no coincide.")

    return True

