This file records aggregated context from previous coding sessions — goals, constraints, progress, key decisions, and relevant file paths. It is updated at the end of each session so subsequent sessions start with full context.

## Goal
- Запустить KVM/libvirt проект в Docker, проанализировать ошибки с визуалом и добавить отображение сети/IP в дашборд

## Constraints & Preferences
- Запуск через `docker-compose`
- UI должен корректно отображать сетевые интерфейсы, DHCP leases и образы репозитория

## Progress
### Done
- Собран образ и запущен контейнер `kvm-mgr-app` через `docker-compose up -d app`
- Проверены эндпоинты: `/health`, `/host/info`, `/host/stats`, `/vm/list`, `/images/list`, `/auth/login` — все работают
  - Все 57 тестов проходят (57 passed, 8 warnings)
- В бэкенд добавлен `network_leases()` (`app/infrastructure/libvirt_driver.py`), `get_network_leases()` (`app/services/vm_manager.py`), эндпоинт `GET /host/networks` (`app/api/host_routes.py`) — возвращает список сетей и DHCP leases (проверено: 2 сети, 1 lease)
- В дашборд добавлен блок **Network Interfaces** (сетки и таблица аренды IP) в `app/main.py` (JS-функции `netTable()`, `leaseTable()`)
- Исправлена вкладка **Repo Images**: в `loadRepoImages()` добавлены `e.preventDefault()` и `return false`
- Исправлены вкладка **ISOs** и кнопки **Upload ISO**/**Download from URL**: добавлены `e.preventDefault()` и `return false` для `loadISOs`, `loadSettings`, `showUploadIsoDialog`, `showDownloadIsoDialog`
- Добавлен **Backup scheduler** (фоновый поток с cron):
  - таблица `backup_schedules` в БД (CRUD через `database.py`)
  - API `GET/POST/PUT/DELETE /vm/backup/schedules` (`vm_routes.py`)
  - фоновый шедулер в `main.py` (проверка крона каждые 60 сек, запуск `backup_vm()`)
- Обогащена страница **Settings**:
  - секция **Host Info** (CPU/архитектура/память)
  - секция **Storage** (пул/использовано/свободно)
  - секция **Backup Schedules** (добавить/редактировать/удалить расписания)

### In Progress
- *(none)*

### Blocked
- *(none)*

## Key Decisions
- Сетевой эндпоинт `/host/networks` объединён (сети + leases в одном ответе), чтобы фронтенд делал один запрос
- Все `onclick` функции в боковом меню должны вызывать `e.preventDefault()` (если есть event) **и** возвращать `false`

## Next Steps
- Исправить предупреждения: мигрировать `on_event` на `lifespan`, увеличить JWT_SECRET_KEY до 32+ байт, поправить `DB_PATH` по умолчанию
- Добавить экранирование имён VM/образов в шаблонных строках UI (XSS-потенциал)

## Critical Context
- **Deprecation**: `@app.on_event("startup")` — заменить на lifespan
- **JWT**: `HMAC key is 23 bytes` — ключ `"change-me-in-production"` короче 32 байт
- **DB_PATH**: по умолчанию `/data/kvm_manager.db` — директория `/data` может не существовать
- API `/images/repo/list` публичный (без auth), остальные закрыты `Bearer` токеном
- libvirt-python установлен, сокет `/var/run/libvirt/libvirt-sock` доступен

## Relevant Files
- `docker-compose.yml`: сборка и запуск сервисов app/tests
- `app/main.py`: FastAPI-приложение, вся фронтенд-логика (JS + HTML), роутеры
- `app/infrastructure/libvirt_driver.py`: `network_leases()` — получение DHCP leases всех сетей
- `app/services/vm_manager.py`: `get_network_leases()` — обёртка над libvirt_driver
- `app/api/host_routes.py`: эндпоинт `GET /host/networks` (сети + leases)
- `app/services/image_manager.py`: список и скачивание облачных образов
- `app/api/image_routes.py`: роуты `/images/repo/list`, `/images/download-cloud` и др.
- `app/auth.py`: JWT-аутентификация, `SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production")`
