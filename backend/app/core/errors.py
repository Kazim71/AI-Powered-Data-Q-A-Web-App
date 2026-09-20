"""Domain exceptions, mapped to HTTP responses in main.py.

Keeping these separate from FastAPI means the ingestion and profiling layers
stay framework-agnostic and unit-testable without spinning up an app.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for expected, user-facing failures."""

    status_code = 400

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class SessionNotFound(AppError):
    status_code = 404


class TableNotFound(AppError):
    status_code = 404


class UnsupportedFileType(AppError):
    status_code = 415


class FileTooLarge(AppError):
    status_code = 413


class TooManyFiles(AppError):
    status_code = 400


class IngestionError(AppError):
    """A file was readable but could not be turned into a usable table."""

    status_code = 422


class EmptySession(AppError):
    """A question was asked before any file was uploaded."""

    status_code = 400


class LLMError(AppError):
    """The LLM provider could not be reached or returned something unusable."""

    status_code = 502


class SQLGenerationError(AppError):
    """The model's SQL failed validation or execution, even after one repair."""

    status_code = 422
