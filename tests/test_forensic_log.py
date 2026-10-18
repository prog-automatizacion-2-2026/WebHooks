"""Tests forenses de los logs JSON y la rotación Gzip.

Titular: Francisco (rama ``feature/franciscodiaz``).

TODO(Francisco): implementar con pytest según la consigna §4.2 y el
instructivo §1:

- abrir los ``*.log.gz`` con ``gzip`` y parsear cada línea como JSON;
- validar presencia de ``TraceId``, ``MessageId`` y la referencia a
  ``X-Webhook-Signature``;
- verificar que la descompresión no pierde datos (tamaño/contenido contra el
  original antes del gzip).
"""
