# Отчет по лабораторной работе №3 «Мониторинг в распределённых системах»

**Выполнил(а):** Чжао Аофэй, группа 13
**Дисциплина:** Непрерывная интеграция и сборка программного обеспечения
**Вариант:** группа 13 — задание 1

## 1. Цель работы

Изучение средств мониторинга для сбора и обработки телеметрии приложений и настройка системы, в которой данные метрик, журналов и трассировок собираются для микросервисного приложения на языке Python.

Задачи работы:

1. подготовить приложение на Python к анализу трассировки с помощью Jaeger;
2. упаковать приложение в образ Docker и поднимать на его основе контейнер, используя Docker Compose;
3. обеспечить приложение механизмами экспортирования телеметрии в Jaeger, Prometheus и Grafana;
4. самостоятельно выполнить сборку метрик, трассировки и журналов по заданию.

## 2. Вариант задания

Согласно критериям оценивания методических указаний: «для групп 10–12 выполнить все 3 задания, для группы 13 — задание 1».

Для группы 13 выполняется **задание 1 «Подключение инструментов и библиотек OpenTelemetry и настройка трассировки приложения»**: приложение на Flask инструментируется средствами OpenTelemetry, спаны экспортируются по протоколу OTLP в Jaeger, всё разворачивается через Docker Compose в каталоге `task1`.

## 3. Краткие теоретические сведения

**Метрики, журналы и трассировки (MLT)** — три компонента наблюдаемости:

- **метрики** — числовые показатели использования ресурсов и работы системы (загрузка CPU, объём диска, пропускная способность, количество запросов, задержки);
- **журналы (логи)** — дискретные события, записываемые работающим ПО (ошибки времени выполнения, обращения пользователей, критические сбои);
- **трассировки** — путь выполнения запроса через компоненты распределённой системы с указанием времени обработки на каждом узле.

**OpenTelemetry (OTel)** — открытая платформа наблюдаемости (проект CNCF), предоставляющая спецификацию, API, SDK, инструментальные библиотеки и экспортёры для сбора метрик, журналов и трассировок. Поддерживает Java, Python, Go, Ruby, C++, JavaScript и другие языки.

Инструменты стека мониторинга, используемые в работе:

| Инструмент | Назначение |
|---|---|
| OpenTelemetry SDK | генерация и экспорт телеметрии из приложения |
| Jaeger | сбор, хранение и визуализация трассировок |
| Prometheus | сбор и хранение метрик (pull-модель) |
| Grafana | единая панель визуализации MLT |
| Promtail + Loki | сбор и агрегация журналов |

В данной работе (задание 1) используется связка **OpenTelemetry SDK → OTLP → Jaeger**.

## 4. Ход выполнения

### Шаг 1. Создание приложения на Python

Создано Flask-приложение `task1/app.py` с тремя маршрутами:

| Маршрут | Назначение |
|---|---|
| `/` | корневой маршрут: создаёт ручной спан `hello` и выполняет исходящий HTTP-вызов `/send` |
| `/send` | имитация отправки уведомления, ручной спан `send-notification` |
| `/health` | проверка живости контейнера (исключена из трассировки) |

Исходящий вызов `/` → `/send` позволяет продемонстрировать распространение контекста трассировки: клиентский и серверный спаны попадают в одно дерево.

### Шаг 2. Установка инструментов и библиотек OpenTelemetry

Зависимости зафиксированы в `task1/requirements.txt`:

```text
Flask==3.1.0
requests==2.32.3
opentelemetry-api==1.29.0
opentelemetry-sdk==1.29.0
opentelemetry-exporter-otlp-proto-grpc==1.29.0
opentelemetry-instrumentation-flask==0.50b0
opentelemetry-instrumentation-requests==0.50b0
```

Установка выполняется внутри образа при сборке контейнера (`pip install -r requirements.txt`).

### Шаг 3. Подключение библиотек для трассировки приложения

В `app.py` последовательно настраиваются ресурс, провайдер трассировки, экспортёр и автоматическая инструментация:

```python
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "lab3-flask-app")
OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

# Ресурс: атрибуты источника телеметрии
resource = Resource.create({
    "service.name": SERVICE_NAME,
    "service.version": "1.0.0",
    "deployment.environment": os.getenv("DEPLOYMENT_ENV", "lab"),
})

# Провайдер + экспортёр OTLP (gRPC) + пакетная отправка спанов
provider = TracerProvider(resource=resource)
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=True))
)
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)

# Автоматическая инструментация Flask (входящие) и requests (исходящие)
app = flask.Flask(__name__)
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()
```

