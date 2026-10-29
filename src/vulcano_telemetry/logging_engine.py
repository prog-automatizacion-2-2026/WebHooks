"""Observabilidad: logs JSON asíncronos con rotación Gzip.

Titular: Francisco (rama ``feature/francisco-diaz``).

Implementa ``AsyncJSONFormatter`` (una línea JSON con timestamp ISO 8601 UTC,
campos ``TraceId``/``MessageId``/``WebhookId`` y extras), la rotación Gzip con
``gzip_rotator`` y el pipeline ``QueueHandler`` + ``QueueListener`` expuesto
por ``setup_vulcano_logging`` para el apagado ordenado del CLI.
"""
import logging
import logging.handlers
import json
import gzip
import os
import queue
import shutil
from datetime import datetime, timezone

class AsyncJSONFormatter(logging.Formatter):
    """Convierte los registros de log a formato estructurado JSON según consigna."""
    def format(self, record):
        log_record = {
            # Timestamp en ISO 8601 UTC estricto
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "logger": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
            "process_id": record.process,
            "thread_name": record.threadName,
        }
        
        # Capturar cualquier atributo pasado por 'extra' (TraceId, MessageId, etc.)
        for key, value in record.__dict__.items():
            if key not in ['args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename', 'funcName', 'levelname', 'levelno', 'lineno', 'message', 'module', 'msecs', 'msg', 'name', 'pathname', 'process', 'processName', 'relativeCreated', 'stack_info', 'thread', 'threadName', 'taskName']:
                log_record[key] = value

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

def gzip_rotator(source, dest):
    """Compresión con gzip y shutil.copyfileobj."""
    with open(source, 'rb') as f_in:
        with gzip.open(dest, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    os.remove(source)

def setup_vulcano_logging(log_filename="vulcano_events.log", max_bytes=2*1024*1024, backup_count=3):
    """Configura el pipeline QueueHandler + QueueListener."""
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

    log_queue = queue.Queue(-1)
    queue_handler = logging.handlers.QueueHandler(log_queue)
    listener = logging.handlers.QueueListener(log_queue, file_handler)
    
    logger.addHandler(queue_handler)
    return logger, listener