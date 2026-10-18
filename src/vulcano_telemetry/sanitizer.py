"""Sanitizadores declarativos para argparse.

Titular: Clelia (rama ``feature/cleliaalvespinto``).

TODO(Clelia): implementar según la consigna §4.2 y el instructivo §1; cada
callable lanza ``argparse.ArgumentTypeError`` con mensaje claro:

- ``parse_queue_name(value)``: regex ``^vulcano-[a-z0-9-]+-queue$``;
- ``parse_wait_time(value)``: entero entre 1 y 20;
- ``parse_webhook_url(value)``: esquema http/https y netloc
  (``urllib.parse.urlparse``);
- ``parse_secret_key(value)``: mínimo 16 caracteres.
"""