Ручные спаны создаются в обработчиках маршрутов:

```python
@app.route("/")
def hello():
    with tracer.start_as_current_span("hello") as span:
        span.set_attribute("hello.target", SEND_URL)
        span.add_event("hello.started")
        response = requests.get(SEND_URL, timeout=5)   # дочерний клиентский спан
        span.set_attribute("hello.send_status_code", response.status_code)
        span.add_event("hello.finished")
    return "Hello, World!\n"
```

Таким образом в приложении одновременно используются **автоматическая** (Flask, requests) и **ручная** (спаны `hello`, `send-notification`) инструментация.

### Шаг 4. Развертывание Jaeger

Jaeger разворачивается контейнером `jaegertracing/all-in-one:1.62.0` (коллектор + хранилище в памяти + веб-интерфейс). Приём телеметрии — по OTLP:

```yaml
jaeger:
  image: jaegertracing/all-in-one:1.62.0
  environment:
    COLLECTOR_OTLP_ENABLED: "true"
  ports:
    - "16686:16686"   # веб-интерфейс
    - "4317:4317"     # OTLP gRPC
    - "4318:4318"     # OTLP HTTP
```

### Шаг 5. Упаковка приложения в Docker-контейнер

`task1/Dockerfile`:

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 5000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health')" || exit 1

CMD ["python", "app.py"]
```

`task1/compose.yaml` описывает два сервиса — приложение и Jaeger:

```yaml
services:
  jaeger:
    image: jaegertracing/all-in-one:1.62.0
    container_name: lab3-jaeger
    environment:
      COLLECTOR_OTLP_ENABLED: "true"
    ports:
      - "16686:16686"
      - "4317:4317"
      - "4318:4318"

  app:
    build: .
    image: lab3-task1-app
    container_name: lab3-app
    environment:
      OTEL_SERVICE_NAME: lab3-flask-app
      OTEL_EXPORTER_OTLP_ENDPOINT: http://jaeger:4317
      SEND_URL: http://127.0.0.1:5000/send
      DEPLOYMENT_ENV: lab
      OTEL_PYTHON_FLASK_EXCLUDED_URLS: health
    ports:
      - "5000:5000"
    depends_on:
      - jaeger
```

Адрес экспортёра `http://jaeger:4317` использует DNS-имя сервиса во внутренней сети Compose, поэтому приложение не зависит от адреса хоста.

## 5. Результаты работы

Запуск стека:

```bash
cd task1
docker compose up -d --build
```

Оба контейнера запускаются, приложение переходит в состояние `healthy`:

```text
NAME          IMAGE                             STATUS                    PORTS
lab3-app      lab3-task1-app                    Up (healthy)              0.0.0.0:5000->5000/tcp
lab3-jaeger   jaegertracing/all-in-one:1.62.0   Up                        0.0.0.0:16686->16686/tcp, 0.0.0.0:4317-4318->4317-4318/tcp
```

Проверка приложения:

```bash
$ curl http://localhost:5000/
Hello, World!

$ curl http://localhost:5000/send
{"message":"Notification sent","status":"ok"}
```

Jaeger зарегистрировал сервис `lab3-flask-app`:

```json
{"data":["lab3-flask-app"],"total":1,"limit":0,"offset":0,"errors":null}
```

Один запрос `GET /` порождает трассировку из **пяти спанов**:

```text
GET /                     3.53 ms   (серверный спан, автоматическая инструментация Flask)
└── hello                 3.04 ms   (ручной спан; атрибуты hello.target, hello.send_status_code)
    └── GET               2.21 ms   (клиентский спан, автоматическая инструментация requests)
        └── GET /send     0.53 ms   (серверный спан Flask)
            └── send-notification  16 µs  (ручной спан; атрибут notification.channel)
```

Это подтверждает: контекст трассировки корректно передаётся через HTTP-заголовок `traceparent`, клиентский и серверный спаны объединяются в одно дерево, атрибуты и события спанов экспортируются в Jaeger.

Скриншоты:

