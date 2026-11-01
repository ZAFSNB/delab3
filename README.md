# Overview

Report on LabRabota3. Мониторинг в распределённых системах (OpenTelemetry + Jaeger).

# Usage

// Заменить <<link>> и <<folder>> на соответствующие ссылки/названия

To check, please, preview report by <<link>> and source files
in <<folder>>.

- Задание 1 (группа 13) — каталог `task1/`: Flask-приложение с трассировкой
  OpenTelemetry и Jaeger, `Dockerfile`, `compose.yaml`.
- Отчет — `docs/report.md`.

Быстрый запуск:

```bash
cd task1
docker compose up -d --build
curl http://localhost:5000/
```

Веб-интерфейс Jaeger: <http://localhost:16686> (сервис `lab3-flask-app`).

# Author

Чжао Аофэй, группа 13.

# Additional Notes

// СКОПИРОВАТЬ И ВСТАВИТЬ ССЫЛКУ НА СВОЙ РЕПОЗИТОРИЙ, НАПРИМЕР
https://github.com/<username>/LabRabota3
