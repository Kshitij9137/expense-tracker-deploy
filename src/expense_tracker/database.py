"""Database layer: owns the SQLite connection and schema."""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS expenses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    category     TEXT    NOT NULL,
    description  TEXT    NOT NULL DEFAULT '',
    spent_on     TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS budgets (
    category     TEXT PRIMARY KEY,
    limit_cents  INTEGER NOT NULL CHECK (limit_cents > 0)
);
CREATE INDEX IF NOT EXISTS idx_expenses_date     ON expenses (spent_on);
CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses (category);
"""


def connect(path: str = "expenses.db") -> sqlite3.Connection:
    """Open the database. File databases use WAL mode and a busy timeout so several
    web workers can read and write at the same time without 'database is locked' errors."""
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    if path != ":memory:":
        conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn
