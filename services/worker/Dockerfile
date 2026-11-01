FROM python:3.12-slim

WORKDIR /srv

COPY packages/shared/python /srv/packages/shared/python
COPY services/worker/requirements.txt /srv/services/worker/requirements.txt

RUN pip install --no-cache-dir -e /srv/packages/shared/python \
    && pip install --no-cache-dir -r /srv/services/worker/requirements.txt

COPY services/worker /srv/services/worker
WORKDIR /srv/services/worker

CMD ["python", "-m", "worker.main"]
