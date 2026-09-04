"""Estadísticas derivadas de las carreras.

Todo lo de aquí se calcula solo con el resumen (fecha, distancia, duración),
así que aplica a las 207 carreras de My Run Stats. Los cálculos que necesitan
muestreos —zonas de FC, eficiencia cardiovascular, récords por ventana
rodante— viven fuera de este módulo porque aún no hay datos que los soporten.
"""

import sqlite3

# Bandas de distancia para los récords. Un récord aquí es el mejor RITMO
# dentro de la banda, no el mejor tiempo: las carreras de una banda no miden
# lo mismo (5,0 y 5,9 km caen en la misma), así que comparar tiempos sería
# comparar distancias distintas.
BANDAS = (
    ("3K", 3.0, 4.0),
    ("5K", 5.0, 6.0),
    ("10K", 10.0, 11.0),
    ("Media", 21.0, 22.0),
)

_FILTRO_ANIO = "AND strftime('%Y', fecha_inicio_unix, 'unixepoch') = ?"


def _where(anio: int | None) -> tuple[str, list]:
    if anio is None:
        return "", []
    return _FILTRO_ANIO, [str(anio)]


def anios(conn: sqlite3.Connection) -> list[int]:
    return [
        int(r[0])
        for r in conn.execute(
            "SELECT DISTINCT strftime('%Y', fecha_inicio_unix, 'unixepoch') a"
            " FROM carrera ORDER BY a DESC"
        )
    ]


def resumen(conn: sqlite3.Connection, anio: int | None = None) -> dict:
    filtro, params = _where(anio)
    fila = conn.execute(
        f"""
        SELECT COUNT(*)               AS carreras,
               SUM(distancia_metros)  AS metros,
               SUM(duracion_segundos) AS segundos,
               MAX(distancia_metros)  AS mas_larga,
               MIN(fecha_inicio_unix) AS desde
        FROM carrera WHERE 1=1 {filtro}
        """,
        params,
    ).fetchone()

    mejor = conn.execute(
        f"""
        SELECT duracion_segundos * 1000.0 / distancia_metros AS ritmo
        FROM carrera WHERE distancia_metros >= 3000 {filtro}
        ORDER BY ritmo LIMIT 1
        """,
        params,
    ).fetchone()

    return {
        "carreras": fila["carreras"] or 0,
        "metros": fila["metros"] or 0,
        "segundos": fila["segundos"] or 0,
        "mas_larga": fila["mas_larga"] or 0,
        "desde": fila["desde"],
        "mejor_ritmo": mejor["ritmo"] if mejor else None,
    }


def records(conn: sqlite3.Connection, anio: int | None = None) -> list[dict]:
    """Mejor ritmo por banda de distancia.

    Son récords POR CARRERA COMPLETA. El "mejor 5K extraído de cualquier
    carrera" necesita distancia acumulada por muestreo y no se puede calcular
    con estas fuentes.
    """
    filtro, params = _where(anio)
    salida = []
    for nombre, minimo, maximo in BANDAS:
        fila = conn.execute(
            f"""
            SELECT id, fecha_inicio_unix, distancia_metros, duracion_segundos,
                   duracion_segundos * 1000.0 / distancia_metros AS ritmo
            FROM carrera
            WHERE distancia_metros >= ? AND distancia_metros < ? {filtro}
            ORDER BY ritmo LIMIT 1
            """,
            [minimo * 1000, maximo * 1000] + params,
        ).fetchone()
        if fila:
            salida.append({"banda": nombre, **dict(fila)})
    return salida


def volumen_por_anio(conn: sqlite3.Connection) -> list[dict]:
    return [
        dict(r)
        for r in conn.execute(
            """
            SELECT strftime('%Y', fecha_inicio_unix, 'unixepoch') AS anio,
                   COUNT(*)                  AS carreras,
                   SUM(distancia_metros)/1000 AS km
            FROM carrera GROUP BY anio ORDER BY anio
            """
        )
    ]


def ritmos(conn: sqlite3.Connection) -> list[dict]:
    """Una entrada por carrera, para la nube de puntos de evolución."""
    return [
        dict(r)
        for r in conn.execute(
            """
            SELECT fecha_inicio_unix,
                   distancia_metros,
                   duracion_segundos * 1000.0 / distancia_metros AS ritmo
            FROM carrera
            WHERE distancia_metros >= 1000
            ORDER BY fecha_inicio_unix
            """
        )
    ]
