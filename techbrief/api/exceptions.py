from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AppError(Exception):
    code: str
    message: str
    status: int
    error_type: str
    details: dict | None = field(default=None)


class ValidationError(AppError):
    def __init__(self, message: str = "validation failed", details: dict | None = None):
        super().__init__(
            code="SYSTEM_VALIDATION_ERROR",
            message=message,
            status=400,
            error_type="ValidationError",
            details=details,
        )


class ConflictError(AppError):
    def __init__(self, message: str = "resource conflict", details: dict | None = None):
        super().__init__(
            code="SYSTEM_CONFLICT",
            message=message,
            status=409,
            error_type="ConflictError",
            details=details,
        )


class InternalServerError(AppError):
    def __init__(self, message: str = "internal server error", details: dict | None = None):
        super().__init__(
            code="SYSTEM_INTERNAL_ERROR",
            message=message,
            status=500,
            error_type="SystemError",
            details=details,
        )
