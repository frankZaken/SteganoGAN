# old_server/database/sql/engine.py

import sqlite3
from dataclasses import dataclass
from typing      import Iterable

from sql.query import Query, Insert


@dataclass
class Engine:
    path: str                         = None
    conn: sqlite3.Connection | None   = None

    def open(self, path: str = None) -> "Engine":
        self.path = self.path if path is None else path
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        return self

    def cursor(self) -> sqlite3.Cursor:
        return self.conn.cursor()

    def execute(self, query: Query, executor=None, raw: bool = False) -> Iterable:
        executor = self.conn if executor is None else executor
        caller   = (executor.executemany if isinstance(query, Insert)
                    else executor.execute)
        output = caller(query.query(raw), query.dump(raw))
        return query.process(output)

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()
        self.conn = None
