FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --create-home --shell /usr/sbin/nologin app

COPY requirements.txt ./
RUN python -m pip install -r requirements.txt

COPY --chown=app:app app ./app
COPY --chown=app:app seed ./seed
COPY --chown=app:app wsgi.py ./
RUN mkdir /app/storage && chown app:app /app/storage

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"]

# The file-backed content store requires one synchronous request worker.
CMD ["gunicorn", "--bind=0.0.0.0:8000", "--workers=1", "--threads=1", "--timeout=60", "--access-logfile=-", "--error-logfile=-", "--capture-output", "wsgi:app"]
