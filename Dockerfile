# Use official Python 3.11 slim image
FROM python:3.11-slim

# Install system dependencies required for mysqlclient
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire project
COPY . .

# Create uploads folder
RUN mkdir -p static/uploads

# Cloud Run provides PORT env var (default 8080)
ENV PORT=8080

# Expose the port
EXPOSE 8080

# Run with gunicorn (production WSGI server)
# 2 workers, 4 threads each — good for Cloud Run
CMD exec gunicorn --bind :$PORT --workers 2 --threads 4 --timeout 60 app:app
