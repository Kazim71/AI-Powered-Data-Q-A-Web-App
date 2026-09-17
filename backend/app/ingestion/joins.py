"""Infer relationships between uploaded tables.

Cross-file analysis is acceptance criterion #2, and the usual failure mode is
not that the model can't write a JOIN — it's that it doesn't know *which*
columns relate. Rather than hoping the LLM guesses, we measure it:

1. Candidate pairs are columns whose names match, or where one is a plausible
   foreign key for the other's table (``employees.department_id`` ->
   ``departments.id``).
2. Each candidate is scored by real **value overlap**, computed in DuckDB.

Only measured overlap produces a hint, so a coincidental name match on
unrelated values is discarded.
"""

from __future__ import annotations

from itertools import combinations

from app.core.session import Session
from app.models import JoinHint, TableProfile

# Column roles that can sensibly act as a join key.
_JOINABLE = {"identifier", "categorical", "text"}

# A column with almost no distinct values is not a key. Without this, every pair
# of tables carrying a constant `currency = 'INR'` column reports a perfect
# "relationship" and buries the real joins in noise.
_MIN_KEY_CARDINALITY = 2
_MIN_CATEGORICAL_KEY_CARDINALITY = 5

_HIGH_CONFIDENCE = 0.80
_MEDIUM_CONFIDENCE = 0.40


def _singularise(name: str) -> str:
    for suffix in ("ies", "s"):
        if name.endswith(suffix) and len(name) > len(suffix) + 1:
            return name[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return name


def _usable_as_key(column) -> bool:
    """Reject columns too degenerate to be a meaningful join key."""
    if column.semantic_type not in _JOINABLE:
        return False
    if column.distinct_count < _MIN_KEY_CARDINALITY:
        return False
    # Identifiers earn the benefit of the doubt; a plain low-card category
    # (status, currency, region) matching across files is usually coincidence.
    if (
        column.semantic_type != "identifier"
        and column.distinct_count < _MIN_CATEGORICAL_KEY_CARDINALITY
    ):
        return False
    return True


def _is_candidate_pair(
    left_table: str, left_col: str, right_table: str, right_col: str
) -> bool:
    if left_col == right_col:
        return True

    # employees.department_id  <->  departments.id / departments.department_id
    right_entity = _singularise(right_table)
    left_entity = _singularise(left_table)
    if left_col in {f"{right_entity}_id", f"{right_entity}_code", f"{right_entity}_key"}:
        return right_col in {"id", "code", "key", left_col}
    if right_col in {f"{left_entity}_id", f"{left_entity}_code", f"{left_entity}_key"}:
        return left_col in {"id", "code", "key", right_col}
    return False


def _overlap(
    session: Session, left_table: str, left_col: str, right_table: str, right_col: str
) -> float:
    """Fraction of distinct left values that appear in the right column.

    Sampled to 1000 distinct values so this stays cheap on wide datasets.
    """
    result = session.connection.execute(
        f"""
        WITH left_vals AS (
            SELECT DISTINCT CAST("{left_col}" AS VARCHAR) AS v
            FROM "{left_table}" WHERE "{left_col}" IS NOT NULL LIMIT 1000
        ),
        right_vals AS (
            SELECT DISTINCT CAST("{right_col}" AS VARCHAR) AS v
            FROM "{right_table}" WHERE "{right_col}" IS NOT NULL
        )
        SELECT count(*), count(*) FILTER (WHERE r.v IS NOT NULL)
        FROM left_vals l LEFT JOIN right_vals r USING (v)
        """
    ).fetchone()

    total, matched = result if result else (0, 0)
    return round(matched / total, 3) if total else 0.0


def infer_joins(session: Session, tables: list[TableProfile]) -> list[JoinHint]:
    hints: list[JoinHint] = []

    for left, right in combinations(tables, 2):
        for left_col in left.columns:
            if not _usable_as_key(left_col):
                continue
            for right_col in right.columns:
                if not _usable_as_key(right_col):
                    continue
                if not _is_candidate_pair(
                    left.name, left_col.name, right.name, right_col.name
                ):
                    continue

                # Compare in both directions and keep the stronger reading: a
                # fact->dimension link is near-total one way, partial the other.
                forward = _overlap(
                    session, left.name, left_col.name, right.name, right_col.name
                )
                backward = _overlap(
                    session, right.name, right_col.name, left.name, left_col.name
                )
                score = max(forward, backward)
                if score < _MEDIUM_CONFIDENCE:
                    continue

                hints.append(
                    JoinHint(
                        left_table=left.name,
                        left_column=left_col.name,
                        right_table=right.name,
                        right_column=right_col.name,
                        overlap=score,
                        confidence="high" if score >= _HIGH_CONFIDENCE else "medium",
                    )
                )

    hints.sort(key=lambda h: h.overlap, reverse=True)
    return hints
