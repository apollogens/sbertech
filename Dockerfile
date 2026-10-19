FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY src/ ./src/
COPY app/ ./app/
COPY config/ ./config/
ARG MODEL_BUNDLE=model
COPY ${MODEL_BUNDLE}/ ./model/
RUN python -c "import json; from pathlib import Path; selected=json.loads(Path('model/config.json').read_text(encoding='utf-8')); Path('config/runtime.json').write_text(json.dumps({'schema_version':1,'active_bundle':'../model','active_strategy':selected.get('strategy','nonton-v1')})+'\n',encoding='utf-8')"
ENV MODEL_DIR=/app/model PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
