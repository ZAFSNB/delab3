# ---------- Базовый образ ----------
# slim-версия Python: достаточно для Flask-приложения, образ компактнее
FROM python:3.12-slim

# ---------- Переменные окружения ----------
# Не создавать .pyc и не буферизовать вывод (логи сразу попадают в docker logs)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ---------- Рабочий каталог ----------
WORKDIR /app

# ---------- Зависимости ----------
# Отдельный слой: при изменении только app.py зависимости переустанавливаться не будут
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------- Исходный код ----------
COPY app.py .

# ---------- Сетевой порт ----------
EXPOSE 5000

# ---------- Проверка живости ----------
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health')" || exit 1

# ---------- Точка входа ----------
CMD ["python", "app.py"]
