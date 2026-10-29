"""
Cliente SQS — productor y consumidor de eventos.
Usa Boto3 contra LocalStack como broker de mensajería.
"""

import json
import boto3
from botocore.exceptions import ClientError
from typing import Optional, Dict, Any
from vulcano_telemetry.exceptions import (
    SQSConnectionError,
    CorruptedMessageError,
)


def get_sqs_client(endpoint_url: str = "http://localhost:4566"):
    """
    Crea y devuelve un cliente SQS configurado para LocalStack.
    Region: us-east-1 | Credenciales simuladas: test/test
    """
    return boto3.client(
        "sqs",
        region_name="us-east-1",
        endpoint_url=endpoint_url,
        aws_access_key_id="test",
        aws_secret_access_key="test"
    )


def produce_event(
    sqs_client,
    queue_url: str,
    event_data: Dict[str, Any]
) -> str:
    """
    Envía un evento a la cola SQS.
    Agrega atributos de mensaje: TraceId, EventTopic y Timestamp.
    Devuelve el MessageId asignado por SQS[span_1](start_span)[span_1](end_span).
    """
    body = json.dumps(event_data, ensure_ascii=False)

    message_attributes = {}
    if "trace_id" in event_data:
        message_attributes["TraceId"] = {
            "StringValue": event_data["trace_id"],
            "DataType": "String"
        }
    if "topic" in event_data:
        message_attributes["EventTopic"] = {
            "StringValue": event_data["topic"],
            "DataType": "String"
        }
    if "timestamp" in event_data:
        message_attributes["Timestamp"] = {
            "StringValue": str(event_data["timestamp"]),
            "DataType": "String"
        }

    response = sqs_client.send_message(
        QueueUrl=queue_url,
        MessageBody=body,
        MessageAttributes=message_attributes
    )
    return response["MessageId"]


def consume_events(
    sqs_client,
    queue_url: str,
    wait_time: int = 10,
    max_messages: int = 5
):
    """
    Consume mensajes de la cola usando Long Polling.
    Solo borra el mensaje tras procesamiento exitoso[span_2](start_span)[span_2](end_span).
    Yielda cada mensaje parseado como diccionario Python.
    """
    try:
        response = sqs_client.receive_message(
            QueueUrl=queue_url,
            WaitTimeSeconds=wait_time,
            MaxNumberOfMessages=max_messages,
            VisibilityTimeout=30,  # <-- Agregado según requerimiento del instructivo[span_3](start_span)[span_3](end_span)
            AttributeNames=["All"],
            MessageAttributeNames=["All"]
        )
    except ClientError as e:
        err = SQSConnectionError(f"Error al conectar o leer desde la cola: {e}")
        err.add_note(f"Endpoint: {sqs_client._endpoint}")  # <-- Uso del método oficial .add_note()[span_4](start_span)[span_4](end_span)
        raise err from e

    if "Messages" not in response:
        return

    for msg in response["Messages"]:
        receipt_handle = msg["ReceiptHandle"]
        message_id = msg.get("MessageId", "unknown")

        try:
            body = json.loads(msg["Body"])
        except json.JSONDecodeError as e:
            corrupted_err = CorruptedMessageError(
                f"Mensaje {message_id} no contiene JSON válido"
            )
            corrupted_err.add_note(f"Contenido: {msg['Body'][:100]}...")  # <-- Uso del método oficial .add_note()[span_5](start_span)[span_5](end_span)
            raise corrupted_err from e

        try:
            yield {
                "message_id": message_id,
                "body": body,
                "receipt_handle": receipt_handle,
                "attributes": msg.get("MessageAttributes", {})
            }
            sqs_client.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle
            )
        except Exception:
            raise
