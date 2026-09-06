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
COLUMNAS_NUEVAS = {
    "carrera": {"sustituida_por": "TEXT"},
    "muestreo": {"potencia_vatios": "INTEGER", "tiempo_contacto_ms": "INTEGER"},
}


def _migrar(conn: sqlite3.Connection) -> None:
    for tabla, columnas in COLUMNAS_NUEVAS.items():
        existentes = {f["name"] for f in conn.execute(f"PRAGMA table_info({tabla})")}
        for col, tipo in columnas.items():
            if col not in existentes:
                conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} {tipo}")
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
