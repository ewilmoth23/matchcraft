FROM python:3.14-slim@sha256:cea0e6040540fb2b965b6e7fb5ffa00871e632eef63719f0ea54bca189ce14a6 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system matchcraft && useradd --system --gid matchcraft --home /app matchcraft
WORKDIR /app

COPY apps/api/pyproject.toml ./pyproject.toml
COPY apps/api/constraints.lock ./constraints.lock
COPY apps/api/app ./app
COPY apps/api/alembic ./alembic
COPY apps/api/alembic.ini ./alembic.ini
RUN pip install --constraint constraints.lock .

RUN mkdir -p /data/uploads /data/exports && chown -R matchcraft:matchcraft /app /data
USER matchcraft

EXPOSE 8000
# Probes /health/live, not /health. The latter contacts the configured model providers,
# so its latency depends on a third party: a firewalled Ollama host made it exceed this
# probe's own timeout and marked a working API unhealthy, which then blocked the web
# container from starting. /health/live also returns a non-200 status when the database
# is unusable, which the previous probe could not detect because /health answers 200
# with "degraded".
HEALTHCHECK --interval=20s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live', timeout=4)" || exit 1

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