- `images/01-structure.png` — структура каталога `task1`;
- `images/02-app-code.png` — настройка OpenTelemetry в `app.py`;
- `images/03-compose-file.png` — `compose.yaml`;
- `images/04-compose-up.png` — сборка и запуск `docker compose up -d --build`;
- `images/05-compose-ps.png` — состояние контейнеров;
- `images/06-curl.png` — ответы приложения;
- `images/07-jaeger-services.png` — сервис `lab3-flask-app` в Jaeger;
- `images/08-jaeger-traces.png` — список трассировок;
- `images/09-jaeger-trace-detail.png` — дерево из пяти спанов;
- `images/10-span-attributes.png` — атрибуты спана `hello`.

## 6. Ответы на контрольные вопросы

### 1. Что такое OpenTelemetry? Атрибуты, события, контекст, журналы, трассировки, показатели?

OpenTelemetry — открытая спецификация и набор инструментов (API, SDK, библиотеки инструментации, коллектор, экспортёры) для сбора, генерации и экспорта телеметрии. Не является бэкендом: данные передаются в Jaeger, Prometheus, Loki и др.

- **Атрибуты (attributes)** — пары «ключ–значение», описывающие спан, метрику, запись журнала или ресурс: `http.method`, `http.status_code`, `service.name`.
- **События (events)** — именованные отметки времени внутри спана с собственными атрибутами (исключения, этапы обработки); в Jaeger отображаются в логах спана.
- **Контекст (context)** — механизм передачи `trace_id`, `span_id` и baggage между вызовами и сервисами; для HTTP стандартизован W3C Trace Context (заголовок `traceparent`).
- **Журналы (logs)** — записи о событиях с временем, уровнем важности и телом сообщения.
- **Трассировки (traces)** — дерево спанов, описывающее путь одного запроса.
- **Показатели (metrics)** — числовые агрегаты за интервал времени (счётчики, гистограммы, датчики).

### 2. Что такое наблюдаемость? Надёжность и показатели?

Наблюдаемость (observability) — свойство системы, позволяющее по внешним данным телеметрии судить о её внутреннем состоянии и отвечать на вопросы «что сломалось», «где» и «почему», не изменяя код приложения.

Надёжность (reliability) — способность системы выполнять заданные функции в течение заданного времени без отказов. Количественно оценивается через SLI — измеримые показатели: задержка (latency), доля ошибок (error rate), пропускная способность (throughput), насыщение (saturation), доступность. На их основе задаются SLO (целевые значения) и SLA (обязательства перед пользователем), а также бюджет ошибок. Наблюдаемость — инструмент контроля и обеспечения надёжности.

### 3. Что такое трассировка? Что такое распределённая трассировка? Как собирать распределённую трассировку и какие проблемы имеются в распределённой архитектуре?

Трассировка — запись пути выполнения операции в виде набора спанов; каждый спан содержит имя операции, время начала и окончания, атрибуты, события и ссылку на родительский спан.

Распределённая трассировка — трассировка запроса, обрабатываемого несколькими сервисами (процессами, контейнерами): все спаны связываются общим `trace_id`, а контекст передаётся через границы сервисов.

Сбор: инструментация приложения (автоматическая и ручная) → SDK с процессором спанов → экспортёр (OTLP) → коллектор → бэкенд (Jaeger/Tempo) → визуализация.

Проблемы распределённой архитектуры:

- передача контекста через разные протоколы, брокеры сообщений и асинхронные вызовы;
- выбор стратегии сэмплирования (head-based / tail-based) при большом объёме запросов;
- накладные расходы на инструментацию и экспорт;
- рассинхронизация часов на разных узлах;
- высокая кардинальность атрибутов и стоимость хранения;
- отсутствие инструментации в legacy-компонентах.

### 4. Сигналы OpenTelemetry: трассировки, метрики, логи?

Три основных сигнала:

- **traces** — спаны и их связи (`TracerProvider`, `Tracer`, `Span`);
- **metrics** — инструменты `Counter`, `UpDownCounter`, `Histogram`, `Gauge` и асинхронные наблюдаемые инструменты (`MeterProvider`, `Meter`);
- **logs** — `LogRecord` и мост к стандартному модулю `logging` (`LoggerProvider`, `Logger`).

Дополнительно спецификация определяет baggage (данные, передаваемые вместе с контекстом) и развивает сигнал profiles. Все сигналы используют общий `Resource` и могут коррелировать по `trace_id`/`span_id`.

### 5. Инструменты OpenTelemetry: автоматические, ручные, библиотеки?

