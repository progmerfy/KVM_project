# Code Review Report — KVM Manager

> Дата: 2026-06-17
> Ветка: `fix/thesis-discrepancies`
> Тесты: 98 passed, 3 failed (в Docker)

---

## 🔴 CRITICAL BUGS

### 1. Missing import `database` в `vm_manager.py:350`
**Файл:** `app/services/vm_manager.py:350`
```python
pw = database.get_vm_root_password(name)   # ← NameError!
```
На строке 13 импортированы только конкретные имена:
```python
from app.database import set_vm_owner, delete_vm_ownership, list_vms_for_user, get_vm_owner
```
Модуль `database` как объект **не импортирован**. При каждом вызове `GET /vm/info/{name}` для работающей ВМ — `NameError: name 'database' is not defined`.

**Воспроизводится:** тестом `test_get_vm_info_with_ip` (упал 1 из 3).

### 2. JWT-ключ генерируется заново при каждом рестарте
**Файл:** `app/auth.py:20-22`
```python
_DEFAULT_KEY = secrets.token_hex(32)
...
_DEFAULT_KEY = "CHANGE-ME-IN-PRODUCTION-MUST-BE-AT-LEAST-32-BYTES!!"
```
- Если не задан `JWT_SECRET_KEY`, при каждом перезапуске генерируется новый ключ → все существующие токены инвалидируются.
- Fallback — хардкодная строка в открытом виде (если импорт `secrets` по какой-то причине упадёт).

### 3. Root-пароль ВМ хранится в plaintext в SQLite
**Файл:** `app/database.py:166-175`
Колонка `root_password` в таблице `vm_ownership` — открытый текст. Любой с доступом к БД или audit-логам может получить пароли гостевых ВМ.

---

## 🔴 SECURITY ISSUES

### 4. SHA-256 без KDF для хэширования паролей
**Файл:** `app/database.py:21-29`
```python
h = hashlib.sha256((salt + password).encode()).hexdigest()
```
Один раунд SHA-256 — GPU-брутфорс со скоростью миллиарды хэшей/сек. Нужен bcrypt/argon2.

### 5. Дефолтный пароль админа — "admin"
**Файл:** `app/database.py:99`
```python
pw = hash_password(os.getenv("API_PASSWORD", "admin"))
```
5 символов, при том что валидация новых паролей требует `min_length=8`.

### 6. Логин-форма предзаполнена credentials
**Файл:** `app/api/auth_routes.py:204-206`
```html
<input value="admin" ... placeholder="admin@localhost">
<input type="password" value="admin" ...>
```
Креды admin/admin отправляются на клиент в исходном HTML → видны в "View Page Source".

### 7. Нет rate limiting на `/auth/login`
**Файл:** `app/api/auth_routes.py:58-74`
Эндпоинт аутентификации не имеет троттлинга, блокировки аккаунта или CAPTCHA → возможен брутфорс.

### 8. SSRF в `/images/download`
**Файл:** `app/api/image_routes.py:114`
```python
subprocess.check_call(["curl", "-L", "-o", dest, url], timeout=600)
```
Параметр `url` от пользователя → `curl -L` идёт по редиректам. Атакующий может сканировать внутреннюю сеть, обращаться к cloud metadata (`169.254.169.254`) и т.д.

### 9. HTTP (8000) работает параллельно с HTTPS (8443) без редиректа
**Файл:** `app/main.py`
Трафик на порт 8000 идёт в открытом виде. Нет middleware для принудительного HTTPS.

### 10. Path traversal в удалении backup
**Файл:** `app/api/vm_routes.py:297` + `app/services/vm_manager.py:635-639`
`backup_dir` — строка от пользователя без валидации. `shutil.rmtree(path)` удалит любую директорию (`../../../etc`).

---

## 🟠 ERROR HANDLING BUGS

### 11. Broad `except Exception` в login маскирует ошибки
**Файл:** `app/api/auth_routes.py:60-63`
```python
except Exception:
    raise HTTPException(status_code=500)
```
Ловит всё, включая `KeyboardInterrupt`, возвращая generic 500.

### 12. Silent error swallowing в `delete_vm`
**Файл:** `app/services/vm_manager.py:229-235`
```python
except Exception:
    pass
```
Дважды: для `cleanup_cloudinit_iso` и `delete_vm_ownership`. Ошибки БД глотаются молча.

### 13. `stop_vm`/`reboot_vm`/`reset_vm` не проверяют существование ВМ → 503 вместо 404
**Файл:** `app/services/vm_manager.py:159-189`
`start_vm` и `delete_vm` проверяют `conn.lookupByName` и возвращают 404. Остальные — нет, ловят libvirtError → 503.

### 14. File handle leak в `index()`
**Файл:** `app/main.py:147`
```python
return HTMLResponse(content=open(react_index, encoding="utf-8").read())
```
Файл не закрыт явно (нет `with`). В CPython GC закроет, но это не гарантировано. Может вызвать `Too many open files`.

### 15. Утечка: `import` модулей внутри `except` блоков
`croniter.is_valid` валидируется внутри `try/except ImportError` — если croniter не установлен, невалидные cron-выражения принимаются молча.

---

## 🟠 RESOURCE MANAGEMENT

### 16. Загрузка ISO целиком в RAM
**Файл:** `app/api/image_routes.py:84`
```python
content = file.file.read()
```
Для ISO в 4-8 ГБ — гарантированный OOM.

