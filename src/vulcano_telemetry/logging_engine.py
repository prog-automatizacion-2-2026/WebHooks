"""Observabilidad: logs JSON asíncronos con rotación Gzip.

Titular: Francisco (rama ``feature/franciscodiaz``).

TODO(Francisco): implementar según la consigna §4.2 y el instructivo §1:

- ``AsyncJSONFormatter(logging.Formatter)``: una línea JSON con ``timestamp``
  ISO 8601 UTC estricto, ``logger``, ``level``, ``message``, ``process_id``,
  ``thread_name`` y los campos ``TraceId``, ``MessageId``, ``WebhookId`` y
  cualquier atributo pasado por ``extra``; serialización recursiva de
  ``ExceptionGroup`` (``.exceptions``), notas de ``add_note()`` (``__notes__``)
  y trazas (``formatException``);
- ``gzip_namer(default_name)`` y ``gzip_rotator(source, dest)``: compresión
  con ``gzip`` + ``shutil.copyfileobj`` y borrado del original;
- ``setup_vulcano_logging(log_filename="vulcano_events.log")``: pipeline
  obligatorio ``QueueHandler`` + ``QueueListener``, ``RotatingFileHandler`` de
  2 MB con 3 backups y ``namer``/``rotator`` a ``.gz``; deja accesible el
  listener para el apagado ordenado del CLI.
"""
