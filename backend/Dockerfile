# Report API image. Build context = repository root:
#   docker compose -f backend/docker-compose.yml up -d --build
FROM python:3.12.8-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    BACKEND_STORE=/app/backend/store IMAGE_ROOT=/data/images
WORKDIR /app

COPY backend/requirements.txt backend/requirements-dev.txt backend/
RUN pip install --no-cache-dir -r backend/requirements-dev.txt

COPY backend/ backend/
# No .git inside the image: the scorer commit is passed in at build time.
ARG SCORER_COMMIT=unknown
ENV SCORER_COMMIT=${SCORER_COMMIT}

# Fail the build if the exception tests fail.
RUN python -m pytest backend/tests -q -p no:cacheprovider

RUN useradd --uid 1000 --create-home app && chown -R app /app
USER app
EXPOSE 8888
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8888/api/health', timeout=4)"
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8888"]
