# old_server/database/sql/table.py

from __future__ import annotations
from dataclasses import dataclass
from typing      import Iterable

from sql.components import Field

DataType = bool | int | float | str | bytes | None
RawItem  = tuple[DataType, ...]
Item     = dict[str | Field, DataType]
F        = Field | str


@dataclass(frozen=True)
class Table:
    name:   str
    fields: tuple[Field, ...]

    def definition(self, exists_ok: bool = False) -> str:
        exists_str = "IF NOT EXISTS " if exists_ok else ""
        fields_def = ",\n    ".join(f.definition() for f in self.fields)
        return f"CREATE TABLE {exists_str}{self.name}(\n    {fields_def}\n);"

    def names(self, fields: Iterable[F] = None) -> Iterable[str]:
        if fields is None:
            return (f.name for f in self.fields)
        return (f if isinstance(f, str) else f.name for f in fields)

    def sorted(self, fields: Iterable[F] = None) -> tuple[str, ...]:
        all_names = [f.name for f in self.fields]
        if fields is None:
            return tuple(all_names)
        input_names = {f if isinstance(f, str) else f.name for f in fields}
        return tuple(n for n in all_names if n in input_names)

    def _find_field(self, name: str) -> Field | None:
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def item(
        self,
        data:   Item | RawItem,
        fields: Iterable[F] = None,
        load:   bool        = False,
    ) -> Item:
        if fields is None:
            relevant = list(self.fields)
        else:
            field_names = {f if isinstance(f, str) else f.name for f in fields}
            relevant    = [f for f in self.fields if f.name in field_names]

        result = {}

        if isinstance(data, dict):
            normalized = {}
            for k, v in data.items():
                key_name = k if isinstance(k, str) else k.name
                normalized[key_name] = v

            for field_obj in relevant:
                val = normalized.get(field_obj.name, None)
                result[field_obj.name] = field_obj.load(val) if load else field_obj.dump(val)
        else:
            use_keys = hasattr(data, "keys")  # sqlite3.Row supports name-based access
            for i, field_obj in enumerate(relevant):
                if use_keys:
                    val = data[field_obj.name]
                else:
                    val = data[i] if i < len(data) else None
                result[field_obj.name] = field_obj.load(val) if load else field_obj.dump(val)

        return result
