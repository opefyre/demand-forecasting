FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    DEMANDLAB_CLOUD_RUNTIME=true DEMANDLAB_AI_ENABLED=false DEMANDLAB_IMPORT_ROOTS=[]
WORKDIR /srv/forecast
COPY requirements.txt ./requirements.txt
COPY deploy/cloudflare/engine-requirements.lock ./engine-requirements.lock
RUN pip install --no-cache-dir -r engine-requirements.lock
COPY app ./app
RUN mkdir -p data runs app/static && useradd --uid 10001 --no-create-home forecast \
    && chown -R forecast:forecast /srv/forecast
USER 10001:10001
EXPOSE 8080
CMD ["uvicorn", "app.cloud_compute:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--no-access-log", "--log-level", "critical"]
