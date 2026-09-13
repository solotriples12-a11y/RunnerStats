import sqlite3

from .analisis import VISIBLE


def listar_carreras(conn: sqlite3.Connection, anio: int | None = None) -> list[sqlite3.Row]:
    """Carreras de más reciente a más antigua."""
    filtro, params = "", []
    if anio is not None:
        filtro = "AND strftime('%Y', c.fecha_inicio_unix, 'unixepoch') = ?"
        params = [str(anio)]

    return conn.execute(
        f"""
        SELECT c.id, c.fecha_inicio_unix, c.distancia_metros,
               c.duracion_segundos, c.fuente, c.fc_media
        FROM carrera c
        WHERE {VISIBLE} {filtro}
        ORDER BY c.fecha_inicio_unix DESC
        """,
        params,
    ).fetchall()


def carreras_en(conn: sqlite3.Connection, inicio: int, fin: int) -> list[sqlite3.Row]:
    """Carreras de un tramo [inicio, fin), de mas reciente a mas antigua."""
    return conn.execute(
        f"""
        SELECT c.id, c.fecha_inicio_unix, c.distancia_metros,
               c.duracion_segundos, c.fuente, c.fc_media
        FROM carrera c
        WHERE {VISIBLE}
          AND c.fecha_inicio_unix >= ? AND c.fecha_inicio_unix < ?
        ORDER BY c.fecha_inicio_unix DESC
        """,
        (inicio, fin),
    ).fetchall()
