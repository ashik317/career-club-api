FROM python:3.12-slim

# Don't write .pyc files, and show logs right away
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first, so Docker caches this layer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project code
COPY . .

# Run as a non-root user
RUN adduser --disabled-password --no-create-home appuser
USER appuser

EXPOSE 8000

CMD ["gunicorn", "myproject.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]