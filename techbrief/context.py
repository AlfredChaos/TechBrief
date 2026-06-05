from __future__ import annotations

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
run_id_var: ContextVar[str | None] = ContextVar("run_id", default=None)
service_var: ContextVar[str | None] = ContextVar("service", default=None)


def set_request_id(value: str | None) -> None:
    request_id_var.set(value)


def get_request_id() -> str | None:
    return request_id_var.get()


def clear_request_id() -> None:
    request_id_var.set(None)


def set_run_id(value: str | None) -> None:
    run_id_var.set(value)


def get_run_id() -> str | None:
    return run_id_var.get()


def set_service(value: str | None) -> None:
    service_var.set(value)


def get_service() -> str | None:
    return service_var.get()
