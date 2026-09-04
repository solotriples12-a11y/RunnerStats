import sqlite3


def listar_carreras(conn: sqlite3.Connection, anio: int | None = None) -> list[sqlite3.Row]:
    """Carreras de más reciente a más antigua.

    `tiene_detalle` distingue el nivel de fidelidad: las carreras sin
    muestreos no admiten gráficas, zonas de FC ni PRs por ventana rodante.
    La UI tiene que decirlo en vez de aparentar que todas son iguales.
    """
    filtro, params = "", []
    if anio is not None:
        filtro = "WHERE strftime('%Y', c.fecha_inicio_unix, 'unixepoch') = ?"
        params = [str(anio)]

    return conn.execute(
        f"""
        SELECT c.id, c.fecha_inicio_unix, c.distancia_metros,
               c.duracion_segundos, c.fuente, c.fc_media,
               EXISTS (SELECT 1 FROM muestreo m WHERE m.carrera_id = c.id)
                   AS tiene_detalle
        FROM carrera c
        {filtro}
        ORDER BY c.fecha_inicio_unix DESC
        """,
        params,
    ).fetchall()
