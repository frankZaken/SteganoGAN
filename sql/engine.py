# sql/engine.py

import sqlite3
import threading
from typing import Iterable

from sql.query import Query, Insert


class Engine:
    """
    SQLite engine with a separate connection per thread.

    A single sqlite3 connection is not safe to use from multiple threads at
    once. The server runs each request in its own thread and trains models in
    a background thread, so every thread gets its own connection (stored in
    thread-local storage). WAL mode lets one writer (the training thread) and
    many readers (status polls, other requests) work at the same time without
    blocking each other; busy_timeout makes a brief lock wait instead of
    raising "database is locked".
    """

    def __init__(self, path: str = None):
        self.path = path
        self._local = threading.local()

    def open(self, path: str = None) -> "Engine":
        self.path = self.path if path is None else path
        self._connect()                       # connection for the current thread
        return self

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")     # concurrent reader(s) + writer
        conn.execute("PRAGMA busy_timeout=5000")    # wait up to 5s on a lock
        conn.execute("PRAGMA foreign_keys = ON")
        self._local.conn = conn
        return conn

    @property
    def conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._connect()                  # lazily create one for this thread
        return conn

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
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None
