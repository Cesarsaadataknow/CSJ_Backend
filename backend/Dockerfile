FROM python:3.9-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Instala dependencias necesarias
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        wget \
        gnupg \
        ca-certificates \
        libxrender1 \
        libxext6 \
        libfontconfig1 \
        libjpeg62-turbo \
        xfonts-base \
        xfonts-75dpi

# Descarga e instala wkhtmltopdf
RUN wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.buster_amd64.deb && \
    dpkg -i wkhtmltox_0.12.6-1.buster_amd64.deb || true && \
    apt-get install -f -y && \
    rm wkhtmltox_0.12.6-1.buster_amd64.deb

# Limpieza
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

# Crear usuario sin privilegios
RUN adduser --disabled-password --gecos '' myuser && \
    chown -R myuser:myuser /app
USER myuser

# Configuración del contenedor
ENV PORT=8000
#ENV PORT=8501
EXPOSE $PORT

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
