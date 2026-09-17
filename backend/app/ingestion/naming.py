"""Identifier normalisation for table and column names.

Real spreadsheets have headers like "Total Revenue (₹)", "  employee id ",
"2024 Q1", and two columns both called "Notes". SQL wants stable, unquoted,
unique snake_case identifiers.

We normalise on ingest and keep a bidirectional map so the UI can always show
the user their original header while the LLM and DuckDB see the clean one.
"""

from __future__ import annotations

import re
import unicodedata

# Reserved words we refuse to emit bare, so generated SQL never needs quoting.
_RESERVED = {
    "select", "from", "where", "group", "order", "by", "table", "column",
    "join", "on", "as", "and", "or", "not", "null", "case", "when", "then",
    "else", "end", "limit", "offset", "union", "all", "distinct", "having",
    "into", "values", "index", "default", "primary", "key", "references",
}


def slugify(raw: str, *, fallback: str = "col") -> str:
    """Turn an arbitrary header into a safe snake_case SQL identifier."""
    # Strip accents/unicode down to ASCII where possible: "Café" -> "Cafe".
    text = unicodedata.normalize("NFKD", str(raw))
    text = text.encode("ascii", "ignore").decode("ascii")

    text = text.strip().lower()
    # Split camelCase before collapsing separators: "totalRevenue" -> "total revenue"
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    # Any run of non-alphanumerics becomes a single underscore.
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")

    if not text:
        text = fallback
    # SQL identifiers cannot start with a digit: "2024_q1" -> "c_2024_q1".
    if text[0].isdigit():
        text = f"c_{text}"
    if text in _RESERVED:
        text = f"{text}_col"
    return text


def deduplicate(names: list[str]) -> list[str]:
    """Append _2, _3 ... to repeated names, preserving input order."""
    seen: dict[str, int] = {}
    out: list[str] = []
    for name in names:
        if name not in seen:
            seen[name] = 1
            out.append(name)
        else:
            seen[name] += 1
            out.append(f"{name}_{seen[name]}")
    return out


def normalise_columns(raw_headers: list[str]) -> tuple[list[str], dict[str, str]]:
    """Normalise a header row.

    Returns the clean column names and a {clean: original} map for display.
    """
    slugged = [
        slugify(h, fallback=f"col_{i + 1}") for i, h in enumerate(raw_headers)
    ]
    clean = deduplicate(slugged)
    return clean, dict(zip(clean, [str(h) for h in raw_headers]))


def table_name_for(filename: str, sheet: str | None = None) -> str:
    """Derive a table name from a filename, plus a sheet name for Excel.

    "Q1 Sales.xlsx" + sheet "By Region" -> "q1_sales_by_region"
    """
    stem = filename.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    base = slugify(stem, fallback="table")
    if sheet:
        suffix = slugify(sheet, fallback="sheet")
        # A sheet named "2023" slugs to "c_2023" because a bare identifier may
        # not start with a digit — but as a *suffix* it is already safe, so
        # strip the guard back off: salaries_2023, not salaries_c_2023.
        if suffix.startswith("c_") and suffix[2:3].isdigit():
            suffix = suffix[2:]
        # Don't produce "sales_sales" when the sheet repeats the filename.
        if suffix != base:
            base = f"{base}_{suffix}"
    return base
