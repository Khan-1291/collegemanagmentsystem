FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

RUN mkdir -p /data/uploads /data/private_uploads/activities \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app /data

ENV UPLOAD_DIR=/data/uploads \
    PROFILE_UPLOAD_DIR=/data/uploads/profiles \
    ACTIVITY_UPLOAD_DIR=/data/private_uploads/activities

USER appuser

EXPOSE 8000

CMD ["sh", "-c", "python -m app.db_bootstrap && alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
