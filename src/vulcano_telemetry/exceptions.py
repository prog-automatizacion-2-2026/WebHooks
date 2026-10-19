"""Excepciones semánticas de VulcanoEventEngine.

Titular: Clelia (rama ``feature/cleliaalvespinto``).

TODO(Clelia): implementar la jerarquía completa según la consigna §4.2 y el
instructivo §1 (todas heredan de ``Exception`` y con docstring):

- ``VulcanoError`` (base);
- dominio SQS: ``SQSConnectionError``, ``QueueTimeoutError``,
  ``CorruptedMessageError``;
- dominio Webhook: ``WebhookSignatureError``, ``WebhookTimestampError``,
  ``WebhookDeliveryError``.
"""
