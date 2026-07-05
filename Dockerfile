FROM python:3.11-slim AS builder

WORKDIR /app
COPY pyproject.toml README.md ./
COPY polymind/ polymind/
RUN pip install --no-cache-dir build && python -m build --wheel

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/polymind-*.whl && rm /tmp/polymind-*.whl

COPY scripts/ /app/scripts/

ENTRYPOINT ["polymind"]
CMD ["--help"]
