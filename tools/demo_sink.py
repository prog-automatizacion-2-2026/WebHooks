"""Destino de prueba para la demo: simula el endpoint del cliente.

Uso:
    python tools/demo_sink.py

Escucha en http://127.0.0.1:8001, imprime cada payload que recibe
(``RECIBIDO: {...}``) y responde 200 para que el despachador borre el mensaje.
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST = "127.0.0.1"
PORT = 8001


class Handler(BaseHTTPRequestHandler):
    """Recibe los POST del despachador y muestra el payload en la terminal."""

    def do_POST(self):
        """Lee el cuerpo, lo imprime y responde 200."""
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = body.decode("utf-8", "replace")
        print("RECIBIDO:", json.dumps(payload, ensure_ascii=False), flush=True)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok": true}')

    def log_message(self, *args):
        """Silencia el log de acceso por defecto para que solo se vea el payload."""


if __name__ == "__main__":
    print(f"Sink escuchando en http://{HOST}:{PORT}", flush=True)
    try:
        HTTPServer((HOST, PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print("Sink detenido.")
