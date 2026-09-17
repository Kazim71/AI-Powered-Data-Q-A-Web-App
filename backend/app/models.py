"""Shared response/domain models.

These are the contract between backend and frontend. The profiling models are
also what gets rendered into the LLM prompt (see docs/04-data-pipeline.md), so
changing them changes answer quality — treat them as a real interface.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

SemanticType = Literal[
    "numeric", "temporal", "categorical", "identifier", "boolean", "text"
]


class ColumnProfile(BaseModel):
    """What we know about a single column after ingestion."""

    name: str = Field(description="Normalised snake_case name used in SQL")
    original_name: str = Field(description="Header exactly as it appeared in the file")
    dtype: str = Field(description="Physical DuckDB type, e.g. BIGINT, VARCHAR")
    semantic_type: SemanticType = Field(
        description="How the column should be used in analysis"
    )
    null_count: int
    null_fraction: float
    distinct_count: int
    sample_values: list[Any] = Field(
        default_factory=list, description="A few real values, for LLM grounding"
    )
    # Populated for numeric/temporal columns only.
    min_value: Any | None = None
    max_value: Any | None = None
    # Populated only for low-cardinality categoricals: the full value list, so
    # the model can filter on 'EMEA' without guessing the spelling.
    categories: list[Any] | None = None


class TableProfile(BaseModel):
    """One uploaded file (or one Excel sheet) as a queryable table."""

    name: str = Field(description="DuckDB table name")
    source_file: str
    sheet_name: str | None = None
    row_count: int
    columns: list[ColumnProfile]


class JoinHint(BaseModel):
    """An inferred relationship between two tables.

    Produced by heuristics (name similarity + sampled value overlap), not by the
    LLM. Surfaced in the prompt so cross-file questions join correctly.
    """

    left_table: str
    left_column: str
    right_table: str
    right_column: str
    overlap: float = Field(
        description="Fraction of sampled left values found in the right column"
    )
    confidence: Literal["high", "medium", "low"]


class SessionSchema(BaseModel):
    """Everything the app knows about a session's data."""

    session_id: str
    created_at: datetime
    tables: list[TableProfile]
    join_hints: list[JoinHint] = Field(default_factory=list)


class UploadedFileResult(BaseModel):
    """Per-file outcome of an upload; one file may yield several tables."""

    filename: str
    status: Literal["ok", "failed"]
    tables: list[str] = Field(default_factory=list)
    error: str | None = None


class UploadResponse(BaseModel):
    session_id: str
    files: list[UploadedFileResult]
    schema_: SessionSchema = Field(serialization_alias="schema")


class SessionCreatedResponse(BaseModel):
    session_id: str
    created_at: datetime
