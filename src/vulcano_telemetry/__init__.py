"""Paquete del motor de eventos VulcanoEventEngine.

Titular: Ariel (rama ``feature/arielfernandez``).

Expone la API pública del motor (Fase 3 del plan por fases).
"""

from .core_sqs import consume_events, get_sqs_client, produce_event
from .exceptions import (
    CorruptedMessageError,
    QueueTimeoutError,
    SQSConnectionError,
    VulcanoError,
    WebhookDeliveryError,
    WebhookSignatureError,
    WebhookTimestampError,
)
from .logging_engine import AsyncJSONFormatter, gzip_rotator, setup_vulcano_logging
from .sanitizer import (
    parse_queue_name,
    parse_secret_key,
    parse_wait_time,
    parse_webhook_url,
)
from .webhook_crypto import generate_signature, verify_signature
from .webhook_receiver import WEBHOOK_SECRET, app

__version__ = "0.1.0"

__all__ = [
    "AsyncJSONFormatter",
    "CorruptedMessageError",
    "QueueTimeoutError",
    "SQSConnectionError",
    "VulcanoError",
    "WEBHOOK_SECRET",
    "WebhookDeliveryError",
    "WebhookSignatureError",
    "WebhookTimestampError",
    "app",
    "consume_events",
    "generate_signature",
    "get_sqs_client",
    "gzip_rotator",
    "parse_queue_name",
    "parse_secret_key",
    "parse_wait_time",
    "parse_webhook_url",
    "produce_event",
    "setup_vulcano_logging",
    "verify_signature",
]
