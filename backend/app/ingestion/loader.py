"""Turn uploaded CSV/Excel files into DuckDB tables.

Design notes
------------
* CSV goes through DuckDB's native ``read_csv_auto``: it streams (so a large
  file never has to fit in memory), sniffs delimiters and encodings, and infers
  types better than a naive pandas read.
* Excel goes through pandas/openpyxl, because DuckDB has no first-class reader.
  **Every sheet becomes its own table** — a workbook is a collection of
  datasets, and flattening that away loses information the user cares about.
* Column headers are normalised after load (see naming.py) and the original
  headers are kept in the session for display.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.core.errors import IngestionError, UnsupportedFileType
from app.core.session import Session
from app.ingestion.naming import normalise_columns, table_name_for


@dataclass(frozen=True)
class LoadedTable:
    """One table created from a file, with the provenance the catalogue needs."""

    table: str
    source_file: str
    sheet_name: str | None = None


CSV_SUFFIXES = {".csv", ".tsv", ".txt"}
EXCEL_SUFFIXES = {".xlsx", ".xls", ".xlsm"}
SUPPORTED_SUFFIXES = CSV_SUFFIXES | EXCEL_SUFFIXES


def is_supported(filename: str) -> bool:
    return Path(filename).suffix.lower() in SUPPORTED_SUFFIXES


def _unique_table_name(session: Session, desired: str) -> str:
    """Avoid clobbering an existing table when two files share a name."""
    existing = set(session.table_names())
    if desired not in existing:
        return desired
    n = 2
    while f"{desired}_{n}" in existing:
        n += 1
    return f"{desired}_{n}"


def _rename_columns(session: Session, table: str) -> dict[str, str]:
    """Normalise a loaded table's columns in place; return {clean: original}.

    Done in two passes via placeholder names so a rename can never collide with
    a column that has not been renamed yet (e.g. swapping "b" and "a").
    """
    raw_headers = [
        row[0]
        for row in session.connection.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'main' AND table_name = ? "
            "ORDER BY ordinal_position",
            [table],
        ).fetchall()
    ]
    clean, labels = normalise_columns(raw_headers)

    if clean == raw_headers:
        return labels

    for index, original in enumerate(raw_headers):
        session.connection.execute(
            f'ALTER TABLE "{table}" RENAME COLUMN "{original}" TO "__tmp_{index}"'
        )
    for index, final in enumerate(clean):
        session.connection.execute(
            f'ALTER TABLE "{table}" RENAME COLUMN "__tmp_{index}" TO "{final}"'
        )
    return labels


def _load_csv(session: Session, path: Path, table: str) -> None:
    session.connection.execute(
        f'CREATE TABLE "{table}" AS SELECT * FROM read_csv_auto(?, header=true, '
        f"sample_size=-1, ignore_errors=true)",
        [str(path)],
    )


def _load_dataframe(session: Session, frame: pd.DataFrame, table: str) -> None:
    # Registering the frame lets DuckDB read it directly; the CTAS then
    # materialises a real table so the frame can be garbage collected.
    session.connection.register("__incoming", frame)
    try:
        session.connection.execute(
            f'CREATE TABLE "{table}" AS SELECT * FROM __incoming'
        )
    finally:
        session.connection.unregister("__incoming")


def load_file(
    session: Session, path: Path, original_filename: str
) -> list[LoadedTable]:
    """Load one file into the session. Returns the tables created."""
    suffix = path.suffix.lower()

    if suffix in CSV_SUFFIXES:
        table = _unique_table_name(session, table_name_for(original_filename))
        try:
            _load_csv(session, path, table)
        except Exception as exc:  # duckdb raises a family of parser errors
            raise IngestionError(
                f"Could not read '{original_filename}' as a CSV.", detail=str(exc)
            ) from exc
        session.column_labels[table] = _rename_columns(session, table)
        return [LoadedTable(table=table, source_file=original_filename)]

    if suffix in EXCEL_SUFFIXES:
        try:
            sheets = pd.read_excel(path, sheet_name=None)
        except Exception as exc:
            raise IngestionError(
                f"Could not read '{original_filename}' as a spreadsheet.",
                detail=str(exc),
            ) from exc

        created: list[LoadedTable] = []
        for sheet_name, frame in sheets.items():
            if frame.empty or frame.columns.empty:
                continue  # skip blank sheets rather than creating useless tables
            table = _unique_table_name(
                session, table_name_for(original_filename, sheet_name)
            )
            # pandas gives unnamed columns as "Unnamed: 3"; let naming.py handle it.
            frame.columns = [str(c) for c in frame.columns]
            _load_dataframe(session, frame, table)
            session.column_labels[table] = _rename_columns(session, table)
            created.append(
                LoadedTable(
                    table=table,
                    source_file=original_filename,
                    sheet_name=str(sheet_name),
                )
            )

        if not created:
            raise IngestionError(
                f"'{original_filename}' contained no readable sheets."
            )
        return created

    raise UnsupportedFileType(
        f"'{original_filename}' is not a supported file type. "
        "Upload a .csv, .tsv, .xlsx or .xls file."
    )
