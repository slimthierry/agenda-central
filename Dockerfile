FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN pip install --no-cache-dir . "uvicorn[standard]"

EXPOSE 4400

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 4400"]
