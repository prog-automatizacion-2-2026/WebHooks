"""Excepciones semánticas de VulcanoEventEngine.

Titular: Clelia Alves s(rama feature/cleliaalvespinto).

Implementa la jerarquía completa según la consigna 64.2 y el instructivo S1.
Todas heredan de Exception y cuentan con su docstring.
"""


class VulcanoError(Exception):
    """Excepción base para todos los errores del dominio VulcanoEventEngine."""
    pass


# Dominio SQS
class SQSConnectionError(VulcanoError):
    """Se lanza cuando no se puede establecer conexión con el servicio SQS."""
    pass


class QueueTimeoutError(VulcanoError):
    """Se lanza cuando se agota el tiempo de espera al intentar acceder a una cola."""
    pass


class CorruptedMessageError(VulcanoError):
    """Se lanza cuando un mensaje recibido tiene un formato o contenido inválido."""
    pass


# Dominio Webhook
class WebhookSignatureError(VulcanoError):
    """Se lanza cuando la firma del webhook no coincide con la esperada."""
    pass


class WebhookTimestampError(VulcanoError):
    """Se lanza cuando la marca de tiempo del mensaje está fuera del rango permitido."""
    pass


class WebhookDeliveryError(VulcanoError):
    """Se lanza cuando ocurre un error durante la entrega del mensaje al receptor."""
    pass