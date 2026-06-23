"""Unit tests for app.database — all DB functions with isolated temp SQLite."""

import os
import tempfile
import pytest

os.environ["DB_PATH"] = tempfile.mktemp(suffix=".db")

from app.database import (
    init_db, hash_password, verify_password,
    create_user, get_user_by_username, get_user_by_login, get_user_by_id,
    list_users, update_password,
    set_vm_owner, get_vm_owner, get_vm_root_password, list_vms_for_user,
    delete_vm_ownership,
    create_backup_schedule, list_backup_schedules, get_backup_schedule,
    update_backup_schedule, delete_backup_schedule, get_enabled_backup_schedules,
    update_backup_schedule_last_run,
    create_audit_log, list_audit_logs,
)

init_db()


class TestPasswordHashing:
    def test_hash_and_verify(self):
        pw = hash_password("test1234")
        assert ":" in pw
        assert verify_password("test1234", pw) is True

    def test_verify_wrong(self):
        pw = hash_password("correct")
        assert verify_password("wrong", pw) is False

    def test_different_salts(self):
        p1 = hash_password("same")
        p2 = hash_password("same")
        assert p1 != p2


class TestUserCRUD:
    def test_create_and_get_by_username(self):
        user = create_user("alice", "alice1234", is_admin=False)
        assert user["username"] == "alice"
        assert user["is_admin"] is False

        fetched = get_user_by_username("alice")
        assert fetched is not None
        assert fetched["username"] == "alice"

    def test_create_admin(self):
        user = create_user("bob", "bob12345", is_admin=True)
        assert user["is_admin"] is True

    def test_get_by_login_username(self):
        user = get_user_by_login("alice")
        assert user is not None
        assert user["username"] == "alice"

    def test_get_by_login_email(self):
        user = get_user_by_login("admin@localhost")
        assert user is not None

    def test_get_by_id(self):
        user = get_user_by_id(1)
        assert user is not None
        assert user["username"] == "admin"

    def test_get_by_id_missing(self):
        assert get_user_by_id(99999) is None

    def test_create_duplicate(self):
        with pytest.raises(ValueError, match="already exists"):
            create_user("alice", "test1234")

    def test_list_users(self):
        users = list_users()
        assert len(users) >= 3
        usernames = [u["username"] for u in users]
        assert "admin" in usernames
        assert "alice" in usernames

    def test_update_password(self):
        update_password(1, "newpass1234")
        user = get_user_by_id(1)
        salt, h = user["password_hash"].split(":")
        import hashlib
        assert hashlib.sha256((salt + "newpass1234").encode()).hexdigest() == h


class TestVMOwnership:
    def test_set_and_get_owner(self):
        set_vm_owner("vm-alpha", 1, root_password="rootpw123")
        owner = get_vm_owner("vm-alpha")
        assert owner is not None
        assert owner["username"] == "admin"
        assert owner["root_password"] == "rootpw123"

    def test_get_root_password(self):
        pw = get_vm_root_password("vm-alpha")
        assert pw == "rootpw123"

    def test_get_root_password_missing(self):
        assert get_vm_root_password("nonexistent") is None

    def test_list_vms_for_user(self):
        set_vm_owner("vm-beta", 2)
        vms = list_vms_for_user(2)
        assert "vm-beta" in vms

    def test_delete_ownership(self):
        set_vm_owner("vm-gamma", 1)
        delete_vm_ownership("vm-gamma")
        assert get_vm_owner("vm-gamma") is None


class TestBackupSchedules:
    def test_create_and_list(self):
        sched = create_backup_schedule("vm-sched-1", "0 */6 * * *", retention=5)
        assert sched["vm_name"] == "vm-sched-1"
        assert sched["retention"] == 5

        schedules = list_backup_schedules()
        names = [s["vm_name"] for s in schedules]
        assert "vm-sched-1" in names

    def test_create_duplicate(self):
        with pytest.raises(ValueError, match="already exists"):
            create_backup_schedule("vm-sched-1", "0 * * * *")

    def test_get_schedule(self):
        scheds = list_backup_schedules()
        sid = scheds[0]["id"]
        sched = get_backup_schedule(sid)
        assert sched is not None
        assert sched["id"] == sid

    def test_get_schedule_missing(self):
        assert get_backup_schedule(99999) is None

    def test_update_schedule(self):
        scheds = list_backup_schedules()
        sid = scheds[0]["id"]
        updated = update_backup_schedule(sid, cron_expression="0 */12 * * *", retention=10, enabled=False)
        assert updated["cron_expression"] == "0 */12 * * *"
        assert updated["retention"] == 10
        assert updated["enabled"] == 0

    def test_update_schedule_no_fields(self):
        scheds = list_backup_schedules()
        sid = scheds[0]["id"]
        updated = update_backup_schedule(sid)
        assert updated is not None

    def test_get_enabled_schedules(self):
        enabled = get_enabled_backup_schedules()
        for s in enabled:
            assert s["enabled"] == 1

    def test_update_last_run(self):
        enabled = get_enabled_backup_schedules()
        if enabled:
            update_backup_schedule_last_run(enabled[0]["id"])
            sched = get_backup_schedule(enabled[0]["id"])
            assert sched["last_run"] is not None

    def test_delete_schedule(self):
        sched = create_backup_schedule("vm-delete-me", "0 0 * * *")
        delete_backup_schedule(sched["id"])
        assert get_backup_schedule(sched["id"]) is None


class TestAuditLog:
    def test_create_and_list(self):
        entry = create_audit_log(1, "admin", "login", "auth", "login", success=True, ip_address="10.0.0.1")
        assert entry["username"] == "admin"
        assert entry["action"] == "login"
        assert entry["success"] is True

        logs = list_audit_logs(limit=10)
        assert len(logs) >= 1

    def test_list_filters(self):
        create_audit_log(1, "admin", "create", "vm", "vm-foo", success=True)
        create_audit_log(2, "alice", "delete", "vm", "vm-bar", success=True)

        filtered = list_audit_logs(action="create")
        assert all(l["action"] == "create" for l in filtered)

        filtered2 = list_audit_logs(resource_type="vm")
        assert all(l["resource_type"] == "vm" for l in filtered2)

        filtered3 = list_audit_logs(user_id=2)
        assert all(l["user_id"] == 2 for l in filtered3)

    def test_list_pagination(self):
        logs_page = list_audit_logs(limit=2, offset=0)
        assert len(logs_page) <= 2

    def test_failed_action_default(self):
        entry = create_audit_log(None, "unknown", "login", "auth", "login", success=False)
        assert entry["success"] is False
        assert entry["user_id"] is None
