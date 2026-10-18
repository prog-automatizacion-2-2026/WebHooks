"""Creación idempotente de las colas SQS en LocalStack.

Titular: Clelia (rama ``feature/cleliaalvespinto``).

TODO(Clelia): implementar según la consigna §4.2 y el instructivo §1: crear
primero ``vulcano-events-dlq`` y después ``vulcano-events-queue`` con
``RedrivePolicy`` (``maxReceiveCount=3`` + ARN de la DLQ); si ya existen, no
falla.
"""
