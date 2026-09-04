import sqlite3


def listar_carreras(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Carreras de más reciente a más antigua.

    `tiene_detalle` distingue el nivel de fidelidad: las carreras sin
    muestreos no admiten gráficas, zonas de FC ni PRs por ventana rodante.
    La UI tiene que decirlo en vez de aparentar que todas son iguales.
    """
    return conn.execute(
        """
        SELECT c.id, c.fecha_inicio_unix, c.distancia_metros,
               c.duracion_segundos, c.fuente, c.fc_media,
               EXISTS (SELECT 1 FROM muestreo m WHERE m.carrera_id = c.id)
                   AS tiene_detalle
        FROM carrera c
        ORDER BY c.fecha_inicio_unix DESC
        """
    ).fetchall()


def totales(conn: sqlite3.Connection) -> sqlite3.Row:
    return conn.execute(
        """
        SELECT COUNT(*)                  AS carreras,
               SUM(distancia_metros)     AS metros,
               SUM(duracion_segundos)    AS segundos,
               MIN(fecha_inicio_unix)    AS desde
        FROM carrera
        """
    ).fetchone()
