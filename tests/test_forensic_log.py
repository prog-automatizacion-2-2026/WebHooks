"""Tests forenses de los logs JSON y la rotación Gzip.

Titular: Francisco (rama ``feature/francisco-diaz``).

Cubren la apertura de ``*.log.gz``, el parseo de cada línea como JSON, la
presencia de ``TraceId``/``MessageId`` y la integridad de la descompresión.
"""
import os
import json
import gzip
import time
from src.vulcano_telemetry.logging_engine import setup_vulcano_logging

def test_json_format_and_gzip_rotation(tmp_path):
    log_file = tmp_path / "test_vulcano.log"
    # Configuramos un log muy pequeño (100 bytes) para que rote rápido
    logger, listener = setup_vulcano_logging(str(log_file), max_bytes=100)
    listener.start()
    
    # 1. Inyectamos un log con los datos extra requeridos por el TP-2
    test_extras = {
        "TraceId": "trace-123",
        "MessageId": "msg-456",
        "X-Webhook-Signature": "sha256=abcd"
    }
    logger.info("Prueba de descompresión", extra=test_extras)
    time.sleep(0.1) # Damos tiempo al QueueListener asíncrono
    
    # 2. Leemos el archivo original antes de que se comprima
    with open(log_file, 'r') as f:
        original_content = f.read()
        original_size = len(original_content)
        
    # 3. Forzamos la rotación Gzip manualmente
    file_handler = listener.handlers[0]
    file_handler.doRollover()
    time.sleep(0.1)
    listener.stop()
    
    gz_file = f"{log_file}.1.gz"
    assert os.path.exists(gz_file), "El archivo Gzip rotado no se creó"
    
    # 4. Validaciones forenses (Consigna §1)
    with gzip.open(gz_file, 'rt') as f:
        uncompressed_content = f.read()
        
        # Verificar que la descompresión no pierde datos (tamaño/contenido)
        assert len(uncompressed_content) == original_size, "Pérdida de tamaño al descomprimir"
        assert uncompressed_content == original_content, "El contenido cambió al descomprimir"
        
        # Parsear JSON y validar presencia de campos específicos
        log_data = json.loads(uncompressed_content.strip())
        assert "TraceId" in log_data, "Falta TraceId en el JSON"
        assert "MessageId" in log_data, "Falta MessageId en el JSON"
        assert "X-Webhook-Signature" in log_data, "Falta X-Webhook-Signature en el JSON"

# --- Serialización de excepciones (ExceptionGroup + add_note) ---------------
import logging
import queue as _queue

from src.vulcano_telemetry.logging_engine import (
    AsyncJSONFormatter,
    VulcanoQueueHandler,
    serialize_exception,
)


def _make_group():
    """Arma un ExceptionGroup con notas y una causa encadenada."""
    try:
        raise ConnectionError("destino caído")
    except ConnectionError as cause:
        delivery = RuntimeError("Falló la entrega")
        delivery.__cause__ = cause
        delivery.add_note("TraceId=trace-789")
    group = ExceptionGroup("errores del lote", [delivery, ValueError("payload corrupto")])
    group.add_note("lote 1 de 1")
    return group


def _record_with(exc):
    return logging.LogRecord(
        "vulcano_telemetry", logging.ERROR, __file__, 1, "Falla agrupada", None,
        (type(exc), exc, exc.__traceback__),
    )


def test_exception_group_serialization_includes_notes_and_cause():
    data = serialize_exception(_make_group())
    assert data["type"] == "ExceptionGroup"
    assert data["notes"] == ["lote 1 de 1"]
    assert [sub["type"] for sub in data["exceptions"]] == ["RuntimeError", "ValueError"]
    assert data["exceptions"][0]["notes"] == ["TraceId=trace-789"]
    assert data["exceptions"][0]["cause"]["type"] == "ConnectionError"
    assert "traceback" in data and "traceback" not in data["exceptions"][0]


def test_formatter_writes_exception_and_trace_fields():
    line = json.loads(AsyncJSONFormatter().format(_record_with(_make_group())))
    assert line["exception"]["type"] == "ExceptionGroup"
    # Los campos de trazabilidad siempre existen, aunque no se hayan pasado
    assert {"TraceId", "MessageId", "WebhookId"} <= line.keys()


def test_queue_handler_keeps_exception_through_the_queue():
    """El QueueHandler estándar pierde exc_info; el de Vulcano lo conserva."""
    handler = VulcanoQueueHandler(_queue.Queue())
    prepared = handler.prepare(_record_with(_make_group()))
    assert prepared.exc_info is None
    line = json.loads(AsyncJSONFormatter().format(prepared))
    assert line["message"] == "Falla agrupada"
    assert line["exception"]["exceptions"][0]["notes"] == ["TraceId=trace-789"]
