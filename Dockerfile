FROM python:3.12-slim as builder

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

COPY pyproject.toml ./

RUN pip install --user --no-cache-dir . "uvicorn[standard]"

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PATH=/root/.local/bin:$PATH

COPY --from=builder /root/.local /root/.local
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 4400

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:4400/health')"

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 4400"]
