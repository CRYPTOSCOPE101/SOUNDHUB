FROM python:3.12-slim

WORKDIR /app

# System deps (minimal; SQLite ships with Python)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Data lives on a persistent volume (mounted at /data on Fly).
ENV SOUNDHUB_DATA_DIR=/data
ENV SOUNDHUB_DATABASE_URL=sqlite:////data/soundhub.db

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
