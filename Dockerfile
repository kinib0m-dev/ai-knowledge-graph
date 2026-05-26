FROM python:3.11-slim

# Instalar dependencias del sistema (necesarias para algunos paquetes)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Añadir Poetry al PATH
ENV PATH="/root/.local/bin:$PATH"

# Configurar Poetry para que no cree venv virtual (Docker ya es un entorno aislado)
RUN poetry config virtualenvs.create false

WORKDIR /app

# Copiar primero los archivos de dependencias (mejor cache de Docker)
COPY pyproject.toml poetry.lock ./

# Instalar dependencias
RUN poetry install --no-root --no-interaction --no-ansi

# Copiar el resto del código
COPY . .

# Exponer puerto para Streamlit
EXPOSE 8501

# Comando por defecto (puedes sobrescribirlo)
CMD ["poetry", "run", "streamlit", "run", "app/app.py", "--server.port=8501", "--server.address=0.0.0.0"]