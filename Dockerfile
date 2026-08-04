FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CURATOR_HOST=0.0.0.0 \
    CURATOR_PORT=8088 \
    CURATOR_DATA_DIR=/data \
    CURATOR_CONFIG=/config/curator.yaml

WORKDIR /app
COPY pyproject.toml README.md /app/
COPY app /app/app
RUN pip install --no-cache-dir .

EXPOSE 8088
CMD ["soulseek-curator"]

