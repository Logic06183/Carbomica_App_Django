FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (gcc needed for psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# setuptools must be explicit in Python 3.12+ slim (pkg_resources removed)
RUN pip install --no-cache-dir setuptools

# Install Python dependencies first (Docker layer cache efficiency)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files (whitenoise serves them directly from Django)
RUN python manage.py collectstatic --noinput

# Cloud Run injects PORT; default to 8080 for local Docker testing
ENV PORT=8080

# Health check (Cloud Run checks / for liveness)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:$PORT/ || exit 1

# start.sh: runs migrations then launches gunicorn
COPY start.sh .
RUN chmod +x start.sh
CMD ["./start.sh"]
