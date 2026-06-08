FROM python:3.13-slim AS backend

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/usr/lib/python3/dist-packages

WORKDIR /app

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

FROM node:20-slim AS frontend-builder
WORKDIR /frontend
COPY frontend/package.json /frontend/
RUN npm install --no-audit --no-fund
COPY frontend/ /frontend/
RUN npx vite build

FROM backend
COPY --from=frontend-builder /frontend/dist /app/frontend-dist

EXPOSE 8000 8443

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8443"]
