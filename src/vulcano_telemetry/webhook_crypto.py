"""Firma y verificación HMAC-SHA256 de webhooks.

Titular: Rene (rama ``feature/renechumacero``).

TODO(Rene): implementar según la consigna §4.2 y el instructivo §1:

- ``generate_signature(secret, timestamp, payload_bytes) -> str``:
  HMAC-SHA256 hex sobre ``f"{timestamp}.".encode("utf-8") + payload_bytes``;
- ``verify_signature(secret, header_value, payload_bytes, tolerance_sec=300)
  -> bool``: parsea ``t=...`` y ``v1=...`` del header
  ``X-Webhook-Signature``; si falta o está malformado lanza
  ``WebhookSignatureError``; fuera de la ventana ±300 s lanza
  ``WebhookTimestampError`` (anti-replay); la comparación final se hace
  obligatoriamente con ``hmac.compare_digest()`` (anti timing attack).
"""
