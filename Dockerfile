FROM python:3.9-slim

WORKDIR /app
ENV PYTHONPATH=/app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    netcat-openbsd \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalar torch primero (optimización para caché de Docker)
RUN pip install torch --no-cache-dir

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]