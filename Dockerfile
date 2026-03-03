FROM python:3.12-slim AS builder
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir ".[prod]"

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .
ENV DJANGO_SETTINGS_MODULE=engram.settings.production
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "engram.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
