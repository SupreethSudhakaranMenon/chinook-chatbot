"""Hybrid router: FTS lookup + guarded text-to-SQL + grounded answers."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from chinook_bot.db import connect_readonly, initialize_database
from chinook_bot.fts import format_hits, search_names
from chinook_bot.llm import complete_json, complete_text
from chinook_bot.schema import schema_card
from chinook_bot.sql_guard import SqlGuardError, validate_sql

ROW_CAP = 40

ROUTER_SYSTEM = """You are a router for a Chinook digital media store chatbot.
The bot may ONLY answer from the Chinook SQLite database (artists, albums, tracks,
genres, media types, playlists, customers, employees, invoices).

Return JSON with keys:
- intent: one of sql, lookup, clarify, out_of_scope
- rationale: short string
- clarify_question: string, required when intent is clarify

Use lookup when the question depends on a person/artist/album/track/playlist/genre name
that may be misspelled or incomplete.
Use sql when the question is already specific enough to query (counts, rankings, joins, lists).
Use clarify when a metric or entity is ambiguous (e.g. "best" with no definition).
Use out_of_scope for weather, news, general music trivia, or anything not in Chinook.
"""

SQL_SYSTEM = f"""You write SQLite SELECT queries for the Chinook database.
Return JSON with keys:
- sql: a single SELECT or WITH ... SELECT
- rationale: why this query answers the question

Rules:
- Use ONLY tables and columns in the schema below.
- Read-only. No INSERT/UPDATE/DELETE/DROP/PRAGMA/ATTACH.
- Prefer joins via the documented foreign keys.
- If catalog entity IDs are provided, filter with those IDs instead of raw user spelling.
- Always include LIMIT unless the query is a single-row aggregate.
- Never invent rows. If unsure, still write the most conservative SELECT.

{schema_card()}
"""

ANSWER_SYSTEM = """You answer strictly from the SQL result set of the Chinook sample database.
Rules:
- If rows are empty, say the Chinook database has no matching data. Do not guess.
- Do not use outside music knowledge even if you recognize an artist name.
- Mention the metric you used when ranking (revenue, quantity, invoice count, etc.).
- Keep the answer concise. Do not dump huge lists; summarize.
- If the SQL or rows contradict a user assumption, follow the rows.
"""


@dataclass
class BotReply:
    text: str
    intent: str
    sql: str | None = None
    rows: list[dict] = field(default_factory=list)
    hits: list[dict] = field(default_factory=list)
    error: str | None = None


class ChinookAgent:
    def __init__(self, db_path: Path | None = None):
        self.db_path = initialize_database(db_path=db_path)

    def ask(self, question: str, history: list[dict] | None = None) -> BotReply:
        history = history or []
        compact_history = [
            {"role": m["role"], "content": m["content"]}
            for m in history
            if m.get("role") in {"user", "assistant"} and m.get("content")
        ]
        route = complete_json(
            ROUTER_SYSTEM,
            f"User question: {question}",
            compact_history,
        )
        intent = str(route.get("intent", "sql")).lower()
        if intent not in {"sql", "lookup", "clarify", "out_of_scope"}:
            intent = "sql"

        if intent == "out_of_scope":
            return BotReply(
                text=(
                    "I only answer questions from the Chinook store database "
                    "(catalog, playlists, customers, employees, and invoices). "
                    "That question is outside this dataset."
                ),
                intent=intent,
            )
        if intent == "clarify":
            q = route.get("clarify_question") or (
                "Could you clarify what you mean? For example, ranking by revenue, "
                "number of tracks sold, or invoice count?"
            )
            return BotReply(text=str(q), intent=intent)

        conn = connect_readonly(self.db_path)
        try:
            hits: list[dict] = []
            if intent == "lookup":
                hits = search_names(conn, question)
            return self._run_sql_path(conn, question, compact_history, hits, intent)
        finally:
            conn.close()

    def _run_sql_path(
        self,
        conn: sqlite3.Connection,
        question: str,
        history: list[dict],
        hits: list[dict],
        intent: str,
    ) -> BotReply:
        user_prompt = f"Question: {question}\n\n{format_hits(hits)}"
        generated = complete_json(SQL_SYSTEM, user_prompt, history)
        raw_sql = str(generated.get("sql", "")).strip()
        try:
            sql = validate_sql(raw_sql)
        except SqlGuardError as exc:
            return BotReply(
                text=(
                    "I could not build a safe read-only query for that question. "
                    f"{exc}"
                ),
                intent=intent,
                sql=raw_sql or None,
                hits=hits,
                error=str(exc),
            )

        try:
            cursor = conn.execute(sql)
            columns = [d[0] for d in cursor.description] if cursor.description else []
            fetched = cursor.fetchmany(ROW_CAP)
            rows = [dict(zip(columns, row)) for row in fetched]
        except sqlite3.Error as exc:
            return BotReply(
                text="The generated query failed against Chinook. I will not guess an answer.",
                intent=intent,
                sql=sql,
                hits=hits,
                error=str(exc),
            )

        answer = complete_text(
            ANSWER_SYSTEM,
            (
                f"Question: {question}\n\nSQL:\n{sql}\n\n"
                f"Rows (JSON, capped at {ROW_CAP}):\n{json.dumps(rows, default=str)}"
            ),
        )
        return BotReply(text=answer, intent=intent, sql=sql, rows=rows, hits=hits)
