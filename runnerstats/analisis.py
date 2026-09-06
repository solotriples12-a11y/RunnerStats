"""Estadísticas derivadas de las carreras.

Todo lo de aquí se calcula solo con el resumen (fecha, distancia, duración),
así que aplica a las 207 carreras de My Run Stats. Los cálculos que necesitan
muestreos —zonas de FC, eficiencia cardiovascular, récords por ventana
rodante— viven fuera de este módulo porque aún no hay datos que los soporten.
"""

import sqlite3
from datetime import datetime, timedelta, timezone

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
            " FROM carrera WHERE sustituida_por IS NULL ORDER BY a DESC"
        )
    ]


def resumen(conn: sqlite3.Connection, anio: int | None = None) -> dict:
    filtro, params = _where(anio)
    fila = conn.execute(
        f"""
        SELECT COUNT(*)               AS carreras,
               SUM(distancia_metros)  AS metros,
               SUM(duracion_segundos) AS segundos
        FROM carrera WHERE sustituida_por IS NULL {filtro}
        """,
        params,
    ).fetchone()

    return {
        "carreras": fila["carreras"] or 0,
        "metros": fila["metros"] or 0,
        "segundos": fila["segundos"] or 0,
    }


MESES_CORTOS = ("ene", "feb", "mar", "abr", "may", "jun",
                "jul", "ago", "sep", "oct", "nov", "dic")

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")


def rango(agrupacion: str, clave: str) -> tuple[int, int] | None:
    """Tramo [inicio, fin) en unix de un periodo, para poder listarlo.

    La clave es la misma que devuelve `volumen`, o sea la que produce el SQL
    de `AGRUPACIONES`: "2024", "2024-02" o el lunes "2024-02-05". Devuelve
    None si no cuadra, que es lo que llega por URL manipulada.
    """
    try:
        if agrupacion == "anio":
            d0 = datetime(int(clave), 1, 1, tzinfo=timezone.utc)
            d1 = d0.replace(year=d0.year + 1)
        elif agrupacion == "mes":
            a, m = (int(x) for x in clave.split("-"))
            d0 = datetime(a, m, 1, tzinfo=timezone.utc)
            d1 = datetime(a + (m == 12), m % 12 + 1, 1, tzinfo=timezone.utc)
        elif agrupacion == "semana":
            d0 = datetime.fromisoformat(clave).replace(tzinfo=timezone.utc)
            if d0.weekday() != 0:
                return None          # las semanas empiezan en lunes
            d1 = d0 + timedelta(days=7)
        else:
            return None
    except ValueError:
        return None
    return int(d0.timestamp()), int(d1.timestamp())


def titulo_periodo(agrupacion: str, clave: str) -> str:
    """Como se lee ese periodo en la cabecera de su pagina."""
    inicio, _ = rango(agrupacion, clave)
    d = datetime.fromtimestamp(inicio, timezone.utc)
    if agrupacion == "anio":
        return clave
    if agrupacion == "mes":
        return f"{MESES[d.month - 1].capitalize()} de {d.year}"
    return f"Semana del {d.day} de {MESES[d.month - 1]} de {d.year}"

# Clave de agrupacion -> expresion SQL.
#
# La semana empieza en lunes. SQLite no tiene "inicio de semana", asi que se
# usa el idioma habitual: 'weekday 0' avanza al domingo de esa semana (o se
# queda si ya es domingo) y restando 6 dias se cae en su lunes.
AGRUPACIONES = {
    "anio": "strftime('%Y', fecha_inicio_unix, 'unixepoch')",
    "mes": "strftime('%Y-%m', fecha_inicio_unix, 'unixepoch')",
    "semana": "date(fecha_inicio_unix, 'unixepoch', 'weekday 0', '-6 days')",
    "carrera": "id",
}


def _etiqueta(agrupacion: str, clave: str, inicio_unix: int, un_solo_anio: bool) -> str:
    if agrupacion == "anio":
        return clave
    d = datetime.fromtimestamp(inicio_unix, timezone.utc)
    if agrupacion == "mes":
        return MESES_CORTOS[d.month - 1] if un_solo_anio else \
            f"{MESES_CORTOS[d.month - 1]} {d.year % 100:02d}"
    return f"{d.day} {MESES_CORTOS[d.month - 1]}"


def volumen(conn: sqlite3.Connection, agrupacion: str = "anio",
            anio: int | None = None) -> list[dict]:
    """Kilometros agrupados por año, mes, semana o carrera.

    Agrupar por año solo tiene sentido sin filtro: con un año elegido la
    grafica pinta ese año, no los quince. Las demas agrupaciones respetan el
    filtro; sin el, el histórico completo por semanas serian ~770 barras y
    no se lee nada.
    """
    # Normalizar aqui y no solo al elegir el SQL: el relleno de huecos
    # tambien se ramifica por esta clave.
    if agrupacion not in AGRUPACIONES:
        agrupacion = "anio"
    expr = AGRUPACIONES[agrupacion]
    filtro, params = ("", []) if agrupacion == "anio" else _where(anio)

    filas = conn.execute(
        f"""
        SELECT {expr}                   AS clave,
               COUNT(*)                 AS carreras,
               SUM(distancia_metros)/1000 AS km,
               MIN(fecha_inicio_unix)   AS inicio
        FROM carrera WHERE sustituida_por IS NULL {filtro}
        GROUP BY clave ORDER BY inicio
        """,
        params,
    ).fetchall()

    un_solo_anio = anio is not None and agrupacion != "anio"
    datos = [dict(f) for f in filas]
    # Los huecos se rellenan cuando el eje es un tramo de tiempo cerrado: los
    # años del histórico, o los doce meses del año elegido. Sin año, mes y
    # semana no: el histórico entero son 178 meses y ~770 semanas, la mayoria
    # sin salir a correr, y el recorte a los ultimos N se gastaba en aire.
    if agrupacion == "anio" or (anio is not None and agrupacion != "carrera"):
        datos = _rellenar_huecos(agrupacion, datos, anio)

    # Sin año filtrado, las agrupaciones finas darian cientos de barras
    # ilegibles (el histórico completo por semanas son ~770). Se recorta a
    # los ultimos N periodos y la UI lo dice.
    recortado = False
    if anio is None and agrupacion in TOPES:
        tope = TOPES[agrupacion]
        if len(datos) > tope:
            datos, recortado = datos[-tope:], True

    for d in datos:
        d["etiqueta"] = _etiqueta(agrupacion, d["clave"], d["inicio"], un_solo_anio)
        d["recortado"] = recortado
    return datos


