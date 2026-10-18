"""Punto de entrada CLI de VulcanoEventEngine.

Titular: Ariel (rama ``feature/arielfernandez``).

TODO(Ariel): implementar según la consigna §4.2 y el instructivo §1:

- ``build_parser()``: flags globales validados con los sanitizadores de Clelia
  (``--queue``, ``--wait-time``, ``--url``, ``--secret``) y subcomandos
  ``produce-sqs`` | ``start-receiver`` | ``start-dispatcher``;
- ``dispatch_webhook(target_url, secret, payload_dict)``: firma con
  ``generate_signature`` (Rene) y POST con header ``X-Webhook-Signature``; si
  el POST falla lanza ``WebhookDeliveryError`` y NO borra el mensaje de SQS
  (así SQS reintenta y, tras ``maxReceiveCount``, cae a la DLQ);
- ``main()``: captura quirúrgica con ``try / except*`` de
  ``WebhookSignatureError``, ``WebhookTimestampError`` y ``SQSConnectionError``;
  ``finally`` de apagado ordenado que libera el ``QueueListener`` (prohibido
  ``return``/``break``/``continue`` dentro del ``finally`` — PEP 765).
"""
