FROM python:3.11-slim AS python-services

RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY auto_subtitle_service.py .
COPY video_processing_service.py .

RUN mkdir -p /data/temp /app/temp

COPY start_services.sh /app/start_services.sh
RUN chmod +x /app/start_services.sh

EXPOSE 8000 8080

CMD ["/app/start_services.sh"]

FROM n8nio/n8n:latest AS n8n

USER root

RUN apk add --no-cache ffmpeg docker-cli

USER node
