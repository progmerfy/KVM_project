from typing import Optional


class AppError(Exception):
    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        http_status: int = 500,
        details: Optional[dict] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.http_status = http_status
        self.details = details or {}


class ServiceError(AppError):
    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        http_status: int = 400,
        details: Optional[dict] = None,
    ):
        super().__init__(message, code=code, http_status=http_status, details=details)


class InfrastructureError(AppError):
    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        http_status: int = 503,
        details: Optional[dict] = None,
    ):
        super().__init__(message, code=code, http_status=http_status, details=details)
