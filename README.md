# KVM Manager MVP

Минимальный MVP системы управления ВМ на базе KVM/libvirt.

Запуск API:

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Примеры запросов:

POST /vm/create

```json
{
  "name": "vm1",
  "image": "/var/lib/libvirt/images/ubuntu.qcow2",
  "cpu": 1,
  "memory_mb": 512,
  "disk_gb": 10
}
```

CLI:

```bash
python -m app.cli create --name vm1 --image /var/lib/libvirt/images/ubuntu.qcow2
```

Docker (build and run):

```bash
# Build images and start app (use modern `docker compose`)
docker compose build --pull
docker compose up -d app

# Run tests in container (explicit project name to avoid empty-name errors)
docker compose -p kvmmgr run --rm tests

# Alternatively set environment variable:
# COMPOSE_PROJECT_NAME=kvmmgr docker compose run --rm tests
```
