FROM python:3.12-slim

# reportlab y psycopg2-binary no requieren libs de sistema extra en slim,
# pero dejamos build-essential por si se compila algo en el futuro.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# EasyPanel inyecta PORT; por defecto 5000.
ENV PORT=5000
EXPOSE 5000

# 2 workers, timeout holgado para generación de PDF y envío secuencial a Monday.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 2 --timeout 300 app:app"]
