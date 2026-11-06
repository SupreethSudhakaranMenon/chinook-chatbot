"""FTS5 name index for fuzzy catalog and people lookups."""

from __future__ import annotations

import re
import sqlite3

FTS_TABLE = "chinook_fts"

_SOURCES = [
    ("SELECT 'Artist' AS entity_type, ArtistId, Name, '' FROM Artist WHERE Name IS NOT NULL",),
    ("SELECT 'Album', AlbumId, Title, '' FROM Album WHERE Title IS NOT NULL",),
    ("SELECT 'Track', TrackId, Name, COALESCE(Composer, '') FROM Track WHERE Name IS NOT NULL",),
    ("SELECT 'Playlist', PlaylistId, Name, '' FROM Playlist WHERE Name IS NOT NULL",),
    ("SELECT 'Genre', GenreId, Name, '' FROM Genre WHERE Name IS NOT NULL",),
    ("SELECT 'MediaType', MediaTypeId, Name, '' FROM MediaType WHERE Name IS NOT NULL",),
    (
        "SELECT 'Customer', CustomerId, FirstName || ' ' || LastName, COALESCE(Company, '') "
        "FROM Customer",
    ),
    (
        "SELECT 'Employee', EmployeeId, FirstName || ' ' || LastName, COALESCE(Title, '') "
        "FROM Employee",
    ),
]


def _fts_ready(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (FTS_TABLE,),
    ).fetchone()
    if not row:
        return False
    count = conn.execute(f"SELECT COUNT(*) FROM {FTS_TABLE}").fetchone()[0]
    return count > 0


def ensure_fts_index(conn: sqlite3.Connection) -> None:
    if _fts_ready(conn):
        return
    conn.execute(f"DROP TABLE IF EXISTS {FTS_TABLE}")
    conn.execute(
        f"""
        CREATE VIRTUAL TABLE {FTS_TABLE} USING fts5(
            entity_type,
            entity_id UNINDEXED,
            name,
            extra,
            tokenize = 'porter unicode61'
        )
        """
    )
    for (select,) in _SOURCES:
        conn.execute(
            f"INSERT INTO {FTS_TABLE} (entity_type, entity_id, name, extra) {select}"
        )


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _match_query(text: str) -> str | None:
    tokens = _TOKEN_RE.findall(text)
    if not tokens:
        return None
    parts = [f'"{tok}"' if len(tok) > 2 else tok for tok in tokens[:8]]
    return " OR ".join(parts)


def search_names(conn: sqlite3.Connection, query: str, limit: int = 8) -> list[dict]:
    match = _match_query(query)
    if not match:
        return []
    try:
        rows = conn.execute(
            f"""
            SELECT entity_type, entity_id, name, extra, rank
            FROM {FTS_TABLE}
            WHERE {FTS_TABLE} MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (match, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [
        {
            "entity_type": row["entity_type"],
            "entity_id": row["entity_id"],
            "name": row["name"],
            "extra": row["extra"],
        }
        for row in rows
    ]


def format_hits(hits: list[dict]) -> str:
    if not hits:
        return "No catalog name matches."
    lines = ["Resolved catalog entities (use these IDs in SQL; do not invent others):"]
    for hit in hits:
        extra = f" ({hit['extra']})" if hit.get("extra") else ""
        lines.append(
            f"- {hit['entity_type']} id={hit['entity_id']}: {hit['name']}{extra}"
        )
    return "\n".join(lines)
