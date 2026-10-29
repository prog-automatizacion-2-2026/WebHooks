"""
Validadores sanitizadores para argumentos de línea de comandos.
Cada función lanza argparse.ArgumentTypeError si el valor no es válido.
"""

import argparse
import re
from urllib.parse import urlparse


def parse_queue_name(value: str) -> str:
    """
    Valida que el nombre de la cola cumpla el formato:
    ^vulcano-[a-z0-9-]+-queue$
    """
    pattern = r'^vulcano-[a-z0-9-]+-queue$'
    if not re.fullmatch(pattern, value):
        raise argparse.ArgumentTypeError(
            f"Nombre de cola inválido: '{value}'. "
            "Debe empezar con 'vulcano-', contener solo minúsculas, números y guiones, "
            "y terminar con '-queue'. Ej: vulcano-eventos-queue"
        )
    return value


def parse_wait_time(value: str) -> int:
    """Valida que el tiempo de espera sea un entero entre 1 y 20 segundos."""
    try:
        wait_time = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Tiempo de espera inválido: '{value}'. Debe ser un número entero."
        )
    if not (1 <= wait_time <= 20):
        raise argparse.ArgumentTypeError(
            f"Tiempo de espera fuera de rango: {wait_time}. "
            "Debe estar entre 1 y 20 segundos."
        )
    return wait_time


def parse_webhook_url(value: str) -> str:
    """
    Valida que la URL tenga esquema http/https y un dominio presente.
    """
    parsed = urlparse(value)
    if not parsed.scheme or parsed.scheme not in ('http', 'https'):
        raise argparse.ArgumentTypeError(
            f"URL inválida: '{value}'. Debe usar esquema http:// o https://"
        )
    if not parsed.netloc:
        raise argparse.ArgumentTypeError(
            f"URL inválida: '{value}'. Falta el dominio o dirección."
        )
    return value


def parse_secret_key(value: str) -> str:
    """Valida que la clave secreta tenga al menos 16 caracteres."""
    if len(value) < 16:
        raise argparse.ArgumentTypeError(
            f"Clave secreta demasiado corta: {len(value)} caracteres. "
            "Mínimo requerido: 16 caracteres."
        )
    return value
