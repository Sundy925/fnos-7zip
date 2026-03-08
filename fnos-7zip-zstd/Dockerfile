FROM python:3.10-slim

WORKDIR /app

# Install required packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY templates/ ./templates/
COPY static/ ./static/
COPY bin/ ./bin/

# Ensure 7zz is executable
RUN chmod +x bin/7zz

# Create config directory
RUN mkdir -p /config

# Environment variables
ENV FLASK_ENV=production
ENV PKG_CONFIG_PATH=/config/config.json
ENV DOCKER_MOUNT_PATHS=/host_fs:/Root

EXPOSE 5000

CMD ["python3", "app.py"]
