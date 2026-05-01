# Примеры ответов об ошибках (API)

Ниже приведены примеры JSON-ответов, которые возвращает API при различных ошибках.

1. Ошибка: образ не найден (ошибка в слое Service)

- Код HTTP: 400
- Тело ответа:

```json
{
  "detail": {
    "code": "IMAGE_NOT_FOUND",
    "message": "base image not found: /var/lib/libvirt/images/missing.qcow2"
  }
}
```

2. Ошибка: ВМ не найдена (404)

```json
{
  "detail": {
    "code": "VM_NOT_FOUND",
    "message": "VM 'unknown' not found"
  }
}
```

3. Ошибка инфраструктуры (libvirt недоступен) — 503

```json
{
  "detail": {
    "code": "InfrastructureError",
    "message": "failed to open connection to qemu:///system"
  }
}
```

4. Внутренняя ошибка сервера — 500

```json
{
  "detail": "Internal Server Error"
}
```
