# old_server/database/sql/query.py

from __future__ import annotations
from abc        import ABC, abstractmethod
from dataclasses import dataclass
from typing     import Iterable, Self

from sql.components import Statement, Field, DataType
from sql.table import Table, RawItem, Item, F

Payload = tuple[DataType, ...]


class Query(ABC):
    @abstractmethod
    def query(self, raw: bool = False) -> str: ...

    def process(self, output):
        return output

    def dump(self, raw: bool = False):
        return ()


class StatementQuery(ABC):
    statement: Statement = None

    def where(self, statement: Statement) -> Self:
        self.statement = statement
        return self

    def dump_statement(self, raw: bool = False) -> Payload:
        return () if self.statement is None else self.statement.dump(raw)

    def _where_clause(self, raw: bool = False) -> str:
        return f" WHERE {self.statement.query(raw)}" if self.statement else ""


class FieldsQuery(ABC):
    fields: Iterable[F] | None = None

    def all(self) -> Self:
        self.fields = None
        return self

    def each(self, fields) -> Self:
        if isinstance(fields, (str, Field)):
            self.fields = (fields,)
        else:
            self.fields = fields
        return self


@dataclass
class Create(Query):
    table:      Table
    exists_ok:  bool = False

    def ignore(self) -> Self:
        self.exists_ok = True
        return self

    def fail(self) -> Self:
        self.exists_ok = False
        return self

    def query(self, raw: bool = False) -> str:
        return self.table.definition(self.exists_ok)


@dataclass
class Select(Query, StatementQuery, FieldsQuery):
    table:     Table
    fields:    Iterable[F] | None = None
    statement: Statement          = None

    def query(self, raw: bool = False) -> str:
        if self.fields:
            cols = ", ".join(self.table.sorted(self.fields))
        else:
            cols = "*"
        return f"SELECT {cols} FROM {self.table.name}{self._where_clause(raw)};"

    def process(self, output) -> Iterable[Item]:
        for row in output:
            yield self.table.item(row, self.fields, load=True)

    def dump(self, raw: bool = False) -> Payload:
        return self.dump_statement(raw)


@dataclass
class Insert(Query, FieldsQuery):
    table:  Table
    fields: Iterable[F] | None = None
    data:   Iterable           = None

    def values(self, items) -> Self:
        self.data = items
        return self

    def query(self, raw: bool = False) -> str:
        field_order = self.table.sorted(self.fields)
        fields_str  = ", ".join(field_order)
        if raw:
            rows = list(self.dump(raw=True))
            if not rows:
                placeholders = ", ".join(["NULL"] * len(field_order))
            else:
                placeholders = ", ".join(str(v) if not isinstance(v, str)
                                         else f"'{v}'" for v in rows[0])
        else:
            placeholders = ", ".join(["?"] * len(field_order))
        return f"INSERT INTO {self.table.name} ({fields_str}) VALUES ({placeholders});"

    def dump(self, raw: bool = False):
        if raw:
            return ()
        field_order = self.table.sorted(self.fields)
        for row in (self.data or []):
            item_dict = self.table.item(row, self.fields)
            yield tuple(item_dict.get(name) for name in field_order)


@dataclass
class Update(Query, StatementQuery, FieldsQuery):
    table:     Table
    data:      Item | RawItem    = None
    fields:    Iterable[F] | None = None
    statement: Statement          = None

    def set(self, item) -> Self:
        self.data = item
        if isinstance(item, dict):
            self.fields = list(item.keys())
        return self

    def dump_values(self, raw: bool = False) -> Payload:
        if self.data is None:
            return ()
        item_dict = self.table.item(self.data, self.fields)
        return tuple(item_dict.get(name) for name in self.table.sorted(self.fields))

    def dump(self, raw: bool = False) -> Payload:
        return self.dump_values(raw) + self.dump_statement(raw)

    def query(self, raw: bool = False) -> str:
        field_order = self.table.sorted(self.fields)
        if raw:
            vals      = self.dump_values(raw=True)
            set_parts = [f"{name} = {repr(v)}" for name, v in zip(field_order, vals)]
        else:
            set_parts = [f"{name} = ?" for name in field_order]
        set_str = ", ".join(set_parts)
        return f"UPDATE {self.table.name} SET {set_str}{self._where_clause(raw)};"


@dataclass
class Delete(Query, StatementQuery):
    table:     Table
    statement: Statement = None

    def query(self, raw: bool = False) -> str:
        return f"DELETE FROM {self.table.name}{self._where_clause(raw)};"

    def dump(self, raw: bool = False) -> Payload:
        return self.dump_statement(raw)


@dataclass
class Drop(Query):
    table: Table

    def query(self, raw: bool = False) -> str:
        return f"DROP TABLE {self.table.name};"
