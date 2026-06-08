This file records aggregated context from previous coding sessions — goals, constraints, progress, key decisions, and relevant file paths. It is updated at the end of each session so subsequent sessions start with full context.

## Goal
- Завершить миграцию с embedded HTML на Vite/React/TypeScript фронтенд; добавить аудит, guest-agent, runbook_url, HTTPS; написать тесты

## Constraints & Preferences
- Все изменения в ветке `fix/thesis-discrepancies`
- Аудит-лог пишется синхронно в SQLite, доступен админу через `GET /audit/logs`
- IP гостя запрашивается через `dom.interfaceAddresses(AGENT)`, guest-agent канал в XML новых ВМ
- Ошибки API возвращают `code`, `message`, `details`, `runbook_url`
- HTTPS порт 8443 (самоподписанный сертификат), HTTP порт 8000 legacy
- React-фронтенд собирается в multi-stage Docker build, раздаётся из `/app/frontend-dist/`
- При отсутствии React build используется embedded `_APP_HTML` как fallback
- Все тесты должны проходить перед мержем

## Progress
### Done
- **runbook_url**: `AppError` + словарь `RUNBOOK_URLS`, `details` и `runbook_url` в JSON-ответе
- **Guest agent**: `guest_agent_ip()` через `VIR_DOMAIN_INTERFACE_ADDRESSES_SOURCE_AGENT`, поле `guest_ip` в `get_vm_info()`/`list_vms()`, канал `org.qemu.guest_agent.0` в XML новых ВМ
- **Аудит**: таблица `audit_log`, `GET /audit/logs` (admin), интеграция во все key endpoints
- **HTTPS**: самоподписанный сертификат `certs/kvm-mgr.{key,crt}`, порт 8443, SSL env vars
- **React-фронтенд**: Vite + React + TypeScript, все страницы (Dashboard, Settings, AuditLog, ISOs, VMDetail)
- **Multi-stage Dockerfile**: React собирается в `node:20-slim`, копируется в `/app/frontend-dist/`
- **Static serving**: `index.html` из `/app/frontend-dist/` (fallback `_APP_HTML`), `/assets` из `/app/frontend-dist/assets/`
- **Поправлен баг snapshot `created`**: поле содержало полный XML вместо даты — `_extract_creation_time()` парсит `<creationTime>`
- **Поправлен баг Scheduler UI**: кнопка «+ Add Schedule» показывает форму через `showSchedForm` state
- **Loading-индикаторы**: `backupLoading`/`deletingBackup`/`snapLoading` для долгих операций
- **44 comprehensive теста**: auth (me/verify/register/admin/duplicate/unauthorized), backup schedules CRUD, audit log (filters + admin-only), host networks, VM backup list/delete, VM autostart, image upload/download/repo, network list, error structure, snapshot time extraction, clone VM, ownership access control
- **40 integration тестов**: create/start/stop/delete/attach-disk/health/images/host/vnc/snapshot/network/auth/export-import/clone/backup-restore/metrics
- **Все 84 теста проходят** (44 comprehensive + 40 integration)
- **Починена `set_vm_autostart`**: libvirtError при отсутствующей ВМ теперь возвращает 404 вместо 500
- **Установлен croniter**: валидация cron-выражений работает в тестах
- **Починены `start_vm`/`delete_vm`**: возвращают 404 вместо 503 при отсутствующей ВМ (проверка `conn.lookupByName` в `vm_manager.py`)
- **Аудит-лог не маскирует ошибки**: `_audit_log` wrapper ловит `Exception` и пишет warning вместо падения запроса (`vm_routes.py`, `auth_routes.py`)
- **Починено удаление ВМ со снепшотами**: `undefine_vm` использует `undefineFlags(VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA)` вместо `undefine()`
- **Валидация формы создания ВМ**: красное предупреждение о незаполненных полях вместо disabled кнопки
- **ISO-based создание ВМ**: поле ISO теперь первично, Image опционален; поле image использует полный путь; исправлен маппинг полей (ram→memory_mb, disk→disk_gb, iso→iso_path, ssh_key→cloud_init_ssh_key)
- **Backend fallback для пути**: если image/iso_path — голое имя файла, ищется в `storage_pool`
- **ISO репозиторий**: `ISO_REPO` в `image_manager.py` (Ubuntu/Debian/Fedora/CentOS/Rocky ISOs), `GET /images/repo/list` возвращает `type: "iso"/"cloud"` + `is_iso`, `POST /images/download-repo-iso` скачивает ISO в storage_pool, фронтенд Repo страница показывает ISOs с бейджем и отдельным обработчиком

### In Progress
- *(none)*

### Blocked
- *(none)*

## Key Decisions
- Аудит синхронно в SQLite (достаточно для single-node)
- Guest agent IP через `interfaceAddresses(AGENT)` — безопасный вызов, не падает при отсутствии qemu-ga
- `runbook_url` автоподставляется из словаря по коду ошибки
- React-фронтенд — замена embedded HTML, dev-режим с прокси к `:8000` через Vite
- Snapshot `created` — извлечение unix-таймстампа из XML → ISO datetime (не полный XML)
- Loading-индикаторы через отдельные state-переменные
- TestClient из conftest.py переопределяет `get_current_user` → admin; тесты для non-admin/unauthorized временно меняют `app.dependency_overrides`

## Next Steps
- Исправить предупреждения: мигрировать `on_event` на lifespan, увеличить JWT_SECRET_KEY до 32+ байт, поправить `DB_PATH` по умолчанию
- Выполнить `git checkout master && git merge fix/thesis-discrepancies` после подтверждения

## Critical Context
- **Бранч**: `fix/thesis-discrepancies`
- **DB_PATH**: `/data/kvm_manager.db` — SQLite
- **croniter>=1.3.0** в `requirements.txt` — валидация cron-выражений
- **libvirt-python** — системный пакет, сокет `/var/run/libvirt/libvirt-sock`
- **84 теста проходят**: 44 comprehensive + 40 integration

## Relevant Files
- `app/errors.py`: `RUNBOOK_URLS`, `AppError` с `runbook_url`
- `app/database.py`: `audit_log` таблица, `create_audit_log()`, `list_audit_logs()`
- `app/api/audit_routes.py`: `GET /audit/logs` (admin, фильтры)
- `app/api/vm_routes.py`: аудит во всех key endpoints
- `app/api/auth_routes.py`: аудит login/register/change_password
- `app/infrastructure/libvirt_driver.py`: `guest_agent_ip()`, `_extract_creation_time()`
- `app/services/vm_manager.py`: `set_vm_autostart()` — 404 при libvirtError
- `tests/test_comprehensive.py`: 44 теста с манипуляцией dependency_overrides
- `tests/test_integration_api.py`: 40 существующих тестов
- `tests/conftest.py`: переопределение `get_current_user` → admin
- `frontend/`: React-фронтенд (Vite + TypeScript)
