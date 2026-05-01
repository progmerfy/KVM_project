FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies required for libvirt-python and qemu-img
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    libvirt-dev \
    libvirt-clients \
    qemu-utils \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