- **Автоматическая инструментация** — патчинг популярных библиотек и фреймворков без изменения кода: `opentelemetry-instrument` (Python), Java-агент, переменные окружения. В работе — `FlaskInstrumentor` и `RequestsInstrumentor`.
- **Ручная инструментация** — явное создание спанов, метрик и событий через API: `tracer.start_as_current_span(...)`, `span.set_attribute(...)`, `span.add_event(...)`.
- **Библиотеки** — пакеты `opentelemetry-instrumentation-*` для конкретных технологий (Flask, Django, requests, SQLAlchemy, gRPC), а также API, SDK и экспортёры.

### 6. Компоненты OpenTelemetry: спецификация, сборщики, библиотеки инструментальных средств, экспортёры, автоматические измерительные инструменты?

- **Спецификация** — стандарты API, SDK, протокола OTLP, семантических конвенций и структуры ресурсов.
- **Коллектор (Collector)** — отдельный процесс: приём (receivers) → обработка (processors: batch, memory_limiter, sampling) → экспорт (exporters). Позволяет централизованно маршрутизировать и обогащать телеметрию.
- **Библиотеки инструментальных средств** — интеграции для фреймворков и библиотек.
- **Экспортёры** — компоненты передачи данных в бэкенды: OTLP (gRPC/HTTP), Jaeger, Zipkin, Prometheus, console.
- **Автоматические измерительные инструменты** — механизмы автоматического подключения инструментации (Python `opentelemetry-instrument`, Java agent, sidecar-агенты).

### 7. Ресурс OpenTelemetry (телеметрия)?

`Resource` — неизменяемый набор атрибутов, описывающих сущность, создающую телеметрию: `service.name`, `service.version`, `service.instance.id`, `host.name`, `deployment.environment`, `telemetry.sdk.*`. Ресурс задаётся программно (`Resource.create`) или через переменные окружения `OTEL_SERVICE_NAME`, `OTEL_RESOURCE_ATTRIBUTES` и автоматически применяется ко всем спанам, метрикам и журналам провайдера. Именно по `service.name` Jaeger группирует трассировки в списке сервисов (в работе — `lab3-flask-app`).

### 8. Экспортёры OpenTelemetry?

Экспортёры передают телеметрию из SDK во внешние системы:

- **OTLP** — основной протокол, gRPC (порт 4317) или HTTP/protobuf (4318);
- **Jaeger** — исторический thrift-экспортёр (устарел, заменён OTLP);
- **Zipkin**;
- **Prometheus** — экспозиция метрик в формате Prometheus через HTTP-endpoint;
- **console/logging** — вывод в stdout для отладки.

Экспортёр работает совместно с процессором (`SimpleSpanProcessor` — синхронно, `BatchSpanProcessor` — пакетно); настраиваются endpoint, TLS, заголовки, таймауты, сжатие.

### 9. Что такое Prometheus? Как работает Prometheus?

Prometheus — open-source система мониторинга и база данных временных рядов (TSDB) проекта CNCF. Работает по **pull-модели**: периодически опрашивает HTTP-endpoint `/metrics` целевых систем согласно конфигурации `scrape_configs`, сохраняет полученные временные ряды, позволяет выполнять запросы на языке PromQL и настраивать правила алертинга с отправкой в Alertmanager. Поддерживает service discovery (Kubernetes, Consul, файлы). Для короткоживущих задач предусмотрен Pushgateway. Prometheus не предназначен для хранения журналов и трассировок; хранение локальное, масштабирование — через федерацию или remote write.

### 10. Концепции Prometheus?

- **Метрика** — именованный временной ряд, идентифицируемый именем и набором меток (`labels`).
- **Sample** — пара (timestamp, value).
- **Labels** — размерность: `job`, `instance`, `method`, `status`; специальная метка `__name__`.
- **Target / scrape** — цель опроса и сам процесс опроса.
- **PromQL** — язык запросов: instant/range vector, функции `rate()`, `increase()`, `histogram_quantile()`, агрегации `sum by (...)`.
- **Recording rules / alerting rules**, **Alertmanager**.
- **Exporters** (node_exporter, mysqld_exporter), **Pushgateway**.
- **Retention**, блоки TSDB, remote write/read.

### 11. Типы метрик?

