FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git tini && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9.17 /uv /usr/local/bin/uv

# The environment lives outside /project, so CI's bind mount of the checkout does not hide it.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PATH=/opt/venv/bin:$PATH

WORKDIR /project
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --extra dev --no-install-project --no-cache
COPY . .
RUN uv sync --locked --extra dev --no-cache

ENTRYPOINT ["/usr/bin/tini", "--", "mutmut"]
