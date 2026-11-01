"""
Лабораторная работа №3, задание 1.
Мониторинг в распределённых системах: трассировка Flask-приложения
средствами OpenTelemetry с экспортом в Jaeger (протокол OTLP).

Приложение демонстрирует:
  * автоматическую инструментацию Flask (входящие HTTP-запросы);
  * автоматическую инструментацию requests (исходящие HTTP-вызовы)
    вместе с распространением контекста W3C Trace Context;
  * ручное создание спанов (tracer.start_as_current_span);
  * атрибуты и события спанов;
  * экспорт спанов в Jaeger через OTLP gRPC.
"""

import os

import flask
import requests
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# ---------------------------------------------------------------------------
# 1. Параметры окружения
# ---------------------------------------------------------------------------
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "lab3-flask-app")
OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
SEND_URL = os.getenv("SEND_URL", "http://127.0.0.1:5000/send")

# ---------------------------------------------------------------------------
# 2. Ресурс: атрибуты, описывающие источник телеметрии
# ---------------------------------------------------------------------------
resource = Resource.create(
    {
        "service.name": SERVICE_NAME,
        "service.version": "1.0.0",
        "deployment.environment": os.getenv("DEPLOYMENT_ENV", "lab"),
    }
)

# ---------------------------------------------------------------------------
# 3. Провайдер трассировки + экспортёр OTLP -> Jaeger
# ---------------------------------------------------------------------------
provider = TracerProvider(resource=resource)
provider.add_span_processor(
    BatchSpanProcessor(
        OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=True)
    )
)
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)

# ---------------------------------------------------------------------------
# 4. Приложение Flask и автоматическая инструментация
# ---------------------------------------------------------------------------
app = flask.Flask(__name__)
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()


@app.route("/")
def hello():
    """Корневой маршрут: создаёт ручной спан и вызывает /send."""
    with tracer.start_as_current_span("hello") as span:
        span.set_attribute("hello.target", SEND_URL)
        span.add_event("hello.started")

        # Исходящий вызов. Благодаря RequestsInstrumentor создаётся
        # дочерний клиентский спан и передаётся заголовок traceparent,
        # поэтому спан /send попадёт в то же дерево трассировки.
        response = requests.get(SEND_URL, timeout=5)

        span.set_attribute("hello.send_status_code", response.status_code)
        span.add_event("hello.finished")

    return "Hello, World!\n"


@app.route("/send")
def send():
    """Вспомогательный маршрут, имитирующий отправку уведомления."""
    with tracer.start_as_current_span("send-notification") as span:
        span.set_attribute("notification.channel", "console")
        span.add_event("notification.sent", {"recipient": "student"})
    return flask.jsonify(status="ok", message="Notification sent")


@app.route("/health")
def health():
    """Проверка живости контейнера."""
    return flask.jsonify(status="up")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
