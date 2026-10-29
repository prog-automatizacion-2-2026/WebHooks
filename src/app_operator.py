"""Punto de entrada CLI de VulcanoEventEngine.

Subcomandos:
    produce-sqs       Publica un evento de prueba en la cola SQS.
    start-receiver    Levanta el servidor receptor de webhooks.
    start-dispatcher  Consume SQS y despacha los eventos firmados.

Titular: Ariel (rama ``feature/arielfernandez``) — Fase 1: esqueleto del CLI.

Dependencias: ``sanitizer``/``exceptions``/``core_sqs`` (Clelia),
``webhook_crypto``/``webhook_receiver`` (Rene) y ``logging_engine``
(Francisco). ``--help`` queda operativo cuando mergee ``sanitizer.py``; los
subcomandos, cuando estén ``core_sqs``, ``webhook_crypto``, el receptor y el
pipeline de logging.
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

logger = logging.getLogger(__name__)

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
    event = {
        "webhook_id": str(uuid.uuid4()),
        "event_topic": "payment.created",
        "amount": 1500,
        "currency": "ARS",
        "timestamp": int(time.time()),
    }
    message_id = core_sqs.produce_event(client, _queue_url(args.queue), event)
    logger.info("Evento de prueba encolado: MessageId=%s", message_id)


def cmd_start_receiver(args: argparse.Namespace) -> None:
    """Levanta el receptor de Rene con la configuración recibida por CLI."""
    os.environ["VULCANO_QUEUE_URL"] = _queue_url(args.queue)
    os.environ["VULCANO_WEBHOOK_SECRET"] = args.secret
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
    for message in core_sqs.consume_events(client, queue_url, wait_time=args.wait_time):
        dispatch_webhook(args.url, args.secret, message["body"])


def dispatch_webhook(target_url: str, secret: str, payload_dict: dict[str, Any]) -> None:
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
    try:
        response = requests.post(target_url, data=payload_bytes, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise exceptions.WebhookDeliveryError(f"Falló la entrega a {target_url}") from exc


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada: parsea argumentos, ejecuta y apaga de forma ordenada."""
    args = build_parser().parse_args(argv)
    listener = logging_engine.setup_vulcano_logging()
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
                "Errores de firma/timestamp: %s (agrupados)", len(group.exceptions)
            )
        except* exceptions.SQSConnectionError as group:
            exit_code = 1
            logger.error("Errores de conexión con SQS: %s (agrupados)", len(group.exceptions))
    except KeyboardInterrupt:
        logger.info("Apagado solicitado por el usuario")
    finally:
        if listener is not None:
            listener.stop()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
