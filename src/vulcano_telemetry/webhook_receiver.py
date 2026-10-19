"""Servidor HTTP local receptor de webhooks (FastAPI sugerido).

Titular: Rene (rama ``feature/renechumacero``).

TODO(Rene): implementar según la consigna §4.2 y el instructivo §1:

- ``POST /webhook``: leer los bytes crudos con ``await request.body()``
  ANTES de cualquier ``.json()``; validar con ``verify_signature``;
  firma/timestamp inválidos → HTTP 401 (y 403 si la firma está presente pero
  es incorrecta); firma válida → HTTP 202 Accepted en menos de 100 ms y
  ``produce_event`` a SQS;
- secreto y URL de cola por ``os.getenv`` con defaults de prueba
  (documentados en el README) — sin secretos reales en el repo.
"""
