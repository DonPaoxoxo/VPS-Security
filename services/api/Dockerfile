FROM python:3.12-slim

WORKDIR /srv

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY packages/shared/python /srv/packages/shared/python
COPY services/api/requirements.txt /srv/services/api/requirements.txt

RUN pip install --no-cache-dir -e /srv/packages/shared/python \
    && pip install --no-cache-dir -r /srv/services/api/requirements.txt

COPY agents/linux /srv/agent-bundle-src
RUN tar -czf /srv/agent-bundle.tar.gz -C /srv/agent-bundle-src \
        --exclude='__pycache__' . \
    && rm -rf /srv/agent-bundle-src
ENV AGENT_BUNDLE_PATH=/srv/agent-bundle.tar.gz

COPY services/api /srv/services/api
WORKDIR /srv/services/api
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
