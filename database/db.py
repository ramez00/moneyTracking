import os
import sqlite3
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "spendly.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    conn.commit()
    conn.close()


def seed_db():
    conn = get_db()
    if conn.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None:
        conn.close()
        return

    password_hash = generate_password_hash("demo123")
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", password_hash),
    )
    user_id = cursor.lastrowid

    today = date.today()
    first_of_month = today.replace(day=1)
    days_elapsed = (today - first_of_month).days

    def day(fraction):
        return (first_of_month + timedelta(days=int(days_elapsed * fraction))).isoformat()

    expenses = [
        (user_id, 45.50, "Food",          day(0 / 7), "Grocery shopping"),
        (user_id, 12.75, "Transport",     day(1 / 7), "Bus fare"),
        (user_id, 89.99, "Bills",         day(2 / 7), "Electricity bill"),
        (user_id, 35.00, "Health",        day(3 / 7), "Pharmacy purchase"),
        (user_id, 22.00, "Entertainment", day(4 / 7), "Movie tickets"),
        (user_id, 60.25, "Shopping",      day(5 / 7), "New shoes"),
        (user_id, 15.00, "Other",         day(6 / 7), "Miscellaneous purchase"),
        (user_id, 8.25,  "Food",          day(7 / 7), "Coffee and breakfast"),
    ]
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        expenses,
    )
    conn.commit()
    conn.close()


def get_user_by_email(email):
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    return user


def create_user(name, email, password_hash):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, password_hash),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


def create_expense(user_id, amount, category, expense_date, description):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, expense_date, description),
    )
    conn.commit()
    expense_id = cursor.lastrowid
    conn.close()
    return expense_id


def get_user_by_id(user_id):
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return user


def get_expenses_by_user(user_id, start_date=None, end_date=None):
    conn = get_db()
    query = "SELECT id, amount, category, date, description FROM expenses WHERE user_id = ?"
    params = [user_id]
    if start_date and end_date:
        query += " AND date BETWEEN ? AND ?"
        params += [start_date, end_date]
    query += " ORDER BY date DESC, id DESC"
    expenses = conn.execute(query, params).fetchall()
    conn.close()
    return expenses


def get_expense_summary(user_id, start_date=None, end_date=None):
    conn = get_db()
    range_clause = " AND date BETWEEN ? AND ?" if start_date and end_date else ""
    range_params = [start_date, end_date] if start_date and end_date else []

    totals = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count "
        "FROM expenses WHERE user_id = ?" + range_clause,
        [user_id] + range_params,
    ).fetchone()
    by_category = conn.execute(
        "SELECT category, SUM(amount) AS total FROM expenses WHERE user_id = ?"
        + range_clause + " GROUP BY category ORDER BY total DESC",
        [user_id] + range_params,
    ).fetchall()
    conn.close()
    return {
        "total": totals["total"],
        "count": totals["count"],
        "by_category": by_category,
    }
