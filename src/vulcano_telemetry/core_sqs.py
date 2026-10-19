"""Cliente Boto3 y productor/consumidor SQS contra LocalStack.

Titular: Clelia (rama ``feature/cleliaalvespinto``).

TODO(Clelia): implementar según la consigna §4.2 y el instructivo §1:

- ``get_sqs_client(endpoint_url="http://localhost:4566")``: región
  ``us-east-1`` y credenciales simuladas ``test``/``test``;
- ``produce_event(sqs_client, queue_url, event_data)``: ``send_message`` con
  JSON en el body y ``MessageAttributes`` (``TraceId``, ``EventTopic``,
  ``Timestamp``); devuelve el ``MessageId``;
- ``consume_events(sqs_client, queue_url, wait_time=10, max_messages=5)``:
  long polling con ``WaitTimeSeconds`` y ``VisibilityTimeout``;
  ``delete_message`` solo tras procesamiento exitoso;
  ``botocore.exceptions.ClientError`` → ``SQSConnectionError`` encadenada
  (``raise ... from ...``) con contexto vía ``add_note()``;
  body no-JSON → ``CorruptedMessageError``.
"""
