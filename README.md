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
│   └── test_forensic_log.py      # logs JSON y descompresión Gzip
├── scripts/
│   └── setup_localstack.py       # crea las colas y la DLQ (idempotente)
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
docker run --rm -d -p 4566:4566 --name vulcano-localstack localstack/localstack
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

## Tests

```bash
python -m pytest
```

## Equipo y roles

| Integrante | Rol | Módulos |
|---|---|---|
| Ariel (SM) | Integración, despachador y CLI | `app_operator.py`, `__init__.py`, estructura, README |
| Clelia | Robustez de entradas + mensajería SQS | `exceptions.py`, `sanitizer.py`, `core_sqs.py`, `scripts/` |
| Rene | Seguridad HMAC + receptor + caos | `webhook_crypto.py`, `webhook_receiver.py`, `tests/test_chaos.py` |
| Francisco | Observabilidad + forense | `logging_engine.py`, `tests/test_forensic_log.py` |

Flujo de trabajo: `main` (releases) / `develop` (integración) / una rama `feature/nombreapellido` por integrante; todo entra por Pull Request con 1 aprobación.
