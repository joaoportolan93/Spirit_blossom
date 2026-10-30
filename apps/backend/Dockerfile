FROM python:3.12-slim

# Dependências do sistema para compilar psycopg e outras extensões
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar dependências antes do código para aproveitar cache de camadas
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Coletar estáticos (em produção, servidos pelo Nginx)
RUN python manage.py collectstatic --noinput --skip-checks 2>/dev/null || true

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--worker-class", "gthread", \
     "--threads", "2", \
     "--timeout", "60", \
     "--access-logfile", "-"]

