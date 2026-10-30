"""Trazabilidad de punta a punta: TraceId, MessageId y WebhookId.

Cubre los atributos SQS de ``produce_event``, el TraceId que devuelve el
receptor y el que reenvía el despachador. No necesita LocalStack: SQS y el
destino HTTP se reemplazan por dobles de prueba.
"""
import time

import pytest
import requests
from fastapi.testclient import TestClient

import app_operator
from vulcano_telemetry import core_sqs, webhook_receiver
from vulcano_telemetry.exceptions import WebhookDeliveryError
from vulcano_telemetry.webhook_crypto import generate_signature


class FakeSQS:
    """Doble de cliente SQS que guarda lo enviado."""

    def __init__(self):
        self.sent = []

    def send_message(self, **kwargs):
        self.sent.append(kwargs)
        return {"MessageId": "msg-001"}


def _attrs(sent):
    return {k: v["StringValue"] for k, v in sent["MessageAttributes"].items()}


def test_produce_event_always_sets_trace_attributes():
    fake = FakeSQS()
    message_id = core_sqs.produce_event(fake, "queue-url", {"event": "payment_completed"})
    attrs = _attrs(fake.sent[0])
    assert message_id == "msg-001"
    assert set(attrs) == {"TraceId", "EventTopic", "Timestamp"}
    assert attrs["EventTopic"] == "payment_completed"
    assert attrs["TraceId"]  # generado automáticamente


def test_produce_event_uses_given_trace_id_and_event_topic():
    fake = FakeSQS()
    core_sqs.produce_event(
        fake, "queue-url", {"event_topic": "payment.created", "timestamp": 1700000000},
        trace_id="trace-abc",
    )
    attrs = _attrs(fake.sent[0])
    assert attrs == {
        "TraceId": "trace-abc", "EventTopic": "payment.created", "Timestamp": "1700000000",
    }


@pytest.fixture
def receiver(monkeypatch):
    """Receptor con SQS reemplazado: captura el trace_id que recibe produce_event."""
    captured = {}

    def fake_produce(sqs_client, queue_url, event_data, *, trace_id=None):
        captured.update(event=event_data, trace_id=trace_id)
        return "msg-002"

    monkeypatch.setattr(webhook_receiver, "get_sqs_client", lambda endpoint_url=None: None)
    monkeypatch.setattr(webhook_receiver, "produce_event", fake_produce)
    return TestClient(webhook_receiver.app), captured


def _signed_headers(payload, **extra):
    timestamp = int(time.time())
    signature = generate_signature(webhook_receiver.WEBHOOK_SECRET, timestamp, payload)
    return {"X-Webhook-Signature": f"t={timestamp},v1={signature}", **extra}


def test_receiver_returns_trace_id_and_passes_it_to_sqs(receiver):
    client, captured = receiver
    payload = b'{"event":"payment_completed","amount":1500}'
    response = client.post("/webhook", content=payload, headers=_signed_headers(payload))
    body = response.json()
    assert response.status_code == 202
    assert body["message_id"] == "msg-002"
    assert body["trace_id"] == captured["trace_id"]


def test_receiver_honors_incoming_trace_header(receiver):
    client, captured = receiver
    payload = b'{"event":"payment_completed"}'
    headers = _signed_headers(payload, **{"X-Trace-Id": "trace-from-client"})
    response = client.post("/webhook", content=payload, headers=headers)
    assert response.json()["trace_id"] == "trace-from-client"
    assert captured["trace_id"] == "trace-from-client"


def test_trace_context_reads_sqs_attributes():
    message = {
        "message_id": "msg-003",
        "body": {"webhook_id": "wh-1"},
        "attributes": {"TraceId": {"StringValue": "trace-xyz", "DataType": "String"}},
    }
    assert app_operator.trace_context(message) == {
        "TraceId": "trace-xyz", "MessageId": "msg-003", "WebhookId": "wh-1",
    }


class _OkResponse:
    def raise_for_status(self):
        return None


def test_dispatch_forwards_trace_header(monkeypatch):
    sent = {}

    def fake_post(url, data, headers, timeout):
        sent.update(url=url, headers=headers)
        return _OkResponse()

    monkeypatch.setattr(app_operator.requests, "post", fake_post)
    app_operator.dispatch_webhook("http://destino/", "x" * 16, {"a": 1}, trace_id="trace-1")
    assert sent["headers"]["X-Trace-Id"] == "trace-1"
    assert sent["headers"]["X-Webhook-Signature"].startswith("t=")


def test_dispatch_failure_raises_delivery_error_with_note(monkeypatch):
    def failing_post(*args, **kwargs):
        raise requests.ConnectionError("rechazado")

    monkeypatch.setattr(app_operator.requests, "post", failing_post)
    with pytest.raises(WebhookDeliveryError) as info:
        app_operator.dispatch_webhook("http://destino/", "x" * 16, {"a": 1})
    assert isinstance(info.value.__cause__, requests.ConnectionError)
    assert "Causa: ConnectionError" in info.value.__notes__
