
# Python runtime
FROM python:3.11-slim

# Python and application environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TESSERACT_CMD=/usr/bin/tesseract

# Application working directory
WORKDIR /app

# Install system dependencies for OCR and PDF processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend application
COPY . .

# Create a non-root user and assign application ownership
RUN useradd --create-home --shell /usr/sbin/nologin appuser && \
    chown -R appuser:appuser /app

# Run application without root privileges
USER appuser

# Render provides PORT; use 8080 as the default
EXPOSE 8080

# Start FastAPI
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
