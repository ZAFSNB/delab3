# Задание 1. Трассировка Flask-приложения (OpenTelemetry + Jaeger)

## Состав каталога

| Файл | Назначение |
|---|---|
| `app.py` | Flask-приложение с автоматической и ручной инструментацией OpenTelemetry |
| `requirements.txt` | зависимости Python (Flask, OTel SDK, OTLP-экспортёр, инструментация) |
| `Dockerfile` | сборка образа приложения |
| `compose.yaml` | запуск приложения и Jaeger (UI + OTLP) |
| `.dockerignore` | исключения из контекста сборки |

## Запуск

```bash
docker compose up -d --build
```

- приложение — <http://localhost:5000/>
- Jaeger UI — <http://localhost:16686> (сервис `lab3-flask-app`)

## Проверка

```bash
curl http://localhost:5000/
curl http://localhost:5000/send
```

Первый запрос создаёт трассировку из пяти спанов:
`GET /` → `hello` → `GET` (клиент) → `GET /send` → `send-notification`.

## Остановка

```bash
docker compose down
```
