FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/usr/lib/python3/dist-packages

WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    libvirt-dev \
    libvirt-clients \
    python3-libvirt \
    qemu-utils \
    genisoimage \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
