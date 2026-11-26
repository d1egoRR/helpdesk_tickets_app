# syntax=docker/dockerfile:1

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app/src"

WORKDIR /app

RUN python -m venv /opt/venv

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements-dev.txt

RUN groupadd --system appgroup \
    && useradd --system --gid appgroup --create-home appuser

COPY --chown=appuser:appgroup pyproject.toml ./
COPY --chown=appuser:appgroup src ./src
COPY --chown=appuser:appgroup tests ./tests
RUN chown appuser:appgroup /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "helpdesk.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
