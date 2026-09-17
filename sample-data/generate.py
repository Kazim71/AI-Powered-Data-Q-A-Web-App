"""Generate three related sample files for demos and tests.

Deliberately joinable, and deliberately messy in realistic ways:
  * employees.csv   - headers with spaces/casing, a department_id foreign key
  * departments.csv - the dimension table
  * salaries.xlsx   - two sheets (2023, 2024) to exercise multi-sheet ingest

Run:  python sample-data/generate.py
"""

from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

random.seed(7)
OUT = Path(__file__).parent

DEPARTMENTS = [
    (1, "Engineering", "Bangalore", "Technology"),
    (2, "Sales", "Mumbai", "Revenue"),
    (3, "Marketing", "Mumbai", "Revenue"),
    (4, "People Ops", "Hyderabad", "Corporate"),
    (5, "Finance", "Hyderabad", "Corporate"),
]

FIRST = ["Aarav", "Diya", "Kabir", "Meera", "Rohan", "Sana", "Vikram", "Ananya",
         "Arjun", "Isha", "Nikhil", "Priya", "Rahul", "Tara", "Yash", "Zoya"]
LAST = ["Sharma", "Patel", "Reddy", "Nair", "Gupta", "Iyer", "Khan", "Bose"]
LEVELS = ["L1", "L2", "L3", "L4", "L5"]


def build_employees(n: int = 120) -> pd.DataFrame:
    rows = []
    for i in range(1, n + 1):
        dept = random.choice(DEPARTMENTS)
        hire_year = random.choice([2021, 2022, 2023, 2023, 2024, 2024])
        rows.append(
            {
                # Intentionally untidy headers - the normaliser should cope.
                "Employee ID": 1000 + i,
                "Full Name": f"{random.choice(FIRST)} {random.choice(LAST)}",
                "department_id": dept[0],
                "Level": random.choice(LEVELS),
                "Hire Date": f"{hire_year}-{random.randint(1, 12):02d}-"
                             f"{random.randint(1, 28):02d}",
                "Is Active": random.random() > 0.12,
                "Performance Rating": random.choice([2, 3, 3, 3, 4, 4, 5, None]),
            }
        )
    return pd.DataFrame(rows)


def build_departments() -> pd.DataFrame:
    return pd.DataFrame(
        DEPARTMENTS, columns=["id", "Department Name", "Location", "Function"]
    )


def build_salaries(employees: pd.DataFrame) -> dict[str, pd.DataFrame]:
    sheets = {}
    for year in (2023, 2024):
        rows = []
        for emp_id in employees["Employee ID"]:
            base = random.randint(6, 45) * 100000
            rows.append(
                {
                    "Employee ID": emp_id,
                    "Year": year,
                    "Base Salary (INR)": base + (150000 if year == 2024 else 0),
                    "Bonus (INR)": int(base * random.uniform(0.0, 0.2)),
                    "Currency": "INR",
                }
            )
        sheets[str(year)] = pd.DataFrame(rows)
    return sheets


def main() -> None:
    employees = build_employees()
    employees.to_csv(OUT / "employees.csv", index=False)
    build_departments().to_csv(OUT / "departments.csv", index=False)

    with pd.ExcelWriter(OUT / "salaries.xlsx") as writer:
        for sheet, frame in build_salaries(employees).items():
            frame.to_excel(writer, sheet_name=sheet, index=False)

    print(f"Wrote employees.csv, departments.csv, salaries.xlsx to {OUT}")


if __name__ == "__main__":
    main()
