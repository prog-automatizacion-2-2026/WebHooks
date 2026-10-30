"""
Script de inicialización de colas en LocalStack.
Crea la DLQ primero y luego la cola principal con su política de reintento.
Es idempotente: si las colas ya existen, no falla.
"""

import json

import boto3
from botocore.exceptions import ClientError


ENDPOINT_URL = "http://localhost:4566"
REGION = "us-east-1"

QUEUE_NAME = "vulcano-events-queue"
DLQ_NAME = "vulcano-events-dlq"
MAX_RECEIVE_COUNT = 3


def get_client():
    """Devuelve cliente SQS apuntando a LocalStack."""
    return boto3.client(
        "sqs",
        region_name=REGION,
        endpoint_url=ENDPOINT_URL,
        aws_access_key_id="test",
        aws_secret_access_key="test"
    )


def get_queue_url(sqs_client, queue_name: str):
    """Obtiene la URL de una cola o devuelve None si no existe."""
    try:
        response = sqs_client.get_queue_url(QueueName=queue_name)
        return response["QueueUrl"]
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == "AWS.SimpleQueueService.NonExistentQueue":
            return None
        raise


def get_queue_arn(sqs_client, queue_url: str) -> str:
    """Obtiene el ARN de una cola a partir de su URL."""
    attrs = sqs_client.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=["QueueArn"]
    )
    return attrs["Attributes"]["QueueArn"]


def create_dlq(sqs_client):
    """Crea la Dead Letter Queue si no existe y devuelve su URL."""
    existing_url = get_queue_url(sqs_client, DLQ_NAME)
    if existing_url:
        print(f"DLQ '{DLQ_NAME}' ya existe: {existing_url}")
        return existing_url

    response = sqs_client.create_queue(QueueName=DLQ_NAME)
    dlq_url = response["QueueUrl"]
    print(f"DLQ creada: {dlq_url}")
    return dlq_url


def create_main_queue(sqs_client, dlq_arn: str):
    """Crea la cola principal con la política de Redrive hacia la DLQ."""
    existing_url = get_queue_url(sqs_client, QUEUE_NAME)
    if existing_url:
        print(f"Cola principal '{QUEUE_NAME}' ya existe: {existing_url}")
        return existing_url

    redrive_policy = {
        "maxReceiveCount": str(MAX_RECEIVE_COUNT),
        "deadLetterTargetArn": dlq_arn
    }

    response = sqs_client.create_queue(
        QueueName=QUEUE_NAME,
        Attributes={
            "RedrivePolicy": json.dumps(redrive_policy)
        }
    )
    queue_url = response["QueueUrl"]
    print(f"Cola principal creada: {queue_url}")
    print(f"   DLQ asociada: {DLQ_NAME} (max {MAX_RECEIVE_COUNT} intentos)")
    return queue_url


def main():
    print("Inicializando colas en LocalStack...")
    print(f"Endpoint: {ENDPOINT_URL}")

    sqs_client = get_client()

    dlq_url = create_dlq(sqs_client)
    dlq_arn = get_queue_arn(sqs_client, dlq_url)

    create_main_queue(sqs_client, dlq_arn)

    print("Listo. Ambas colas están disponibles.")
    print("\nVerificar con:")
    print("aws --endpoint-url=http://localhost:4566 sqs list-queues")


if __name__ == "__main__":
    main()
