# old_server/database/sql/components.py

from __future__ import annotations
from abc        import ABC, abstractmethod
from dataclasses import dataclass
from typing     import ClassVar

from sql.conversion import sql

DataType = bool | int | float | str | bytes | None
Payload  = tuple[DataType, ...]


@dataclass(eq=False, frozen=True)
class Operand:
    value: DataType
    field: bool      = None
    base:  type      = None

    def dump_value(self) -> DataType:
        return sql.dump(self.value, self.base)

    def query(self, raw: bool = False) -> str:
        if self.field:
            return str(self.value)
        if not raw:
            return "?"
        data = self.dump_value()
        return str(data) if isinstance(data, str) else repr(data)

    def dump(self, raw: bool = False) -> Payload:
        if raw or self.field:
            return ()
        return (self.dump_value(),)

    @staticmethod
    def auto(val) -> Operand:
        if isinstance(val, Operand):
            return val
        return (field if isinstance(val, Field) else value)(val)

    def typed(self, base=None) -> Operand:
        return Operand(self.value, self.field, self.base or base)

    def _operands(self, other) -> tuple[Operand, Operand]:
        other = Operand.auto(other)
        return self.typed(other.base), other

    def __eq__(self, other)  -> "Equals":       return Equals(*self._operands(other))
    def __ne__(self, other)  -> "NotEquals":    return NotEquals(*self._operands(other))
    def __lt__(self, other)  -> "Less":         return Less(*self._operands(other))
    def __le__(self, other)  -> "LessEq":       return LessEq(*self._operands(other))
    def __gt__(self, other)  -> "Greater":      return Greater(*self._operands(other))
    def __ge__(self, other)  -> "GreaterEq":    return GreaterEq(*self._operands(other))
    def __add__(self, other) -> "Add":          return Add(*self._operands(other))
    def __sub__(self, other) -> "Sub":          return Sub(*self._operands(other))
    def __mul__(self, other) -> "Mul":          return Mul(*self._operands(other))
    def __truediv__(self, other) -> "Div":      return Div(*self._operands(other))

    def __hash__(self):
        return hash((self.value, self.field, self.base))


@dataclass(frozen=True, eq=False, unsafe_hash=True)
class Field:
    name:     str
    base:     type
    primary:  bool = None
    unique:   bool = None
    nullable: bool = None

    def definition(self) -> str:
        parts = [self.name, sql.sql_name(self.base)]
        if self.primary:
            parts.append("PRIMARY KEY")
        if self.unique:
            parts.append("UNIQUE")
        if self.nullable is False:
            parts.append("NOT NULL")
        return " ".join(parts)

    def dump(self, data) -> DataType:
        return sql.dump(data, self.base)

    def load(self, data) -> DataType:
        return sql.load(data, self.base)

    def _operands(self, other) -> tuple[Operand, Operand]:
        return field(self), Operand.auto(other).typed(self.base)

    def __eq__(self, other)  -> "Equals":    val, o = self._operands(other); return val == o
    def __ne__(self, other)  -> "NotEquals": val, o = self._operands(other); return val != o
    def __lt__(self, other)  -> "Less":      val, o = self._operands(other); return val <  o
    def __le__(self, other)  -> "LessEq":    val, o = self._operands(other); return val <= o
    def __gt__(self, other)  -> "Greater":   val, o = self._operands(other); return val >  o
    def __ge__(self, other)  -> "GreaterEq": val, o = self._operands(other); return val >= o


def field(data: str | Field) -> Operand:
    if isinstance(data, str):
        return Operand(value=data, field=True)
    return Operand(value=data.name, field=True, base=data.base)

def value(data: DataType, base: type = None) -> Operand:
    return Operand(value=data, field=False, base=base)


class Statement(ABC):
    def __and__(self, other: Statement) -> "All":
        return All(_statements(self, other, All))

    def __or__(self, other: Statement) -> "Any":
        return Any(_statements(self, other, Any))

    def __invert__(self) -> "Not | Statement":
        return self.statement if isinstance(self, Not) else Not(self)

    @abstractmethod
    def query(self, raw: bool = False) -> str: ...

    @abstractmethod
    def dump(self, raw: bool = False) -> Payload: ...


def _statements(s, other, base):
    values = list(s.statements) if isinstance(s, base) else [s]
    values.extend(other.statements if isinstance(other, base) else [other])
    return tuple(values)

def _dump_statements(s, raw: bool = False) -> Payload:
    values = []
    for stmt in s.statements:
        values.extend(stmt.dump(raw))
    return tuple(values)


@dataclass(frozen=True)
class All(Statement):
    statements: tuple[Statement, ...]
    def query(self, raw=False) -> str:
        return " AND ".join(f"({s.query(raw)})" for s in self.statements)
    def dump(self, raw=False) -> Payload:
        return _dump_statements(self, raw)

@dataclass(frozen=True)
class Any(Statement):
    statements: tuple[Statement, ...]
    def query(self, raw=False) -> str:
        return " OR ".join(f"({s.query(raw)})" for s in self.statements)
    def dump(self, raw=False) -> Payload:
        return _dump_statements(self, raw)

@dataclass(frozen=True)
class Not(Statement):
    statement: Statement
    def query(self, raw=False) -> str:
        return f"NOT {self.statement.query(raw)}"
    def dump(self, raw=False) -> Payload:
        return self.statement.dump(raw)


@dataclass(frozen=True)
class Operation(Statement, ABC):
    a: Operand
    b: Operand
    OPERATOR: ClassVar[str]

    def query(self, raw=False) -> str:
        return f"{self.a.query(raw)} {self.OPERATOR} {self.b.query(raw)}"

    def dump(self, raw=False) -> Payload:
        return self.a.dump(raw) + self.b.dump(raw)


class Equals(Operation):    OPERATOR: ClassVar[str] = "="
class NotEquals(Operation): OPERATOR: ClassVar[str] = "!="
class Less(Operation):      OPERATOR: ClassVar[str] = "<"
class LessEq(Operation):    OPERATOR: ClassVar[str] = "<="
class Greater(Operation):   OPERATOR: ClassVar[str] = ">"
class GreaterEq(Operation): OPERATOR: ClassVar[str] = ">="
class Add(Operation):       OPERATOR: ClassVar[str] = "+"
class Sub(Operation):       OPERATOR: ClassVar[str] = "-"
class Mul(Operation):       OPERATOR: ClassVar[str] = "*"
class Div(Operation):       OPERATOR: ClassVar[str] = "/"
