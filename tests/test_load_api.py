"""Load/stress tests for the KVM Manager API.

Tests endpoints that do NOT require libvirt (health, auth, audit, images).
Concurrent requests to verify non-blocking behaviour.
"""

import os
import sys
import pytest
import concurrent.futures
from unittest.mock import patch, MagicMock

os.environ["DB_PATH"] = "/tmp/kvm_load_test.db"
os.environ["JWT_SECRET_KEY"] = "load-test-secret-key-32-bytes-minimum!!"
os.environ["STORAGE_POOL"] = "/tmp/kvm_load_test_pool"

for p in [os.environ["DB_PATH"], os.environ["DB_PATH"] + "-wal", os.environ["DB_PATH"] + "-shm"]:
    try:
        os.remove(p)
    except FileNotFoundError:
        pass

# libvirt stub from conftest handles this; don't replace sys.modules

from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db, create_user
from app.auth import create_access_token

init_db()
try:
    create_user("admin", "admin1234", is_admin=True)
except ValueError:
    pass

admin_token = create_access_token({"sub": "admin", "user_id": 1})
headers = {"Authorization": f"Bearer {admin_token}"}

ENDPOINTS_NO_AUTH = [
    ("GET", "/health"),
]

ENDPOINTS_WITH_AUTH = [
    ("GET", "/auth/me"),
    ("GET", "/api/images"),
    ("GET", "/api/images/cloud/list"),
    ("GET", "/api/images/repo/list"),
    ("GET", "/audit/logs"),
]

REQUEST_COUNT = 20
CONCURRENCY = 10


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestLoadEndpoints:
    def test_concurrent_health_requests(self, client):
        futures = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            for _ in range(REQUEST_COUNT):
                futures.append(pool.submit(client.get, "/health"))
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        assert all(r.status_code == 200 for r in results)
        assert len(results) == REQUEST_COUNT

    def test_concurrent_auth_requests(self, client):
        futures = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            for _ in range(REQUEST_COUNT):
                futures.append(pool.submit(client.get, "/auth/me", headers=headers))
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        assert all(r.status_code == 200 for r in results)
        assert len(results) == REQUEST_COUNT

    def test_concurrent_images(self, client):
        futures = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            for _ in range(REQUEST_COUNT // 2):
                futures.append(pool.submit(client.get, "/api/images", headers=headers))
                futures.append(pool.submit(client.get, "/api/images/cloud/list", headers=headers))
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        failed = [r for r in results if r.status_code >= 500]
        assert len(failed) == 0, f"{len(failed)} requests returned 5xx"

    def test_concurrent_audit(self, client):
        futures = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            for _ in range(REQUEST_COUNT):
                futures.append(pool.submit(client.get, "/audit/logs", headers=headers))
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        failed = [r for r in results if r.status_code >= 500]
        assert len(failed) == 0

    def test_mixed_endpoints_sequential(self, client):
        for _, path in ENDPOINTS_NO_AUTH:
            resp = client.get(path)
            assert resp.status_code < 500, f"GET {path} returned {resp.status_code}"
        for _, path in ENDPOINTS_WITH_AUTH:
            resp = client.get(path, headers=headers)
            assert resp.status_code < 500, f"GET {path} returned {resp.status_code}"
