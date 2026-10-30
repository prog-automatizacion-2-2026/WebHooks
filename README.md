# VulcanoEventEngine — Webhooks HMAC, cola SQS y observabilidad asíncrona

TP-2 de **Programación para la Automatización II** (UPATECo) — Tec. Universitaria en Gestión de Infraestructura Cloud y DevOps.

Sistema de procesamiento de eventos de **Vulcano Pay**: recibe webhooks HTTP firmados (HMAC-SHA256), los encola en SQS de forma desacoplada y los despacha a los destinos de los clientes con reintentos y Dead Letter Queue. Todo con logs estructurados JSON no bloqueantes.

## Arquitectura

```mermaid
flowchart LR
    C["Cliente / pasarela"] -->|"POST /webhook + firma HMAC"| R["Receptor<br/>webhook_receiver.py"]
    R -->|"202 Accepted en menos de 100 ms"| C
    R -->|"produce_event()"| Q[("SQS: vulcano-events-queue")]
    Q -->|"consume_events() long polling"| D["Despachador<br/>app_operator.py"]
    D -->|"dispatch_webhook() POST firmado"| T["Endpoint destino"]
    D -.->|"entrega fallida: el mensaje no se borra"| Q
    Q -.->|"maxReceiveCount = 3"| DLQ[("SQS: vulcano-events-dlq")]
```

## Estructura del repositorio

```text
WebHooks/
├── src/
│   ├── vulcano_telemetry/
│   │   ├── __init__.py           # API pública del paquete
│   │   ├── exceptions.py         # excepciones semánticas
│   │   ├── sanitizer.py          # validadores para argparse
│   │   ├── core_sqs.py           # cliente Boto3 + productor/consumidor
│   │   ├── webhook_crypto.py     # HMAC-SHA256 (firma y verificación)
│   │   ├── webhook_receiver.py   # servidor HTTP receptor (FastAPI)
│   │   └── logging_engine.py     # logs JSON asíncronos + rotación Gzip
│   └── app_operator.py           # CLI: produce-sqs | start-receiver | start-dispatcher
├── tests/
│   ├── test_chaos.py             # firmas inválidas y mensajes venenosos
│   ├── test_forensic_log.py      # logs JSON, Gzip y serialización de ExceptionGroup
│   └── test_trazabilidad.py      # TraceId/MessageId/WebhookId de punta a punta
├── scripts/
│   └── setup_localstack.py       # crea las colas y la DLQ (idempotente)
├── tools/
│   ├── send_webhook.py           # envía un webhook firmado de prueba (202 / 401)
│   └── demo_sink.py              # destino de prueba que imprime lo que recibe
├── requirements.txt
├── pytest.ini
└── README.md
```

## Requisitos

- Python >= 3.14 (`except*`, PEP 765)
- Docker (para LocalStack)
- Git

## Instalación

```bash
git clone https://github.com/prog-automatizacion-2-2026/WebHooks.git
cd WebHooks
python -m venv .venv
# Windows: .venv\Scripts\activate  |  Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

LocalStack y colas:

```bash
docker run --rm -d -p 4566:4566 --name vulcano-localstack localstack/localstack:3
python scripts/setup_localstack.py
```

## Variables de entorno

| Variable | Default | Uso |
|---|---|---|
| `VULCANO_AWS_ENDPOINT` | `http://localhost:4566` | Endpoint de LocalStack para Boto3 |
| `VULCANO_QUEUE_URL` | `http://localhost:4566/000000000000/vulcano-events-queue` | URL de la cola de eventos |
| `VULCANO_WEBHOOK_SECRET` | `vulcano-dev-secret-2026` | Clave HMAC de desarrollo (mínimo 16 caracteres) |

Sin secretos reales en el repositorio: estos valores son solo para desarrollo local.

## Uso (CLI)

```bash
python src/app_operator.py --help
python src/app_operator.py start-receiver     # servidor receptor (202 / 401)
python src/app_operator.py produce-sqs        # publica un evento de prueba
python src/app_operator.py start-dispatcher   # consume SQS y despacha
```

Flags globales: `--queue`, `--wait-time`, `--url`, `--secret` (validados por `sanitizer.py`).

## Demo local de punta a punta

Con LocalStack levantado y las colas creadas, en cuatro terminales (venv activado):

```bash
python src/app_operator.py start-receiver                                    # T1: receptor en :8000
python tools/demo_sink.py                                                    # T2: destino en :8001
python tools/send_webhook.py && python tools/send_webhook.py --invalid       # T3: 202 y 401
python src/app_operator.py start-dispatcher --url http://127.0.0.1:8001/     # T3: entrega al destino
```

El sink imprime `RECIBIDO: {"event": "payment_completed", "amount": 1500}` y la terminal del despachador muestra el mismo `TraceId` que devolvió el `202`. Pasar siempre `--url`: el valor por defecto apunta al propio receptor.

## Trazabilidad y logs

Cada evento lleva un **TraceId**: lo genera el receptor (o lo toma del header `X-Trace-Id` si viene) y lo devuelve en la respuesta `202`. Viaja como atributo del mensaje SQS (`TraceId`, `EventTopic` y `Timestamp`) y el despachador lo reenvía al destino en el header `X-Trace-Id`.

Cada línea de `vulcano_events.log` es un JSON con `timestamp` (ISO 8601 UTC), `logger`, `level`, `message`, `process_id`, `thread_name`, `TraceId`, `MessageId` y `WebhookId`. Los errores se guardan en el campo `exception`, con el `ExceptionGroup` completo: subexcepciones, notas de `add_note()` y causa encadenada. El CLI también muestra una versión corta en la terminal.

Para seguir un evento: `Select-String vulcano_events.log -Pattern <trace_id>` (PowerShell) o `grep <trace_id> vulcano_events.log`.

## Tests

```bash
python -m pytest
```

`test_poison_message_derivation_to_dlq` usa LocalStack si está levantado (si no, se omite) y publica un mensaje de prueba en la cola principal.

## Equipo y roles

| Integrante | Rol | Módulos |
|---|---|---|
| Ariel (SM) | Integración, despachador y CLI | `app_operator.py`, `__init__.py`, estructura, README |
| Clelia | Robustez de entradas + mensajería SQS | `exceptions.py`, `sanitizer.py`, `core_sqs.py`, `scripts/` |
| Rene | Seguridad HMAC + receptor + caos | `webhook_crypto.py`, `webhook_receiver.py`, `tests/test_chaos.py` |
| Francisco | Observabilidad + forense | `logging_engine.py`, `tests/test_forensic_log.py` |

Flujo de trabajo: `main` (releases) / `develop` (integración) / una rama `feature/nombreapellido` por integrante; todo entra por Pull Request con revisión (la aprobación no bloquea el merge).
