# ARM 32-Bit kompatibles Python-Image (Raspberry Pi 3B+)
FROM python:3.11-slim-bookworm

# Plattform-Hint für BuildKit (wird von docker-compose gesetzt)
ARG TARGETARCH

WORKDIR /app

# System-Abhängigkeiten für caldav / lxml / cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

ENV CONFIG_PATH=/config/config.json
ENV PYTHONUNBUFFERED=1

EXPOSE 5000

CMD ["python", "app.py"]
