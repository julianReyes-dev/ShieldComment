# Usamos python:3.9-alpine para tener una imagen más ligera
FROM python:3.9-alpine

# Establecer el directorio de trabajo
WORKDIR /app

# Establecer PYTHONPATH
ENV PYTHONPATH=/app

# Instalar nc (netcat) para poder usarlo en los scripts
RUN apk add --no-cache netcat-openbsd

# Copiar el archivo requirements.txt y luego instalar las dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto de la aplicación
COPY . .

# Comando para ejecutar el servidor con Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

