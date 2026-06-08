from typing import Optional

_RUNBOOK_BASE = "https://docs.kvm-mgr.local/runbooks"


def _runbook_url(*parts: str) -> str:
    return f"{_RUNBOOK_BASE}/{'/'.join(parts)}"


RUNBOOK_URLS: dict[str, str] = {
    "VM_NOT_FOUND": _runbook_url("vm", "not-found"),
    "VM_CREATE_FAILED": _runbook_url("vm", "create-failed"),
    "VM_START_FAILED": _runbook_url("vm", "start-failed"),
    "VM_STOP_FAILED": _runbook_url("vm", "stop-failed"),
    "VM_DELETE_FAILED": _runbook_url("vm", "delete-failed"),
    "FORBIDDEN": _runbook_url("auth", "access-denied"),
    "INVALID_CREDENTIALS": _runbook_url("auth", "invalid-credentials"),
    "IMAGE_NOT_FOUND": _runbook_url("images", "not-found"),
    "IMAGE_ALREADY_EXISTS": _runbook_url("images", "already-exists"),
    "UPLOAD_FAILED": _runbook_url("images", "upload-failed"),
    "DOWNLOAD_FAILED": _runbook_url("images", "download-failed"),
    "STORAGE_FULL": _runbook_url("storage", "full"),
    "NETWORK_NOT_FOUND": _runbook_url("network", "not-found"),
    "SCHEDULE_EXISTS": _runbook_url("backup", "schedule-exists"),
    "INVALID_CRON": _runbook_url("backup", "invalid-cron"),
    "BACKUP_FAILED": _runbook_url("backup", "backup-failed"),
    "SNAPSHOT_FAILED": _runbook_url("vm", "snapshot-failed"),
    "LIBVIRT_CONNECTION": _runbook_url("infrastructure", "libvirt-connection"),
    "INTERNAL_ERROR": _runbook_url("infrastructure", "internal-error"),
}


class AppError(Exception):
    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        http_status: int = 500,
        details: Optional[dict] = None,
        runbook_url: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.http_status = http_status
        self.details = details or {}
        self.runbook_url = runbook_url or RUNBOOK_URLS.get(self.code)


class ServiceError(AppError):
    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        http_status: int = 400,
        details: Optional[dict] = None,
        runbook_url: Optional[str] = None,
    ):
        super().__init__(message, code=code, http_status=http_status, details=details, runbook_url=runbook_url)


class InfrastructureError(AppError):
    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        http_status: int = 503,
        details: Optional[dict] = None,
        runbook_url: Optional[str] = None,
    ):
        super().__init__(message, code=code, http_status=http_status, details=details, runbook_url=runbook_url)
