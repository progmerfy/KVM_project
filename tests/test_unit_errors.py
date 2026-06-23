"""Unit tests for app.errors — AppError, ServiceError, InfrastructureError, RUNBOOK_URLS."""

from app.errors import AppError, ServiceError, InfrastructureError, RUNBOOK_URLS


class TestRunbookUrls:
    def test_all_codes_have_runbooks(self):
        expected_codes = [
            "VM_NOT_FOUND", "VM_CREATE_FAILED", "VM_START_FAILED",
            "VM_STOP_FAILED", "VM_DELETE_FAILED", "FORBIDDEN",
            "INVALID_CREDENTIALS", "IMAGE_NOT_FOUND", "IMAGE_ALREADY_EXISTS",
            "UPLOAD_FAILED", "DOWNLOAD_FAILED", "STORAGE_FULL",
            "NETWORK_NOT_FOUND", "SCHEDULE_EXISTS", "INVALID_CRON",
            "BACKUP_FAILED", "SNAPSHOT_FAILED", "LIBVIRT_CONNECTION",
            "INTERNAL_ERROR",
        ]
        for code in expected_codes:
            assert code in RUNBOOK_URLS, f"Missing runbook URL for {code}"
            assert RUNBOOK_URLS[code].startswith("https://docs.kvm-mgr.local/runbooks/")

    def test_runbook_urls_format(self):
        for code, url in RUNBOOK_URLS.items():
            assert url.startswith("https://docs.kvm-mgr.local/runbooks/")
            assert len(url) > len("https://docs.kvm-mgr.local/runbooks/")
            # Each URL has path components (e.g. vm/not-found)
            path = url.replace("https://docs.kvm-mgr.local/runbooks/", "")
            assert "/" in path


class TestAppError:
    def test_default_values(self):
        err = AppError("test error")
        assert err.message == "test error"
        assert err.code == "AppError"
        assert err.http_status == 500
        assert err.details == {}
        assert err.runbook_url is None

    def test_with_code_and_runbook(self):
        err = AppError("VM not found", code="VM_NOT_FOUND", http_status=404)
        assert err.code == "VM_NOT_FOUND"
        assert err.http_status == 404
        assert err.runbook_url == RUNBOOK_URLS["VM_NOT_FOUND"]

    def test_with_details(self):
        err = AppError("error", details={"vm_name": "test-vm"})
        assert err.details == {"vm_name": "test-vm"}

    def test_explicit_runbook_overrides(self):
        err = AppError("error", code="VM_NOT_FOUND", runbook_url="https://custom.url")
        assert err.runbook_url == "https://custom.url"

    def test_exception_raised_and_caught(self):
        try:
            raise AppError("something broke", code="INTERNAL_ERROR")
        except AppError as e:
            assert str(e) == "something broke"
            assert e.code == "INTERNAL_ERROR"


class TestServiceError:
    def test_default_http_status(self):
        err = ServiceError("service error")
        assert err.http_status == 400
        assert err.code == "ServiceError"

    def test_with_code(self):
        err = ServiceError("not found", code="VM_NOT_FOUND", http_status=404)
        assert err.http_status == 404
        assert err.code == "VM_NOT_FOUND"


class TestInfrastructureError:
    def test_default_http_status(self):
        err = InfrastructureError("infra error")
        assert err.http_status == 503

    def test_is_app_error(self):
        err = InfrastructureError("test")
        assert isinstance(err, AppError)
