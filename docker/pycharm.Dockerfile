FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    libfontconfig1 \
    libfreetype6 \
    libxi6 \
    libxrender1 \
    libxtst6 \
    && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /opt/pycharm && \
    curl -L 'https://download.jetbrains.com/product?code=PCP&latest&distribution=linux' -o /tmp/pycharm.tar.gz && \
    tar -xzf /tmp/pycharm.tar.gz -C /tmp && \
    mv /tmp/pycharm-*/* /opt/pycharm/ && \
    rm -rf /tmp/pycharm*

ENV PATH="/opt/pycharm/bin:$PATH"
ENV JAVA_TOOL_OPTIONS="-Djava.awt.headless=true -Didea.config.path=/opt/pycharm-config -Didea.system.path=/tmp/pycharm-system"

# Keep the isolated inspection runner aligned with the repository's British
# English prose, without copying personal IDE settings or disabling any rules.
COPY pycharm-options/grazie_global.xml /opt/pycharm-config/options/grazie_global.xml
COPY pycharm-options/jdk.table.xml /opt/pycharm-config/options/jdk.table.xml

WORKDIR /project
