import sqlite3
from pathlib import Path

ESQUEMA = Path(__file__).parent / "schema.sql"


def conectar(ruta: str | Path) -> sqlite3.Connection:
    """Abre la base y garantiza que el esquema existe.

    `foreign_keys` hay que activarlo en cada conexión: SQLite lo trae apagado
    por defecto y sin él el ON DELETE CASCADE de muestreo no se aplica.
    """
    conn = sqlite3.connect(ruta)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(ESQUEMA.read_text())
    return conn
