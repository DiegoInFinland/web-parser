# syntax=docker/dockerfile:1
FROM python:3.14-alpine3.24 AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN addgroup -S app && adduser -S -G app app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM base AS development
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY server.py test_server.py ./
USER app
CMD ["python", "server.py"]

FROM development AS test
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "test_server.py"]

# Keep production last so a plain `docker build .` builds this stage.
FROM base AS production
COPY server.py .
USER app
CMD ["python", "server.py"]
