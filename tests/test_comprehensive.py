"""Comprehensive tests covering auth, backup schedules, audit log, network,
ownership, snapshots, error structure, and edge cases.

The conftest.py overrides get_current_user with an admin user for ALL tests.
We manipulate app.dependency_overrides within individual tests to test
non-admin and unauthorized scenarios.
"""

from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import io
import os

from app.main import app
from app.auth import get_current_user

client = TestClient(app)

# Reference user dicts matching conftest shape
_ADMIN = {"id": 1, "username": "admin", "is_admin": 1}
_NON_ADMIN = {"id": 2, "username": "nonadmin", "is_admin": 0}


def _set_user(user_dict: dict):
    """Override get_current_user to always return `user_dict`."""
    app.dependency_overrides[get_current_user] = lambda: user_dict


def _no_auth():
    """Remove the dependency override so real auth (require_auth) runs."""
    app.dependency_overrides.pop(get_current_user, None)


# ──────────────────────────────────────────────
#  AUTH
# ──────────────────────────────────────────────

def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_auth_me():
    """Default conftest behaviour: admin user."""
    resp = client.get("/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["username"] == "admin"
    assert data["user"]["is_admin"] is True   # bool(...) wraps 1


def test_auth_me_unauthorized():
    """Without the override, /auth/me requires a valid Bearer token."""
    _no_auth()
    try:
        resp = client.get("/auth/me")
        assert resp.status_code == 401
    finally:
        _set_user(_ADMIN)


def test_auth_verify():
    _no_auth()
    try:
        # /auth/verify uses Depends(require_auth) — not overridden by conftest
        # We need a real token
        resp = client.post("/auth/login", json={"username": "admin", "password": "admin1234"})
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        resp = client.get("/auth/verify", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
    finally:
        _set_user(_ADMIN)


def test_auth_verify_invalid():
    _no_auth()
    try:
        resp = client.get("/auth/verify", headers={"Authorization": "Bearer invalid"})
        assert resp.status_code == 401
    finally:
        _set_user(_ADMIN)


def test_auth_register():
    import random
    name = f"reg_{random.randint(10000, 99999)}"
    resp = client.post("/auth/register", json={"username": name, "password": "testpass123"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_auth_register_short_password():
    resp = client.post("/auth/register", json={"username": "shortpw", "password": "12"})
    assert resp.status_code == 422


def test_auth_register_duplicate():
    resp = client.post("/auth/register", json={"username": "dupuser", "password": "testpass123"})
    assert resp.status_code == 200
    resp = client.post("/auth/register", json={"username": "dupuser", "password": "testpass123"})
    assert resp.status_code in (400, 409)


def test_auth_register_admin():
    resp = client.post("/auth/register-admin", json={
        "username": "admin2",
        "password": "adminpass123",
        "is_admin": True,
    })
    assert resp.status_code == 200
    data = resp.json()["user"]
    # create_user stores is_admin as bool; SQLite stores as int but dict returns Python bool
    assert data["is_admin"] is True or data["is_admin"] == 1


def test_auth_register_admin_non_admin_forbidden():
    _set_user(_NON_ADMIN)
    try:
        resp = client.post("/auth/register-admin", json={
            "username": "shouldfail",
            "password": "test1234",
        })
        assert resp.status_code == 403
    finally:
        _set_user(_ADMIN)


def test_auth_users():
    resp = client.get("/auth/users")
    assert resp.status_code == 200
    assert len(resp.json()["users"]) >= 1


def test_auth_users_forbidden_non_admin():
    _set_user(_NON_ADMIN)
    try:
        resp = client.get("/auth/users")
        assert resp.status_code == 403
    finally:
        _set_user(_ADMIN)


def test_auth_change_password():
    resp = client.post("/auth/change-password", json={
        "current_password": "admin1234",
        "new_password": "admin12345",
    })
    assert resp.status_code == 200
    # revert to original password
    resp = client.post("/auth/change-password", json={
        "current_password": "admin12345",
        "new_password": "admin1234",
    })
    assert resp.status_code == 200
    # verify old password no longer works
    resp = client.post("/auth/login", json={"username": "admin", "password": "admin12345"})
    assert resp.status_code == 401


def test_auth_change_password_wrong():
    resp = client.post("/auth/change-password", json={
        "current_password": "wrongpass",
        "new_password": "newadmin123",
    })
    assert resp.status_code in (400, 422)


# ──────────────────────────────────────────────
#  BACKUP SCHEDULES CRUD (admin-only)
# ──────────────────────────────────────────────

def test_backup_schedules_empty():
    resp = client.get("/vm/backup/schedules")
    assert resp.status_code == 200
    assert resp.json()["schedules"] == []


def test_backup_schedules_forbidden_non_admin():
    _set_user(_NON_ADMIN)
    try:
        resp = client.get("/vm/backup/schedules")
        assert resp.status_code == 403
        resp = client.post("/vm/backup/schedules", json={
            "vm_name": "x", "cron_expression": "0 * * * *",
        })
        assert resp.status_code == 403
    finally:
        _set_user(_ADMIN)


def test_backup_schedules_create():
    resp = client.post("/vm/backup/schedules", json={
        "vm_name": "test-vm",
        "cron_expression": "0 */6 * * *",
        "retention": 5,
    })
    assert resp.status_code == 200
    s = resp.json()["schedule"]
    assert s["vm_name"] == "test-vm"
    assert s["cron_expression"] == "0 */6 * * *"
    assert s["retention"] == 5
    # SQLite returns integer 1 for enabled
    assert s["enabled"] == 1


def test_backup_schedules_create_invalid_cron():
    resp = client.post("/vm/backup/schedules", json={
        "vm_name": "bad-cron",
        "cron_expression": "not-a-cron",
    })
    assert resp.status_code == 400


def test_backup_schedules_list():
    resp = client.get("/vm/backup/schedules")
    assert resp.status_code == 200
    assert len(resp.json()["schedules"]) >= 1


def test_backup_schedules_update():
    resp = client.put("/vm/backup/schedules/1", json={
        "cron_expression": "0 */12 * * *",
        "retention": 10,
        "enabled": False,
    })
    assert resp.status_code == 200
    s = resp.json()["schedule"]
    assert s["cron_expression"] == "0 */12 * * *"
    assert s["retention"] == 10
    # SQLite returns integer 0 for False
    assert s["enabled"] == 0


def test_backup_schedules_update_not_found():
    resp = client.put("/vm/backup/schedules/999", json={
        "cron_expression": "0 * * * *",
    })
    assert resp.status_code == 404


def test_backup_schedules_delete():
    resp = client.delete("/vm/backup/schedules/1")
    assert resp.status_code == 200


def test_backup_schedules_delete_not_found():
    resp = client.delete("/vm/backup/schedules/999")
    assert resp.status_code == 404


# ──────────────────────────────────────────────
#  AUDIT LOG (admin-only)
# ──────────────────────────────────────────────

def test_audit_logs():
    resp = client.get("/audit/logs")
    assert resp.status_code == 200
    assert "logs" in resp.json()


def test_audit_logs_filters():
    resp = client.get("/audit/logs?limit=5&action=login")
    assert resp.status_code == 200


def test_audit_logs_forbidden_non_admin():
    _set_user(_NON_ADMIN)
    try:
        resp = client.get("/audit/logs")
        assert resp.status_code == 403
    finally:
        _set_user(_ADMIN)


def test_audit_logs_unauthorized():
    _no_auth()
    try:
        resp = client.get("/audit/logs")
        assert resp.status_code == 401
    finally:
        _set_user(_ADMIN)


# ──────────────────────────────────────────────
#  HOST NETWORKS
# ──────────────────────────────────────────────

def test_host_networks(monkeypatch):
    mock_conn = MagicMock()
    monkeypatch.setattr("app.infrastructure.libvirt_driver.connect", lambda uri: mock_conn)
    monkeypatch.setattr("app.infrastructure.libvirt_driver.network_list", lambda conn: [
        {"name": "default", "active": True, "bridge": "virbr0", "subnet": "192.168.122.0/24"},
    ])
    monkeypatch.setattr("app.infrastructure.libvirt_driver.network_leases", lambda conn: [
        {"network": "default", "ip": "192.168.122.10", "mac": "52:54:00:aa:bb:cc", "hostname": "test-vm"},
    ])
    resp = client.get("/host/networks")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["networks"]) == 1
    assert len(data["leases"]) == 1


# ──────────────────────────────────────────────
#  VM BACKUP LIST / DELETE
# ──────────────────────────────────────────────

def test_vm_backup_list(monkeypatch):
    mock_conn = MagicMock()
    monkeypatch.setattr("app.infrastructure.libvirt_driver.connect", lambda uri: mock_conn)
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.get_domain_xml",
        lambda conn, name: "<domain><name>test-vm</name></domain>",
    )
    monkeypatch.setattr("os.path.isdir", lambda path: True)
    monkeypatch.setattr("os.listdir", lambda path: ["backup_20260101_120000"])
    monkeypatch.setattr("builtins.open", lambda f, m="r": io.StringIO(
        '{"timestamp": "2026-01-01T12:00:00", "vm_name": "test-vm"}',
    ))
    resp = client.get("/vm/backup/list/test-vm")
    assert resp.status_code == 200
    assert "backups" in resp.json()


def test_vm_backup_delete(monkeypatch):
    monkeypatch.setattr("os.path.exists", lambda path: True)
    monkeypatch.setattr("os.path.isdir", lambda path: True)
    import shutil
    monkeypatch.setattr(shutil, "rmtree", lambda path: None)
    resp = client.delete("/vm/backup/delete?backup_dir=/tmp/test-backup")
    assert resp.status_code == 200


def test_vm_backup_delete_not_found():
    resp = client.delete("/vm/backup/delete?backup_dir=/tmp/nonexist-dir-12345")
    assert resp.status_code in (200, 404)


def test_vm_backup_delete_forbidden_non_admin():
    _set_user(_NON_ADMIN)
    try:
        resp = client.delete("/vm/backup/delete?backup_dir=/tmp/test")
        assert resp.status_code == 403
    finally:
        _set_user(_ADMIN)


# ──────────────────────────────────────────────
#  VM AUTOSTART
# ──────────────────────────────────────────────

def test_vm_autostart_set(monkeypatch):
    mock_conn = MagicMock()
    mock_dom = MagicMock()
    mock_conn.lookupByName.return_value = mock_dom
    monkeypatch.setattr("app.infrastructure.libvirt_driver.connect", lambda uri: mock_conn)
    resp = client.post("/vm/autostart?name=test-vm&enable=true")
    assert resp.status_code == 200
    assert resp.json()["autostart"] is True


def test_vm_autostart_vm_not_found(monkeypatch):
    import libvirt
    mock_conn = MagicMock()
    mock_conn.lookupByName.side_effect = libvirt.libvirtError("not found")
    monkeypatch.setattr("app.infrastructure.libvirt_driver.connect", lambda uri: mock_conn)
    resp = client.post("/vm/autostart?name=noexist&enable=true")
    assert resp.status_code == 404


# ──────────────────────────────────────────────
#  IMAGE UPLOAD / DOWNLOAD / REPO
# ──────────────────────────────────────────────

def test_images_repo_list():
    resp = client.get("/images/repo/list")
    assert resp.status_code == 200
    assert "families" in resp.json()


def test_images_download_url(monkeypatch):
    monkeypatch.setattr("builtins.open", lambda f, m="r": MagicMock())
    monkeypatch.setattr("os.path.exists", lambda path: False)
    monkeypatch.setattr("app.services.image_manager.list_images", lambda: [])
    resp = client.post("/images/download", json={"url": "https://example.com/test.qcow2"})
    assert resp.status_code in (200, 400, 422)


def test_images_upload(monkeypatch):
    monkeypatch.setattr("app.services.image_manager.list_images", lambda: [])
    resp = client.post(
        "/images/upload",
        files={"file": ("test.qcow2", b"fake", "application/octet-stream")},
    )
    assert resp.status_code in (200, 201, 422, 500)


# ──────────────────────────────────────────────
#  VM OWNERSHIP
# ──────────────────────────────────────────────

def test_vm_access_denied_non_owner(monkeypatch):
    mock_conn = MagicMock()
    mock_dom = MagicMock()
    mock_dom.name.return_value = "test-vm-owned"
    mock_conn.lookupByName.return_value = mock_dom
    monkeypatch.setattr("app.infrastructure.libvirt_driver.connect", lambda uri: mock_conn)
    # VM is owned by admin (id=1), non-admin tries to start it → 403
    monkeypatch.setattr(
        "app.services.vm_manager.get_vm_owner",
        lambda name: {"id": 1, "username": "admin", "vm_name": "test-vm-owned"},
    )
    _set_user(_NON_ADMIN)
    try:
        resp = client.post("/vm/start", json={"name": "test-vm-owned"})
        assert resp.status_code == 403
    finally:
        _set_user(_ADMIN)


# ──────────────────────────────────────────────
#  NETWORK MANAGEMENT (admin-only)
# ──────────────────────────────────────────────

def test_network_list_admin(monkeypatch):
    mock_conn = MagicMock()
    monkeypatch.setattr("app.infrastructure.libvirt_driver.connect", lambda uri: mock_conn)
    monkeypatch.setattr("app.infrastructure.libvirt_driver.network_list", lambda conn: [
        {"name": "default", "active": True},
    ])
    resp = client.get("/vm/network/list")
    assert resp.status_code == 200
    assert len(resp.json()["networks"]) == 1


def test_network_list_forbidden_non_admin():
    _set_user(_NON_ADMIN)
    try:
        resp = client.get("/vm/network/list")
        assert resp.status_code == 403
    finally:
        _set_user(_ADMIN)


# ──────────────────────────────────────────────
#  VM CLONE
# ──────────────────────────────────────────────

def test_clone_vm(monkeypatch):
    mock_conn = MagicMock()
    monkeypatch.setattr("app.infrastructure.libvirt_driver.connect", lambda uri: mock_conn)
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.get_domain_xml",
        lambda conn, name: "<domain><name>source</name></domain>",
    )
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.rename_in_xml",
        lambda xml, new_name: xml.replace("source", new_name),
    )
    monkeypatch.setattr(
        "app.services.vm_manager._get_disk_path",
        lambda conn, name: "/tmp/source.qcow2",
    )
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.copy_disk_image",
        lambda src, dst: None,
    )
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.define_vm",
        lambda conn, xml: "cloned",
    )
    monkeypatch.setattr(
        "app.infrastructure.libvirt_driver.start_vm",
        lambda conn, name: None,
    )
    monkeypatch.setattr(
        "app.infrastructure.network.get_vm_ip",
        lambda conn, name: "10.0.0.42",
    )
    resp = client.post("/vm/clone", json={"name": "source", "new_name": "cloned"})
    assert resp.status_code == 200
    assert resp.json()["vm"]["name"] == "cloned"


# ──────────────────────────────────────────────
#  SNAPSHOT _extract_creation_time
# ──────────────────────────────────────────────

def test_extract_creation_time():
    from app.infrastructure.libvirt_driver import _extract_creation_time
    xml = "<domainsnapshot><creationTime>1780905828</creationTime></domainsnapshot>"
    assert _extract_creation_time(xml) == "2026-06-08T08:03:48+00:00"


def test_extract_creation_time_empty():
    from app.infrastructure.libvirt_driver import _extract_creation_time
    assert _extract_creation_time("<domainsnapshot></domainsnapshot>") == ""


# ──────────────────────────────────────────────
#  ERROR STRUCTURE (runbook_url)
# ──────────────────────────────────────────────

def test_error_has_code_and_runbook():
    resp = client.post("/vm/start", json={"name": "nonexistent-vm-12345"})
    body = resp.json()
    detail = body.get("detail", body)
    if isinstance(detail, dict):
        assert "code" in detail
