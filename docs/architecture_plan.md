# План архитектуры системы управления виртуальными машинами (KVM + libvirt)

Дата: 2026-05-01

## Цель документа

Дать структурированное и практически применимое описание архитектуры системы управления виртуальными машинами на базе KVM с использованием libvirt. Документ ориентирован на выпускную работу (диплом) и реализацию промышленного решения.

## Ключевые требования

- Использовать libvirt как низкоуровневый драйвер управления гипервизором.
- Предоставить REST API для управления ВМ: создание, запуск, остановка, удаление, просмотр статуса.
- Поддержка асинхронных длительных операций (provisioning) и надёжных откатов.

## Краткое архитектурное описание

Система разделена на несколько логических слоёв:

- Presentation (REST API): FastAPI (Python) — входная точка для клиентов и UI, валидация, аутентификация, rate-limit.
- Control Plane (Orchestrator): бизнес-логика, планирование размещения, проверка квот, формирование задач.
- Workers (Task Executors): фоновые воркеры (Celery + RabbitMQ/Redis или RQ) для выполнения длительных операций.
- Libvirt Adapter (Driver Layer): thin-wrapper над `python-libvirt`, генерация domain XML, управление подключениями к libvirtd (TLS/SSH).
- Metadata Store: PostgreSQL — описание ВМ, хостов, образов, задач, событий.
- Message Broker: RabbitMQ или Redis — очередь задач, уведомления.
- Storage: Ceph/RBD, NFS или локальные qcow2 для дисков ВМ.
- Network Manager: bridge / OVS / VLAN, интеграция с DHCP/IPAM при необходимости.
- Observability & Security: Prometheus, ELK/EFK, TLS, RBAC, audit log.

## Схема высокоуровневого взаимодействия

Client -> REST API -> Orchestrator -> Task Queue -> Worker -> Libvirt Adapter -> Compute Node (libvirtd)

API и БД служат единой точкой правды для метаданных; очередь обеспечивает асинхронность.

## Компоненты и их ответственность

- REST API (FastAPI)
  - Авторизация/аутентификация (JWT/RBAC).
  - Валидация запросов (Pydantic).
  - CRUD и публикация задач (task_id) для длительных операций.

- Orchestrator (API service или отдельный сервис)
  - Проверки квот, бизнес-правила, выбор целевого хоста (scheduler).
  - Создание записей в БД: `tasks`, `vms` (status=creating).

- Task Queue / Workers (Celery)
  - Подготовка дисков (клонирование/создание), генерация XML, вызовы libvirt (define/create/destroy).
  - Повторные попытки, backoff, compensation (rollback) при ошибках.

- Libvirt Adapter
  - Унификация работы с libvirt: open, defineXML, create, destroy, snapshot.
  - Поддержка разных коннекторов: `qemu+ssh://`, `qemu+tls://`.

- Metadata DB (Postgres)
  - Таблицы: `vms`, `hosts`, `images`, `tasks`, `events`, `users`, `quotas`.

- Storage Manager
  - Создание/клонирование/удаление дисков, snapshot, resize.

- Network Manager
  - Выделение MAC/IP, управление bridge/VLAN/OVS.

## Безопасность и надёжность

- TLS/mTLS для всех внутренних соединений (API <-> Worker, Worker <-> libvirtd при возможности).
- RBAC и audit log для всех операций.
- Idempotency: `client_token` для операций создания ВМ.
- Distributed locking (Redis locks или SELECT FOR UPDATE) при выделении ресурсов и выборе хоста.
- Transactional resource reservation: сначала reserve в БД, затем provisioning.

## Масштабируемость и отказоустойчивость

- Stateless API (масштабирование через replicas behind load balancer).
- Workers — горизонтально масштабируемые, очередь обеспечивает распределение.
- Storage — использование распределённых хранилищ (Ceph/RBD) для быстрого клонирования и live-migration.
- Monitoring: health checks на сервисы, auto-restart, alerting.

## Технологический стек (рекомендации)

- Язык: Python 3.11+
- REST API: FastAPI + Pydantic
- Queue: RabbitMQ или Redis + Celery
- DB: PostgreSQL (Alembic для миграций)
- Libvirt: python-libvirt
- Storage: Ceph/RBD или qcow2 + qemu-img
- Auth: Keycloak (опционально) или JWT + internal RBAC
- Observability: Prometheus + Grafana, EFK/ELK
- CI/CD: GitHub Actions / GitLab CI

## Структура проекта (пример)

- infra/
  - docker-compose.yml, k8s/
- api/
  - app.py, routes/, schemas.py, services/, db.py, config.py
- worker/
  - celery_app.py, tasks/vm_tasks.py, services/storage.py
- libvirt_adapter/
  - driver.py, xml_templates/
- models/
  - vm.py, host.py, task.py
- migrations/ (Alembic)
- docs/ (архитектура, API спецификация)

## Поток запроса: создание ВМ (детально)

1. Клиент -> POST /v1/vms
   - Передаёт: name, template/image, cpu, memory_mb, disk_gb, network.
2. REST API
   - Аутентификация + авторизация.
   - Валидация схемы запроса.
   - Проверка квот (в БД).
   - Scheduler выбирает хост (first-fit / bin-packing).
   - Создаёт транзакцию: insert `tasks` (queued), insert `vms` (creating).
   - Возвращает `202 Accepted` с `task_id` и `vm_id`.
3. Orchestrator -> Queue
   - Публикует задачу provisioning в очередь с параметрами: vm_id, host_id, spec.
4. Worker
   - Захватывает lock на host.
   - Подготавливает диск (клонирование image или создание qcow2).
   - Резервирует network (MAC/IP).
   - Генерирует domain XML по шаблону.
   - Через Libvirt Adapter выполняет `defineXML` и `create`.
   - При успехе: обновляет `vms.status = running`, сохраняет domain UUID.
   - При ошибке: rollback (удаление дисков, освобождение ресурсов), `vms.status = error`.
5. Post-provisioning
   - Poller / libvirt events обновляют финальные статусы в БД.

## Контракты и API (кратко)

- POST /v1/vms — создание (202 + task_id)
- GET /v1/vms/{id} — информация и status
- POST /v1/vms/{id}/start — запуск
- POST /v1/vms/{id}/stop — остановка
- DELETE /v1/vms/{id} — удаление (enqueue)
- GET /v1/tasks/{task_id} — статус операции

## Рекомендации для диплома и реализации

- В дипломе: опишите trade-offs (single-host vs distributed storage, sync vs async), обоснуйте выбор технологий.
- Реализация: начните с минимального POC — `FastAPI` + `Celery` + `python-libvirt` и одним тестовым host, затем добавляйте storage/network интеграции.
- Тестирование: unit для адаптера libvirt (mock), integration tests с контейнеризированным libvirtd (или QEMU test host).

## Дальнейшие шаги

- Подготовить skeleton проекта: minimal FastAPI + Celery + libvirt adapter.
- Сгенерировать Jinja2-шаблон для domain XML и пример `driver.py`.
- Написать сценарий для тестового стенда (provision виртуальной машины на локальном KVM).

Файл создан: docs/architecture_plan.md
