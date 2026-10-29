"""Tests de caos: firmas inválidas y mensajes venenosos.

Titular: Rene (rama ``feature/renechumacero``).

TODO(Rene): implementar con pytest según la consigna §4.2 y el instructivo §1:

- webhooks con firma alterada o clave incorrecta → respuesta 401/403;
- webhook con timestamp de hace 1 hora → rechazo por
  ``WebhookTimestampError``;
- mensaje venenoso publicado a SQS → verificar que termina en
  ``vulcano-events-dlq`` (``ApproximateNumberOfMessages``).
"""
