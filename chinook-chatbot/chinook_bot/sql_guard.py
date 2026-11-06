"""Parse and allow only read-only Chinook SELECT statements."""

from __future__ import annotations

from sqlglot import exp, parse
from sqlglot.errors import ParseError

from chinook_bot.schema import ALLOWED_COLUMNS, ALLOWED_TABLES

MAX_LIMIT = 50
FORBIDDEN = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.Command,
    exp.Merge,
    exp.Pragma,
    exp.Transaction,
    exp.Grant,
)


class SqlGuardError(ValueError):
    pass


def _is_aggregate_only(select: exp.Select) -> bool:
    if select.args.get("group") or select.args.get("from") is None:
        return False
    expressions = select.expressions
    if not expressions:
        return False
    for expr in expressions:
        if expr.find(exp.Star):
            return False
        if not expr.find((exp.AggFunc, exp.Count)):
            return False
    return True


def _ensure_limit(select: exp.Select) -> None:
    if select.args.get("limit") is not None:
        limit_node = select.args["limit"]
        try:
            n = int(limit_node.expression.this)
            if n > MAX_LIMIT:
                select.set("limit", exp.Limit(expression=exp.Literal.number(MAX_LIMIT)))
        except (TypeError, ValueError, AttributeError):
            select.set("limit", exp.Limit(expression=exp.Literal.number(MAX_LIMIT)))
        return
    if _is_aggregate_only(select) and not select.args.get("group"):
        return
    select.set("limit", exp.Limit(expression=exp.Literal.number(MAX_LIMIT)))


def _outer_select(tree: exp.Expression) -> exp.Select | None:
    if isinstance(tree, exp.Select):
        return tree
    if isinstance(tree, exp.Union):
        return _outer_select(tree.this) or _outer_select(tree.expression)
    if isinstance(tree, exp.With):
        return _outer_select(tree.this)
    if isinstance(tree, exp.Subquery):
        return _outer_select(tree.this)
    return tree.find(exp.Select)


def validate_sql(sql: str) -> str:
    cleaned = sql.strip()
    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].strip()
    if not cleaned:
        raise SqlGuardError("Empty SQL")
    if ";" in cleaned:
        raise SqlGuardError("Multiple SQL statements are not allowed")

    try:
        statements = parse(cleaned, read="sqlite")
    except ParseError as exc:
        raise SqlGuardError(f"Could not parse SQL: {exc}") from exc

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise SqlGuardError("Exactly one SQL statement is required")

    tree = statements[0]
    if not isinstance(tree, (exp.Select, exp.Union, exp.With)):
        raise SqlGuardError("Only SELECT queries are allowed")

    for node in tree.walk():
        if isinstance(node, FORBIDDEN):
            raise SqlGuardError(f"Disallowed SQL node: {type(node).__name__}")
        if isinstance(node, exp.Table):
            name = (node.name or "").lower()
            if not name:
                continue
            if name not in ALLOWED_TABLES:
                raise SqlGuardError(f"Table not allowed: {node.name}")
        if isinstance(node, exp.Column) and node.table:
            table = node.table.lower()
            col = (node.name or "").lower()
            if table in ALLOWED_COLUMNS and col and col not in ALLOWED_COLUMNS[table]:
                if col not in {"rank"}:
                    raise SqlGuardError(f"Unknown column {node.table}.{node.name}")

    select = _outer_select(tree)
    if select is None:
        raise SqlGuardError("Could not find a SELECT clause")
    _ensure_limit(select)
    return tree.sql(dialect="sqlite")
