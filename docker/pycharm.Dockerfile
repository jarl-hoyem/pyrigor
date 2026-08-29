FROM eclipse-temurin:21-jre-jammy

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /opt/pycharm && \
    curl -L 'https://download.jetbrains.com/product?code=PCP&latest&distribution=linux' -o /tmp/pycharm.tar.gz && \
    tar -xzf /tmp/pycharm.tar.gz -C /tmp && \
    mv /tmp/pycharm-*/* /opt/pycharm/ && \
    rm -rf /tmp/pycharm*

ENV PATH="/opt/pycharm/bin:$PATH"
ENV JAVA_TOOL_OPTIONS="-Djava.awt.headless=true"

WORKDIR /project
