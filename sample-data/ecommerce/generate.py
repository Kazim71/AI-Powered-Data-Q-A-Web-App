"""A second demo dataset, deliberately in a different domain from the HR one
(sample-data/generate.py) — retail/e-commerce, not HR — so a reviewer sees
the app isn't hard-coded around one shape of data.

Three joinable, deliberately messy files:
  * customers.csv  - headers with spaces, a signup date, a segment column
  * products.csv   - a small catalogue with a category
  * orders.csv     - the fact table, foreign keys into both of the above,
                      including some cancelled/returned orders (so "total
                      revenue" has a genuine, non-trivial filter to get right)

Run:  python sample-data/ecommerce/generate.py
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

random.seed(11)
OUT = Path(__file__).parent

CATEGORIES = ["Electronics", "Home & Kitchen", "Apparel", "Books", "Sports"]
CITIES = ["Mumbai", "Delhi", "Bangalore", "Pune", "Hyderabad", "Chennai"]
SEGMENTS = ["Consumer", "Business"]
STATUSES = ["Delivered", "Delivered", "Delivered", "Delivered", "Returned", "Cancelled"]

PRODUCTS = [
    (1, "Wireless Mouse", "Electronics", 799),
    (2, "Mechanical Keyboard", "Electronics", 3499),
    (3, "USB-C Hub", "Electronics", 1499),
    (4, "Non-stick Pan Set", "Home & Kitchen", 2199),
    (5, "Electric Kettle", "Home & Kitchen", 1299),
    (6, "Cotton T-Shirt", "Apparel", 599),
    (7, "Running Shoes", "Sports", 3999),
    (8, "Yoga Mat", "Sports", 899),
    (9, "The Pragmatic Programmer", "Books", 899),
    (10, "Atomic Habits", "Books", 499),
    (11, "Desk Lamp", "Home & Kitchen", 1099),
    (12, "Bluetooth Speaker", "Electronics", 2299),
]

FIRST = ["Priya", "Rohan", "Ananya", "Vikram", "Ishaan", "Meera", "Arjun", "Kavya",
          "Aditya", "Sneha", "Karan", "Divya"]
LAST = ["Mehta", "Rao", "Singh", "Kapoor", "Joshi", "Verma", "Nair", "Chatterjee"]


def build_customers(n: int = 40) -> pd.DataFrame:
    rows = []
    for i in range(1, n + 1):
        signup = date(2023, 1, 1) + timedelta(days=random.randint(0, 700))
        rows.append(
            {
                "Customer ID": 2000 + i,
                "Customer Name": f"{random.choice(FIRST)} {random.choice(LAST)}",
                "City": random.choice(CITIES),
                "Segment": random.choice(SEGMENTS),
                "Signup Date": signup.isoformat(),
            }
        )
    return pd.DataFrame(rows)


def build_products() -> pd.DataFrame:
    return pd.DataFrame(
        PRODUCTS, columns=["product_id", "Product Name", "Category", "Unit Price (INR)"]
    )


def build_orders(customers: pd.DataFrame, n: int = 300) -> pd.DataFrame:
    rows = []
    customer_ids = customers["Customer ID"].tolist()
    for i in range(1, n + 1):
        order_date = date(2024, 1, 1) + timedelta(days=random.randint(0, 364))
        product = random.choice(PRODUCTS)
        rows.append(
            {
                "order_id": 5000 + i,
                "Customer ID": random.choice(customer_ids),
                "product_id": product[0],
                "Quantity": random.randint(1, 4),
                "Order Date": order_date.isoformat(),
                "Status": random.choice(STATUSES),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    customers = build_customers()
    customers.to_csv(OUT / "customers.csv", index=False)
    build_products().to_csv(OUT / "products.csv", index=False)
    build_orders(customers).to_csv(OUT / "orders.csv", index=False)
    print(f"Wrote customers.csv, products.csv, orders.csv to {OUT}")


if __name__ == "__main__":
    main()
