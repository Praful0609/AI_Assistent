FROM python:3.11-slim

# System deps for Tree-sitter, git, psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    git \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (better layer caching)
# requirements.txt is now at backend/requirements.txt, copied via root context
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the backend app
COPY backend/app ./app

# Copy shared modules that the backend imports at runtime
COPY parsers  ./parsers
COPY graph    ./graph
COPY vector   ./vector
COPY ai       ./ai

# Create uploads directory
RUN mkdir -p /app/uploads

EXPOSE 8000
