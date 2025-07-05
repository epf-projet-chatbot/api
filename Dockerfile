# ================================
# 🐍 PYTHON BASE IMAGE
# ================================
FROM python:3.12-slim

# ================================
# 📦 SYSTEM DEPENDENCIES
# ================================
# Install system dependencies for Python packages
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libmagic1 \
    libmagic-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ================================
# 🏗️ WORKING DIRECTORY
# ================================
WORKDIR /app

# ================================
# 📋 PYTHON DEPENDENCIES
# ================================
# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ================================
# 📁 APPLICATION CODE
# ================================
# Copy application code (structure correcte)
COPY app/ ./
COPY rag/ ./rag/
COPY launch_embedding.sh /app/launch_embedding.sh
RUN chmod +x /app/launch_embedding.sh

# ================================
# ⚙️ ENVIRONMENT SETUP
# ================================
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Create uploads directory
RUN mkdir -p /app/uploads

# ================================
# 🚀 STARTUP COMMAND
# ================================
EXPOSE 8000

ENTRYPOINT ["/app/launch_embedding.sh"]