- **Counter** — монотонно возрастающее значение (число запросов, ошибок); анализируется через `rate()`/`increase()`.
- **Gauge** — значение, изменяющееся в обе стороны (температура, число активных соединений, использование памяти).
- **Histogram** — распределение значений по настраиваемым бакетам; даёт `_sum`, `_count` и квантили через `histogram_quantile()` (задержки запросов).
- **Summary** — квантили, вычисляемые на клиенте (в OpenTelemetry не рекомендуется, в Prometheus ограниченно применим).
- В OpenTelemetry дополнительно: **UpDownCounter** (может уменьшаться) и асинхронные наблюдаемые инструменты (ObservableGauge, ObservableCounter, ObservableUpDownCounter).

### 12. Запрос и преобразование данных Grafana?

Grafana не хранит телеметрию: она отправляет запросы к источнику данных через соответствующий плагин (PromQL для Prometheus, LogQL для Loki, API Jaeger/Tempo, SQL для БД). Далее применяются:

- **преобразования (transformations)** — join, merge, filter, rename, calculate, reduce, sort, organize fields;
- **выражения (expressions)** — Math, Reduce, Resample для вычислений поверх результатов запросов;
- **переменные (template variables)** — параметризация дашбордов (`$instance`, `$__rate_interval`);
- **интервалы и диапазон времени** — `$__interval`, `$__range`;
- **пороги (thresholds)**, переопределения (field overrides), единицы измерения.

Результат визуализируется выбранной панелью.

### 13. Источники данных Grafana?

Core-плагины: Prometheus, Loki, Jaeger, Tempo, Graphite, InfluxDB, Elasticsearch/OpenSearch, MySQL, PostgreSQL, Microsoft SQL Server, CloudWatch, Azure Monitor, Google Cloud Monitoring, Grafana Mimir, TestData. Дополнительно устанавливаются community-плагины (VictoriaMetrics, ClickHouse, Infinity для REST/JSON, CSV и др.). Подключаются через UI или provisioning YAML; для каждого источника настраиваются URL, аутентификация и параметры запросов.

### 14. Панели мониторинга Grafana?

Dashboard — набор панелей, объединённых сеткой (grid), с общими переменными, диапазоном времени, автообновлением, аннотациями и ссылками. Панель включает: источник данных, запрос(ы), преобразования, тип визуализации (time series, stat, gauge, bar chart, table, heatmap, logs, trace), настройки осей и легенды, пороги и алерты. Дашборды хранятся в виде JSON, поддерживают версионирование, папки, provisioning, импорт/экспорт и публичные снапшоты.

### 15. Процесс обработки журналов Grafana Loki?

1. Агент (Promtail, Grafana Alloy, Fluent Bit, драйвер Docker) собирает журналы из файлов, journald или контейнеров.
2. К записям добавляются метки (labels): `job`, `container`, `level`, `namespace` — индексируются только метки, а не текст.
3. Данные отправляются по HTTP в **distributor**, который распределяет потоки по ингесторам.
4. **Ingester** формирует чанки и сохраняет их в объектное хранилище (S3, MinIO, файловая система), индекс — отдельно.
5. **Querier** выполняет запросы LogQL по индексу и чанкам; **ruler** — правила алертинга.
6. Grafana отображает результат; поддерживаются фильтрация по меткам, парсинг (json, logfmt, regexp) и метрические запросы (`rate`, `count_over_time`).

Индексирование только меток делает Loki дешевле полнотекстовых систем, но требует продуманной схемы меток.

### 16. Варианты сборки журналов для Grafana Loki?

- **Promtail** — классический агент (переведён в режим поддержки, рекомендуется миграция);
- **Grafana Alloy** — современный рекомендованный агент (замена Promtail);
- **Fluent Bit / Fluentd** — плагин вывода `loki`;
- **Docker-драйвер** `loki` (`docker run --log-driver=loki ...`);
- **OpenTelemetry Collector** — экспортёры `loki` / `otlphttp`;
- **Vector**, **Logstash**;
- прямая отправка из приложения через HTTP API `/loki/api/v1/push`;
- сбор в Kubernetes (DaemonSet/Helm), systemd-journald, syslog.

## 7. Вывод

В ходе выполнения задания 1 приложение на Flask было инструментировано средствами OpenTelemetry: настроены ресурс, провайдер трассировки, пакетный экспортёр OTLP, автоматическая инструментация Flask и requests, а также ручные спаны с атрибутами и событиями. Приложение упаковано в Docker-образ и запускается вместе с Jaeger через Docker Compose. Проверка показала, что один запрос `GET /` формирует в Jaeger трассировку из пяти связанных спанов, охватывающую серверные и клиентские операции, — то есть сбор и визуализация распределённой трассировки настроены корректно.