TOPES = {"mes": 36, "semana": 52, "carrera": 50}


def _rellenar_huecos(agrupacion: str, datos: list[dict],
                     anio: int | None = None) -> list[dict]:
    """Inserta periodos a cero entre el primero y el ultimo con datos.

    Sin esto el eje miente: un mes vacio simplemente no aparece y su vecino
    de dos meses despues sale pegado, como si fueran consecutivos.

    Con un año filtrado los meses son los doce del calendario, no del primero
    al ultimo con carreras: al mirar un año se espera ver el año entero, y
    empezar en abril porque en marzo no se salio a correr esconde ese dato.
    """
    porclave = {d["clave"]: d for d in datos}
    salida = []

    if agrupacion == "mes" and anio is not None:
        claves = [(f"{anio:04d}-{m:02d}", datetime(anio, m, 1, tzinfo=timezone.utc))
                  for m in range(1, 13)]
    elif len(datos) < 2:
        return datos
    elif agrupacion == "anio":
        claves = [(str(a), datetime(a, 1, 1, tzinfo=timezone.utc))
                  for a in range(int(datos[0]["clave"]), int(datos[-1]["clave"]) + 1)]
    elif agrupacion == "mes":
        y, m = (int(x) for x in datos[0]["clave"].split("-"))
        fin = tuple(int(x) for x in datos[-1]["clave"].split("-"))
        claves = []
        while (y, m) <= fin:
            claves.append((f"{y:04d}-{m:02d}", datetime(y, m, 1, tzinfo=timezone.utc)))
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    else:  # semana: lunes a lunes
        d0 = datetime.fromisoformat(datos[0]["clave"]).replace(tzinfo=timezone.utc)
        d1 = datetime.fromisoformat(datos[-1]["clave"]).replace(tzinfo=timezone.utc)
        claves = []
        while d0 <= d1:
            claves.append((d0.date().isoformat(), d0))
            d0 += timedelta(days=7)

    for clave, fecha in claves:
        if clave in porclave:
            salida.append(porclave[clave])
        else:
            salida.append({"clave": clave, "carreras": 0, "km": 0.0,
                           "inicio": int(fecha.timestamp())})
    return salida


def ritmos(conn: sqlite3.Connection, anio: int | None = None) -> list[dict]:
    """Una entrada por carrera, para la nube de puntos de evolución."""
    filtro, params = _where(anio)
    return [
        dict(r)
        for r in conn.execute(
            f"""
            SELECT fecha_inicio_unix,
                   distancia_metros,
                   duracion_segundos * 1000.0 / distancia_metros AS ritmo
            FROM carrera
            WHERE sustituida_por IS NULL AND distancia_metros >= 1000 {filtro}
            ORDER BY fecha_inicio_unix
            """,
            params,
        )
    ]


def records_rodantes(conn: sqlite3.Connection, anio: int | None = None) -> list[dict]:
    """Mejor 1K/5K/10K extraído de DENTRO de cualquier carrera.

    Esto es lo que un corredor entiende por "mi mejor 5K": no hace falta que
    la carrera midiera 5 km, basta con que en algún tramo los cubriera.

    Lee de `record_ventana`, que se rellena al importar. Calcularlo al vuelo
    costaba 300 ms por visita.
    """
    from . import detalle

    filtro, params = _where(anio)
    filas = conn.execute(
        f"""
        SELECT r.metros, r.segundos, r.carrera_id,
               c.fecha_inicio_unix, c.distancia_metros AS distancia_carrera,
               MIN(r.segundos) OVER (PARTITION BY r.metros) AS mejor
        FROM record_ventana r
        JOIN carrera c ON c.id = r.carrera_id
        WHERE c.sustituida_por IS NULL {filtro}
        """,
        params,
    ).fetchall()

    mejores = {}
    for f in filas:
        if f["segundos"] != f["mejor"]:
            continue
        if f["metros"] not in mejores:
            mejores[f["metros"]] = {
                **dict(f), "nombre": detalle.NOMBRES[f["metros"]],
                "ritmo": f["segundos"] / (f["metros"] / 1000),
            }
    return [mejores[d] for d in detalle.DISTANCIAS if d in mejores]


def carrera_mas_larga(conn: sqlite3.Connection, anio: int | None = None) -> dict | None:
    """La carrera de mayor distancia. Va la primera entre los récords porque
    es la única que no depende de tener muestreos: sale del resumen."""
    filtro, params = _where(anio)
    fila = conn.execute(
        f"""
        SELECT id, fecha_inicio_unix, distancia_metros, duracion_segundos
        FROM carrera WHERE sustituida_por IS NULL {filtro}
        ORDER BY distancia_metros DESC LIMIT 1
        """,
        params,
    ).fetchone()
    return dict(fila) if fila else None
