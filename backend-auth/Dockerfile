# FROM python:3.9-slim

# # Evita que Python genere archivos pyc y usa salida sin buffer
# ENV PYTHONUNBUFFERED=1

# # Establece el directorio de trabajo
# WORKDIR /app

# # Instala dependencias del sistema necesarias para wkhtmltopdf
# RUN apt-get update && \
#     apt-get install -y --no-install-recommends \
#     wkhtmltopdf \
#     libxrender1 \
#     libxext6 \
#     libfontconfig1 \
#     libjpeg62-turbo \
#     && apt-get clean && rm -rf /var/lib/apt/lists/*
    
# # Copia solo requirements.txt primero para aprovechar la cache de Docker
# COPY requirements.txt .

# # Instala dependencias en un solo paso optimizado
# RUN pip install --no-cache-dir -r requirements.txt

# # Copia el resto del código
# COPY . .

# # Configurar variables de entorno
# ENV PORT=8000
# EXPOSE $PORT

# # Crear usuario sin privilegios y Asegurar que el usuario tiene permisos en el directorio de trabajo
# RUN adduser --disabled-password --gecos '' myuser
# RUN chown -R myuser:myuser /app
# USER myuser

# # Ejecutar uvicorn
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM python:3.9-slim-bullseye
 
ENV PYTHONUNBUFFERED=1
WORKDIR /app
 
# Dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    xfonts-75dpi \
    xfonts-base \
    fontconfig \
    libxrender1 \
    libxext6 \
    libjpeg62-turbo \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*
 
 
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
 
COPY . .
 
EXPOSE 8000
 
RUN adduser --disabled-password --gecos '' myuser && \
    chown -R myuser:myuser /app
USER myuser
 
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]