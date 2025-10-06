FROM python:3.10-slim

# Prevents Python from writing .pyc files and enables unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for lxml and onvif-zeep (libxml2, libxslt), plus build tools
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       libxml2-dev \
       libxslt1-dev \
       libffi-dev \
       libssl-dev \
       pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first to leverage Docker layer caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy source code
COPY . /app

# Expose gRPC port
EXPOSE 50051

# Default command mirrors docker-compose
CMD ["python", "grpc_server.py"]


