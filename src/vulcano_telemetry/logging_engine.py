"""Observabilidad: logs JSON asíncronos con rotación Gzip.

Titular: Francisco (rama ``feature/francisco-diaz``).

Implementa ``AsyncJSONFormatter`` (una línea JSON con timestamp ISO 8601 UTC,
campos ``TraceId``/``MessageId``/``WebhookId`` y extras), la serialización
recursiva de excepciones (``ExceptionGroup``, notas de ``add_note`` y causa
encadenada), la rotación Gzip con ``gzip_rotator`` y el pipeline
``QueueHandler`` + ``QueueListener`` expuesto por ``setup_vulcano_logging``
para el apagado ordenado del CLI.
"""
import copy
import gzip
import json
import logging
import logging.handlers
import os
import queue
import re
import shutil
import sys
import traceback
from datetime import datetime, timezone

# Formato aceptado para un TraceId que llega desde afuera (header o mensaje).
_TRACE_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,64}")


def is_valid_trace_id(value):
    """True si ``value`` es un TraceId seguro para logs y headers HTTP."""
    return isinstance(value, str) and _TRACE_ID_PATTERN.fullmatch(value) is not None


# Campos de trazabilidad que siempre aparecen en cada línea (null si no aplica).
TRACE_FIELDS = ("TraceId", "MessageId", "WebhookId")

# Atributos estándar de LogRecord que no se copian como "extra".
_RESERVED_ATTRS = frozenset({
    "args", "asctime", "created", "exc_info", "exc_text", "filename",
    "funcName", "levelname", "levelno", "lineno", "message", "module",
    "msecs", "msg", "name", "pathname", "process", "processName",
    "relativeCreated", "stack_info", "thread", "threadName", "taskName",
})


def serialize_exception(exc, include_traceback=True):
    """Convierte una excepción en un dict JSON-serializable.

    Recorre ``ExceptionGroup`` (``.exceptions``) de forma recursiva, incluye
    las notas de ``add_note()`` (``__notes__``) y la causa (``__cause__``).
    La traza completa se agrega solo en el nivel superior para no repetirla.
    """
    data = {
        "type": type(exc).__name__,
        "message": str(exc),
        "notes": list(getattr(exc, "__notes__", [])),
    }
    if isinstance(exc, BaseExceptionGroup):
        data["exceptions"] = [
            serialize_exception(sub, include_traceback=False) for sub in exc.exceptions
        ]
    if exc.__cause__ is not None:
        data["cause"] = serialize_exception(exc.__cause__, include_traceback=False)
    if include_traceback:
        data["traceback"] = "".join(traceback.format_exception(exc))
    return data


class AsyncJSONFormatter(logging.Formatter):
    """Convierte los registros de log a formato estructurado JSON según consigna."""

    def format(self, record):
        log_record = {
            # ISO 8601 UTC del momento en que se generó el evento (no de la escritura)
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "logger": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
            "process_id": record.process,
            "thread_name": record.threadName,
        }
        for field in TRACE_FIELDS:
            log_record[field] = getattr(record, field, None)

        # Cualquier otro atributo pasado por 'extra'
        for key, value in record.__dict__.items():
            if key not in _RESERVED_ATTRS and key not in log_record:
                log_record[key] = value

        if record.exc_info and record.exc_info[1] is not None:
            log_record["exception"] = serialize_exception(record.exc_info[1])
        return json.dumps(log_record, default=str)


class ConsoleFormatter(logging.Formatter):
    """Formato corto para la terminal: hora, nivel, mensaje y TraceId si existe."""

    def __init__(self):
        super().__init__("%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")

    def format(self, record):
        text = super().format(record)
        trace_id = getattr(record, "TraceId", None)
        if not trace_id:
            return text
        # Escapa caracteres de control para que no se puedan falsificar líneas
        safe = str(trace_id).encode("unicode_escape").decode("ascii")[:64]
        return f"{text} [TraceId={safe}]"


class VulcanoQueueHandler(logging.handlers.QueueHandler):
    """QueueHandler que conserva la excepción estructurada.

    El ``QueueHandler`` estándar descarta ``exc_info`` antes de encolar. Acá la
    excepción se serializa en el hilo que la generó (donde el objeto sigue vivo)
    y viaja como atributo ``exception`` hasta el formatter JSON.
    """

    def prepare(self, record):
        record = copy.copy(record)
        if record.exc_info and record.exc_info[1] is not None:
            record.exception = serialize_exception(record.exc_info[1])
        record.message = record.getMessage()
        record.msg = record.message
        record.args = None
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return record


def gzip_rotator(source, dest):
    """Compresión con gzip y shutil.copyfileobj."""
    with open(source, 'rb') as f_in:
        with gzip.open(dest, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    os.remove(source)


def setup_vulcano_logging(
    log_filename="vulcano_events.log",
    max_bytes=2 * 1024 * 1024,
    backup_count=3,
    console=False,
):
    """Configura el pipeline QueueHandler + QueueListener.

    Con ``console=True`` el listener también escribe una versión corta en la
    terminal (stderr), útil para seguir el flujo en vivo.
    """
    logger = logging.getLogger("vulcano_telemetry")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger, None

    file_handler = logging.handlers.RotatingFileHandler(
        log_filename, maxBytes=max_bytes, backupCount=backup_count
    )
    file_handler.setFormatter(AsyncJSONFormatter())
    file_handler.rotator = gzip_rotator
    file_handler.namer = lambda name: name + ".gz"

    handlers = [file_handler]
    if console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(ConsoleFormatter())
        handlers.append(console_handler)

    log_queue = queue.Queue(-1)
    queue_handler = VulcanoQueueHandler(log_queue)
    listener = logging.handlers.QueueListener(log_queue, *handlers)

    logger.addHandler(queue_handler)
    return logger, listener
