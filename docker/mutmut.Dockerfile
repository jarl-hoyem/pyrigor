FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git tini && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /project
COPY . .

RUN pip install --no-cache-dir -e ".[dev]" mutmut

ENTRYPOINT ["/usr/bin/tini", "--", "mutmut"]
