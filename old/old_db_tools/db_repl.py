# old_db_tools/db_repl.py
# Interactive database explorer for SteganoGAN.
# Run from the IDE:  python SteganoGAN2/old_db_tools/db_repl.py
# Or import in a console:  from SteganoGAN2.old_db_tools.db_repl import *

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent   # PycharmProjects/SteganoGAN/
sys.path.insert(0, str(ROOT))

from SteganoGAN2.app.database.db     import get_engine, DB_PATH
from SteganoGAN2.app.database.schema import (
    USERS_TABLE, MODELS_TABLE, ROOMS_TABLE,
    ROOM_MEMBERS_TABLE, ROOM_MESSAGES_TABLE, CREATIONS_TABLE,
    ROOM_MODELS_TABLE, ROOM_SETTINGS_TABLE, DIRECT_SHARES_TABLE,
)
from SteganoGAN2.app.database.sql.query import Select, Insert, Update, Delete

# ── Convenience aliases ────────────────────────────────────────────────────────

TABLES = {
    "users":          USERS_TABLE,
    "models":         MODELS_TABLE,
    "rooms":          ROOMS_TABLE,
    "room_members":   ROOM_MEMBERS_TABLE,
    "room_messages":  ROOM_MESSAGES_TABLE,
    "creations":      CREATIONS_TABLE,
    "room_models":    ROOM_MODELS_TABLE,
    "room_settings":  ROOM_SETTINGS_TABLE,
    "direct_shares":  DIRECT_SHARES_TABLE,
}


def engine():
    """Return a fresh Engine connected to the DB."""
    return get_engine()


def all(table_name: str) -> list[dict]:
    """Return every row from a table as a list of dicts."""
    table = TABLES[table_name]
    eng   = get_engine()
    rows  = list(eng.execute(Select(table)))
    eng.close()
    return rows


def where(table_name: str, **kwargs) -> list[dict]:
    """Filter rows by field=value kwargs.
    Example: where('users', username='peleg')
    """
    table = TABLES[table_name]
    if not kwargs:
        return all(table_name)

    filters = []
    for col, val in kwargs.items():
        f = next(fld for fld in table.fields if fld.name == col)
        filters.append(f == val)   # Field.__eq__ returns an Equals statement

    statement = filters[0]
    for extra in filters[1:]:
        statement = statement & extra   # Statement.__and__ returns All

    eng  = get_engine()
    rows = list(eng.execute(Select(table).where(statement)))
    eng.close()
    return rows


def show(table_name: str, limit: int = 50):
    """Pretty-print up to `limit` rows from a table."""
    rows = all(table_name)[:limit]
    if not rows:
        print(f"(no rows in {table_name})")
        return
    cols = list(rows[0].keys())
    col_w = {c: max(len(c), max(len(str(r[c])) for r in rows)) for c in cols}
    header = "  ".join(c.ljust(col_w[c]) for c in cols)
    print(header)
    print("-" * len(header))
    for row in rows:
        print("  ".join(str(row[c]).ljust(col_w[c]) for c in cols))
    print(f"\n({len(rows)} row{'s' if len(rows) != 1 else ''})")


def tables():
    """List all known tables."""
    for name in TABLES:
        print(name)


def schema(table_name: str):
    """Print the field definitions for a table."""
    table = TABLES[table_name]
    print(f"Table: {table.name}")
    for f in table.fields:
        print(f"  {f.definition()}")


# ── REPL ───────────────────────────────────────────────────────────────────────

_HELP = """
SteganoGAN DB REPL
==================
  tables()              — list all tables
  schema('name')        — show field definitions for a table
  show('name')          — print rows from a table
  all('name')           — return rows as list of dicts
  where('name', col=v)  — filter rows by column value
  engine()              — raw Engine for custom queries
  exit                  — quit

You can also use the SQL query classes directly:
  from SteganoGAN2.app.database.sql.query import Select, Insert, Update, Delete
  from SteganoGAN2.app.database.schema import USERS_TABLE, ...
"""

if __name__ == "__main__":
    print(_HELP)
    print(f"DB: {DB_PATH}\n")

    # Drop into an interactive Python shell with all helpers pre-imported
    import code
    code.interact(
        banner="Type tables() to get started.",
        local={**globals(), **locals()},
        exitmsg="Bye.",
    )
