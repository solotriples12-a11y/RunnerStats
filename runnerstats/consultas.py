import sqlite3


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
        WHERE c.sustituida_por IS NULL {filtro}
        ORDER BY c.fecha_inicio_unix DESC
        """,
        params,
    ).fetchall()
