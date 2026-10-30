"""Servidor HTTP receptor de Webhooks para Vulcano Event Engine.

Responsable: Rene Chumacero (Dev C)
"""

import json
import logging
import os
import uuid

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse

try:
    from vulcano_telemetry.webhook_crypto import verify_signature
    from vulcano_telemetry.exceptions import (
        WebhookSignatureError,
        WebhookTimestampError,
    )
    from vulcano_telemetry.core_sqs import get_sqs_client, produce_event
    from vulcano_telemetry.logging_engine import is_valid_trace_id
except ImportError:
    from webhook_crypto import verify_signature
    class WebhookSignatureError(Exception): pass
    class WebhookTimestampError(Exception): pass
    def get_sqs_client(endpoint_url=None): return None
    def produce_event(sqs_client, queue_url, event_data, *, trace_id=None): return "msg-id-12345"
    def is_valid_trace_id(value): return False

app = FastAPI(title="Vulcano Webhook Receiver API", version="1.0.0")

# Hijo de "vulcano_telemetry": usa el pipeline asíncrono que configura el CLI.
logger = logging.getLogger("vulcano_telemetry.receiver")

# Variables de entorno con valores por defecto para desarrollo local
WEBHOOK_SECRET = os.getenv("VULCANO_WEBHOOK_SECRET", "vulcano-dev-secret-2026")
QUEUE_URL = os.getenv(
    "VULCANO_QUEUE_URL",
    "http://localhost:4566/000000000000/vulcano-events-queue"
)
AWS_ENDPOINT = os.getenv("VULCANO_AWS_ENDPOINT", "http://localhost:4566")


@app.post("/webhook", status_code=status.HTTP_202_ACCEPTED)
async def receive_webhook(request: Request):
    """Receptor asíncrono de webhooks.

    Verifica firma HMAC en tiempo constante y encola el mensaje en SQS.
    Cada pedido lleva un TraceId: el del header ``X-Trace-Id`` si tiene un
    formato seguro (``[A-Za-z0-9._-]{1,64}``) o uno nuevo (UUID4).
    """
    incoming = request.headers.get("X-Trace-Id")
    trace_id = incoming if is_valid_trace_id(incoming) else str(uuid.uuid4())

    # 1. Obtener bytes crudos obligatoriamente antes de parsear JSON
    raw_bytes = await request.body()

    # 2. Obtener encabezado de firma
    signature_header = request.headers.get("X-Webhook-Signature")
    if not signature_header:
        logger.warning("Webhook rechazado: header de firma ausente", extra={"TraceId": trace_id})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header X-Webhook-Signature ausente."
        )

    # 3. Validar Criptografía y Timestamp
    try:
        verify_signature(
            secret=WEBHOOK_SECRET,
            header_value=signature_header,
            payload_bytes=raw_bytes,
            tolerance_sec=300
        )
    except WebhookSignatureError as err:
        logger.warning("Webhook rechazado: firma inválida (%s)", err, extra={"TraceId": trace_id})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Firma inválida: {str(err)}"
        ) from err
    except WebhookTimestampError as err:
        logger.warning("Webhook rechazado: timestamp expirado (%s)", err, extra={"TraceId": trace_id})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Timestamp expirado (Replay attack): {str(err)}"
        ) from err

    # 4. Parsear JSON una vez validada la firma
    try:
        event_data = json.loads(raw_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as err:
        logger.warning("Webhook rechazado: JSON inválido", extra={"TraceId": trace_id})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload no es un JSON válido."
        ) from err
    if not isinstance(event_data, dict):
        logger.warning("Webhook rechazado: el payload no es un objeto JSON", extra={"TraceId": trace_id})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El payload debe ser un objeto JSON."
        )

    # 5. Encolar evento en SQS
    try:
        sqs_client = get_sqs_client(endpoint_url=AWS_ENDPOINT)
        message_id = produce_event(
            sqs_client=sqs_client,
            queue_url=QUEUE_URL,
            event_data=event_data,
            trace_id=trace_id,
        )
    except Exception as err:
        logger.error(
            "No se pudo publicar el evento en SQS", exc_info=err, extra={"TraceId": trace_id}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al publicar evento en SQS."
        ) from err

    webhook_id = event_data.get("webhook_id") or event_data.get("id")
    logger.info(
        "Webhook aceptado y encolado",
        extra={"TraceId": trace_id, "MessageId": message_id, "WebhookId": webhook_id},
    )
    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={"status": "accepted", "message_id": message_id, "trace_id": trace_id}
    )
