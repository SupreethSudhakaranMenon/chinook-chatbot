"""Load Chinook_Sqlite.sql into a local SQLite file and open connections."""

from __future__ import annotations

import sqlite3
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
CHATBOT_DIR = PACKAGE_DIR.parent
REPO_ROOT = CHATBOT_DIR.parent
DEFAULT_SQL = REPO_ROOT / "ChinookDatabase" / "DataSources" / "Chinook_Sqlite.sql"
DATA_DIR = CHATBOT_DIR / "data"
DB_PATH = DATA_DIR / "chinook.db"

EXPECTED_TABLES = {
    "Album",
    "Artist",
    "Customer",
    "Employee",
    "Genre",
    "Invoice",
    "InvoiceLine",
    "MediaType",
    "Playlist",
    "PlaylistTrack",
    "Track",
}


def _existing_tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row[0] for row in rows}


def _chinook_loaded(conn: sqlite3.Connection) -> bool:
    tables = _existing_tables(conn)
    if not EXPECTED_TABLES.issubset(tables):
        return False
    count = conn.execute("SELECT COUNT(*) FROM Artist").fetchone()[0]
    return count > 0


def initialize_database(sql_path: Path | None = None, db_path: Path | None = None) -> Path:
    """Create chinook.db from the official SQLite script if needed."""
    sql_path = Path(sql_path) if sql_path else DEFAULT_SQL
    db_path = Path(db_path) if db_path else DB_PATH
    if not sql_path.is_file():
        raise FileNotFoundError(f"Chinook SQL file not found: {sql_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        if not _chinook_loaded(conn):
            script = sql_path.read_text(encoding="utf-8")
            conn.executescript(script)
            conn.commit()
            if not _chinook_loaded(conn):
                raise RuntimeError("Failed to load Chinook tables from SQL script")
        from chinook_bot.fts import ensure_fts_index

        ensure_fts_index(conn)
        conn.commit()
    finally:
        conn.close()
    return db_path


def connect_readonly(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DB_PATH
    if not path.is_file():
        raise FileNotFoundError(f"Database not initialized: {path}")
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def connect_readwrite(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn
