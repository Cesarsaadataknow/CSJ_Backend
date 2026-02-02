FROM python:3.11-slim

# Evita que Python genere archivos pyc y usa salida sin buffer
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Establece el directorio de trabajo
WORKDIR /app

# Copia solo requirements.txt primero para aprovechar cache
COPY requirements.txt .

# Instala dependencias Python
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copia el resto del código
COPY . .

# Expone el puerto de la aplicación
EXPOSE 8000

# Comando de ejecución (ajusta si tu app está en otro módulo)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
