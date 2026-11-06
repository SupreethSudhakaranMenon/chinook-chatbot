"""Offline checks that do not call an LLM."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chinook_bot.db import connect_readonly, initialize_database
from chinook_bot.fts import search_names
from chinook_bot.sql_guard import SqlGuardError, validate_sql


def test_load_and_fts() -> None:
    db_path = initialize_database()
    conn = connect_readonly(db_path)
    try:
        artists = conn.execute("SELECT COUNT(*) FROM Artist").fetchone()[0]
        tracks = conn.execute("SELECT COUNT(*) FROM Track").fetchone()[0]
        assert artists > 0, "Artist table empty"
        assert tracks > 0, "Track table empty"
        hits = search_names(conn, "AC DC")
        assert hits, "Expected FTS hits for AC/DC"
        types = {h["entity_type"] for h in hits}
        assert "Artist" in types or "Album" in types or "Track" in types
    finally:
        conn.close()


def test_sql_guard() -> None:
    ok = validate_sql("SELECT Name FROM Artist ORDER BY Name")
    assert "LIMIT" in ok.upper()
    ok2 = validate_sql("SELECT COUNT(*) AS n FROM Invoice")
    assert ok2
    try:
        validate_sql("DELETE FROM Artist")
        raise AssertionError("DELETE should be rejected")
    except SqlGuardError:
        pass
    try:
        validate_sql("SELECT * FROM sqlite_master")
        raise AssertionError("sqlite_master should be rejected")
    except SqlGuardError:
        pass
    try:
        validate_sql("SELECT 1; SELECT 2")
        raise AssertionError("multiple statements should be rejected")
    except SqlGuardError:
        pass


if __name__ == "__main__":
    test_load_and_fts()
    test_sql_guard()
    print("offline tests passed")
