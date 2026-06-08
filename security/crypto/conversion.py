# database/sql/conversion.py
# MasterConverter â€” from your SQL builder assignment.

PYTHON_TYPES_TO_SQL_NAMES = {
    bool:  "INTEGER",
    int:   "INTEGER",
    float: "REAL",
    str:   "TEXT",
    bytes: "BLOB",
}


class MasterConverter:
    @staticmethod
    def dump(value, base=None):
        return value

    @staticmethod
    def load(value, base=None):
        return value

    @staticmethod
    def sql_types() -> tuple:
        return tuple(PYTHON_TYPES_TO_SQL_NAMES.keys())

    @staticmethod
    def sql_name(base) -> str:
        return PYTHON_TYPES_TO_SQL_NAMES[base]


sql = MasterConverter