### 17. Подключение libvirt на каждый запрос
~30 функций в `vm_manager.py` открывают и закрывают libvirt-соединение. Это TCP-сокет с XML-RPC-рукопожатием и polkit-аутентификацией. При нагрузке >50 RPS — бутылочное горлышко.

### 18. SQLite — connection per call, нет пула
35+ функций в `database.py` создают новое соединение каждый вызов. Нет retry при `database is locked`.

---

## 🟡 CODE QUALITY

### 19. `import re` внутри функций (14 мест)
Файлы: `vm_manager.py` (строки 288, 366, 382, 416, 427), `libvirt_driver.py` (231, 268, 284, 331, 351, 402, 461, 492), `network.py` (90).

### 20. `__import__()` antipattern (3 места)
- `vm_manager.py:557` — `__import__('re').search(...)`
- `vm_routes.py:66` — `logger = __import__("logging").getLogger(...)`
- `libvirt_driver.py:496` — `__import__('uuid').uuid4()`

### 21. Парсинг XML через regex (15+ мест)
Весь разбор domain XML — через regex вместо `xml.etree.ElementTree`. XML не является регулярным языком → сломается при изменении форматирования или порядка атрибутов в libvirt.

### 22. Три независимые реализации разбора путей дисков из XML
`_get_disk_path`, `_get_disk_target`, inline-парсинг в `get_vm_info` — трижды дублированная regex-логика.

### 23. 1542 строки в `main.py`
Файл содержит: импорты, middleware, lifespan, scheduler, error handlers, routes, и 1362 строки встроенного HTML/JS/CSS (`_APP_HTML`). Файл должен быть разбит на 3-4 модуля.

### 24. 927 строк в `vm_manager.py`
Один файл = VM lifecycle + networking + snapshots + backups + cloud-init + export/import + resize + VNC.

---

## 🟡 ARCHITECTURE ISSUES

### 25. Нет слоя абстракции между бизнес-логикой и libvirt
`vm_manager.py` напрямую вызывает функции из `libvirt_driver`, `storage`, `network`, `cloud_init`. Тестирование требует `monkeypatch` на каждый вызов.

### 26. Backup scheduler живёт в `main.py`
```python
def _backup_scheduler_loop():   # main.py:26
```
Должен быть в отдельном модуле `services/scheduler.py`.

### 27. Нет dependency injection
Все сервисы — модульные функции с глобальным `settings`. Тесты — через `monkeypatch`.

---

## 🟡 LOGIC ISSUES

### 28. `storage.prepare_disk` — неявный fallback на `shutil.copy`
**Файл:** `app/infrastructure/storage.py:42-44`
Если `qemu-img create -b` падает, код молча делает полную копию (COW теряется) без предупреждения.

### 29. `generate_mac()` использует `random`, не `secrets`
**Файл:** `app/infrastructure/network.py:10-17`
```python
random.randrange(0x00, 0xFF)
```
При конкурентном создании ВМ возможны коллизии MAC-адресов.

### 30. VNC слушает на `0.0.0.0` без пароля
**Файл:** `app/services/vm_manager.py:884-886`
VNC-сервер открыт на всех интерфейсах без аутентификации. noVNC proxy защищает WebSocket, но raw-порт VNC доступен снаружи.

### 31. `block_resize` использует hardcode 512-байтовых секторов
**Файл:** `app/services/vm_manager.py:453`
```python
req.disk_gb * 1024**3 // 512
```
На дисках с 4K секторами — неверный размер.

---

## 🟢 MINOR ISSUES

| # | Файл | Проблема |
|---|------|----------|
| 32 | `app/config.py:12` | `LOG_LEVEL` без валидации |
| 33 | `app/services/vm_manager.py:924` | Путь к эмулятору захардкожен (`qemu-system-x86_64`) |
| 34 | `app/auth.py:19-22` | `secrets.token_hex(32)` выполняется при импорте, а не при старте |
| 35 | `app/infrastructure/network.py:10` | MAC-генерация без unicast-бита (первый байт может быть нечётным) |
| 36 | `tests/test_comprehensive.py:153` | Тест `test_auth_change_password` меняет пароль на "admin12345" → fragile |

---

## ИТОГИ ТЕСТИРОВАНИЯ В DOCKER

| Результат | Кол-во |
|-----------|--------|
| ✅ Passed | 98 |
| ❌ Failed | 3 |

### Причины падений:
1. **`test_get_vm_info_with_ip`** — `NameError: name 'database' is not defined` (Critical bug #1)
2. **`test_auth_login`** — 401 (зависит от окружения: пароль admin изменён предыдущими тестами)
3. **`test_auth_secured_endpoint`** — следствие #2

---

## СТАТУС ЗАПУСКА В DOCKER

| Компонент | Порт | Статус |
|-----------|------|--------|
| HTTPS (SSL) | 8443 | ✅ Работает |
| HTTP (legacy) | 8000 | ✅ Работает |
| React frontend | 8443 | ✅ Раздаётся |
| Auth JWT | 8443 | ✅ login/admin |
| Audit logs | 8443 | ✅ | 
| Health check | 8443 | ✅ `{"status":"ok"}` |
| libvirt socket | mount | ✅ `/var/run/libvirt` |
