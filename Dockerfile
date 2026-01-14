# Usamos una imagen ligera de Python
FROM python:3.10-slim

# Directorio de trabajo
WORKDIR /app

# Copiamos los archivos
COPY . .

# Instalamos las dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Comando para arrancar con Gunicorn (Como en AI Pro)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]