FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies needed for psycopg2, lxml, etc.
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    libxml2-dev \
    libxslt1-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Start server
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
