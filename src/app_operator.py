"""Punto de entrada CLI de VulcanoEventEngine.

Subcomandos:
    produce-sqs       Publica un evento de prueba en la cola SQS.
    start-receiver    Levanta el servidor receptor de webhooks.
    start-dispatcher  Consume SQS y despacha los eventos firmados.

Titular: Ariel (rama ``feature/arielfernandez``).

Dependencias: ``sanitizer``/``exceptions``/``core_sqs`` (Clelia),
``webhook_crypto``/``webhook_receiver`` (Rene) y ``logging_engine``
(Francisco).

Trazabilidad: cada evento lleva un TraceId que nace en el receptor (o en
``produce-sqs``), viaja como atributo del mensaje SQS y el despachador lo
reenvía al destino en el header ``X-Trace-Id``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
import uuid
from collections.abc import Sequence
from typing import Any

import requests
import uvicorn

from vulcano_telemetry import core_sqs, exceptions, logging_engine, sanitizer
from vulcano_telemetry import webhook_crypto, webhook_receiver

logger = logging.getLogger("vulcano_telemetry")

DEFAULT_ENDPOINT = os.getenv("VULCANO_AWS_ENDPOINT", "http://localhost:4566")
DEFAULT_QUEUE_NAME = "vulcano-events-queue"
DEFAULT_WAIT_TIME = 10
DEFAULT_TARGET_URL = "http://localhost:8000/webhook"
DEFAULT_SECRET = os.getenv("VULCANO_WEBHOOK_SECRET", "vulcano-dev-secret-2026")
RECEIVER_HOST = "127.0.0.1"
RECEIVER_PORT = 8000


def _queue_url(queue_name: str) -> str:
    """Arma la URL de la cola en LocalStack a partir de su nombre."""
    return f"{DEFAULT_ENDPOINT}/000000000000/{queue_name}"


def build_parser() -> argparse.ArgumentParser:
    """Construye el parser: flags globales validados y los tres subcomandos."""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--queue",
        type=sanitizer.parse_queue_name,
        default=DEFAULT_QUEUE_NAME,
        help="Nombre de la cola SQS (default: %(default)s)",
    )
    common.add_argument(
        "--wait-time",
        type=sanitizer.parse_wait_time,
        default=DEFAULT_WAIT_TIME,
        help="Segundos de long polling, 1-20 (default: %(default)s)",
    )
    common.add_argument(
        "--url",
        type=sanitizer.parse_webhook_url,
        default=DEFAULT_TARGET_URL,
        help="URL destino del webhook (default: %(default)s)",
    )
    common.add_argument(
        "--secret",
        type=sanitizer.parse_secret_key,
        default=DEFAULT_SECRET,
        help="Clave HMAC de desarrollo (mínimo 16 caracteres)",
    )

    parser = argparse.ArgumentParser(
        prog="app_operator.py",
        description="Operador de VulcanoEventEngine: productor, receptor y despachador.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    produce = subparsers.add_parser(
        "produce-sqs",
        parents=[common],
        help="Publica un evento de prueba en SQS",
    )
    produce.set_defaults(func=cmd_produce_sqs)

    receiver = subparsers.add_parser(
        "start-receiver",
        parents=[common],
        help="Levanta el servidor receptor de webhooks",
    )
    receiver.set_defaults(func=cmd_start_receiver)

    dispatcher = subparsers.add_parser(
        "start-dispatcher",
        parents=[common],
        help="Consume SQS y despacha los eventos",
    )
    dispatcher.set_defaults(func=cmd_start_dispatcher)

    return parser


def cmd_produce_sqs(args: argparse.Namespace) -> None:
    """Publica un evento de ejemplo para validar la cola y el flujo."""
    client = core_sqs.get_sqs_client(endpoint_url=DEFAULT_ENDPOINT)
    trace_id = str(uuid.uuid4())
    event = {
        "webhook_id": str(uuid.uuid4()),
        "event_topic": "payment.created",
        "amount": 1500,
        "currency": "ARS",
        "timestamp": int(time.time()),
    }
    message_id = core_sqs.produce_event(
        client, _queue_url(args.queue), event, trace_id=trace_id
    )
    logger.info(
        "Evento de prueba encolado",
        extra={"TraceId": trace_id, "MessageId": message_id, "WebhookId": event["webhook_id"]},
    )


def cmd_start_receiver(args: argparse.Namespace) -> None:
    """Levanta el receptor de Rene con la configuración recibida por CLI."""
    queue_url = _queue_url(args.queue)
    os.environ["VULCANO_QUEUE_URL"] = queue_url
    os.environ["VULCANO_WEBHOOK_SECRET"] = args.secret
    webhook_receiver.QUEUE_URL = queue_url
    webhook_receiver.WEBHOOK_SECRET = args.secret
    logger.info("Receptor escuchando en http://%s:%s", RECEIVER_HOST, RECEIVER_PORT)
    uvicorn.run(webhook_receiver.app, host=RECEIVER_HOST, port=RECEIVER_PORT)


def cmd_start_dispatcher(args: argparse.Namespace) -> None:
    """Consume SQS con long polling y despacha cada evento al destino.

    ``consume_events`` borra el mensaje recién cuando el despacho termina sin
    excepciones; si falla, queda en la cola para el reintento y su paso a la DLQ.
    """
    client = core_sqs.get_sqs_client(endpoint_url=DEFAULT_ENDPOINT)
    queue_url = _queue_url(args.queue)
    logger.info("Despachador escuchando %s (wait_time=%ss)", queue_url, args.wait_time)
    delivered = 0
    for message in core_sqs.consume_events(client, queue_url, wait_time=args.wait_time):
        context = trace_context(message)
        logger.info("Evento recibido de SQS", extra=context)
        try:
            dispatch_webhook(args.url, args.secret, message["body"], trace_id=context["TraceId"])
        except exceptions.WebhookDeliveryError as err:
            err.add_note(f"TraceId={context['TraceId']} MessageId={context['MessageId']}")
            err.add_note("El mensaje no se borra: SQS lo reintenta y tras 3 intentos va a la DLQ")
            logger.error("Entrega fallida a %s", args.url, extra=context)
            raise
        delivered += 1
        logger.info("Webhook entregado a %s", args.url, extra=context)
    logger.info("Lote terminado: %s evento(s) entregado(s)", delivered)


def trace_context(message: dict[str, Any]) -> dict[str, Any]:
    """Arma los campos de trazabilidad de un mensaje consumido de SQS."""
    attributes = message.get("attributes", {})
    body = message.get("body")
    body = body if isinstance(body, dict) else {}
    trace_id = attributes.get("TraceId", {}).get("StringValue") or body.get("trace_id")
    if not logging_engine.is_valid_trace_id(trace_id):
        trace_id = None
    return {
        "TraceId": trace_id,
        "MessageId": message.get("message_id"),
        "WebhookId": body.get("webhook_id") or body.get("id"),
    }


def dispatch_webhook(
    target_url: str,
    secret: str,
    payload_dict: dict[str, Any],
    *,
    trace_id: str | None = None,
) -> None:
    """Firma y re-emite el webhook al destino del cliente.

    Si el POST falla lanza ``WebhookDeliveryError`` y NO borra el mensaje de
    SQS: la cola lo reintenta y, tras ``maxReceiveCount``, cae a la DLQ.
    """
    payload_bytes = json.dumps(payload_dict, separators=(",", ":")).encode("utf-8")
    timestamp = int(time.time())
    signature = webhook_crypto.generate_signature(secret, timestamp, payload_bytes)
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": f"t={timestamp},v1={signature}",
    }
    if logging_engine.is_valid_trace_id(trace_id):
        headers["X-Trace-Id"] = trace_id
    try:
        response = requests.post(target_url, data=payload_bytes, headers=headers, timeout=10)
        response.raise_for_status()
    except (requests.RequestException, ValueError) as exc:
        error = exceptions.WebhookDeliveryError(f"Falló la entrega a {target_url}")
        error.add_note(f"Causa: {type(exc).__name__}")
        raise error from exc


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada: parsea argumentos, ejecuta y apaga de forma ordenada."""
    args = build_parser().parse_args(argv)
    logger, listener = logging_engine.setup_vulcano_logging(console=True)
    if listener is not None:
        listener.start()
    exit_code = 0
    try:
        try:
            args.func(args)
        except* (
            exceptions.WebhookSignatureError,
            exceptions.WebhookTimestampError,
        ) as group:
            exit_code = 1
            logger.error(
                "Errores de firma/timestamp: %s (agrupados)",
                len(group.exceptions),
                exc_info=group,
            )
        except* exceptions.SQSConnectionError as group:
            exit_code = 1
            logger.error(
                "Errores de conexión con SQS: %s (agrupados)",
                len(group.exceptions),
                exc_info=group,
            )
        except* exceptions.VulcanoError as group:
            exit_code = 1
            logger.error(
                "Errores del motor Vulcano: %s (agrupados)",
                len(group.exceptions),
                exc_info=group,
            )
    except KeyboardInterrupt:
        logger.info("Apagado solicitado por el usuario")
    finally:
        if listener is not None:
            listener.stop()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
