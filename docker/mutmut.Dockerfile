FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /project
COPY . .

RUN pip install --no-cache-dir -e ".[dev]" mutmut pytest-cov

ENTRYPOINT ["mutmut"]
