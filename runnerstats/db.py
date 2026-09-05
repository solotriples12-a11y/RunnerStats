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
    _migrar(conn)
    _rellenar_records(conn)
    return conn


# Columnas añadidas despues de que la base existiera en produccion.
# CREATE TABLE IF NOT EXISTS no toca una tabla que ya esta creada.
COLUMNAS_NUEVAS = {"sustituida_por": "TEXT"}


def _migrar(conn: sqlite3.Connection) -> None:
    existentes = {f["name"] for f in conn.execute("PRAGMA table_info(carrera)")}
    for col, tipo in COLUMNAS_NUEVAS.items():
        if col not in existentes:
            conn.execute(f"ALTER TABLE carrera ADD COLUMN {col} {tipo}")
    conn.commit()


def _rellenar_records(conn: sqlite3.Connection) -> None:
    """Rellena `record_ventana` la primera vez que se abre una base que ya
    tenía muestreos.

    La tabla es nueva; sin esto, una base ya existente (la de producción) se
    quedaría sin récords hasta la siguiente importación.
    """
    hay_muestreos = conn.execute("SELECT 1 FROM muestreo LIMIT 1").fetchone()
    if not hay_muestreos:
        return
    if conn.execute("SELECT 1 FROM record_ventana LIMIT 1").fetchone():
        return
    from . import detalle
    detalle.recalcular_records(conn)
