FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements/main.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r main.txt

COPY --chmod=755 ./scripts /app/scripts
COPY ./logging.yaml /app/logging.yaml
COPY ./soumetsu_api /app/soumetsu_api
WORKDIR /app

ENTRYPOINT ["/app/scripts/bootstrap.sh"]
