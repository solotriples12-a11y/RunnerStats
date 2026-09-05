"""Cálculos de una carrera concreta a partir de sus muestreos.

Todo aquí es opcional por diseño: de las 296 carreras visibles, 267 tienen
muestreos pero solo unas tienen GPS, otras pulso y otras distancia acumulada.
Cada función devuelve None o lista vacía cuando falta su materia prima, y la
plantilla omite la sección correspondiente.
"""

import sqlite3

from . import geo

# El ritmo instantáneo entre dos muestras consecutivas es puro ruido. Se
# calcula sobre una ventana hacia atrás.
VENTANA_S = 20

# Por debajo de esto en toda la ventana no estabas corriendo, estabas parado
# (semaforo, pausa automatica). El "ritmo" de una parada tiende a infinito y
# aplasta la escala de la grafica, asi que esos tramos no son un ritmo.
METROS_MINIMOS = 10.0


def carrera(conn: sqlite3.Connection, carrera_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM carrera WHERE id = ?", (carrera_id,)).fetchone()


def muestreos(conn: sqlite3.Connection, carrera_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM muestreo WHERE carrera_id = ? ORDER BY timestamp_unix",
        (carrera_id,),
    ).fetchall()


def _con_distancia(ms) -> list[tuple[int, float]]:
    """Instantes con distancia acumulada, derivándola del GPS si hace falta.

    Nike escribe la distancia por punto en unas carreras y solo el total en
    otras. Cuando falta pero hay traza, se deriva: es la misma técnica
    validada con un 0,3 % de error, y sin ella estas carreras se quedarían
    sin ritmo ni parciales pese a tener 800 puntos de GPS.
    """
    propia = [(m["timestamp_unix"], m["distancia_acumulada_metros"])
              for m in ms if m["distancia_acumulada_metros"] is not None]
    if len(propia) > 2:
        return propia

    acum = geo.acumular([(m["timestamp_unix"], m["latitud"], m["longitud"])
                         for m in ms])
    return sorted(acum.items())


def serie_ritmo(ms) -> list[dict]:
    """Ritmo en s/km sobre una ventana móvil, con su distancia y su instante."""
    puntos = _con_distancia(ms)
    if len(puntos) < 2:
        return []

    salida, j = [], 0
    for i, (t, d) in enumerate(puntos):
        if i == 0:
            continue
        while puntos[j][0] < t - VENTANA_S and j < i - 1:
            j += 1
        # Si las muestras estan mas separadas que la ventana, se usa la
        # anterior en vez de descartar el punto: con muestreo cada 30 s la
        # ventana de 20 s nunca contendria un punto previo y la serie
        # saldria vacia.
        dt = t - puntos[j][0]
        dd = d - puntos[j][1]
        if dt <= 0 or dd < METROS_MINIMOS:
            continue
        salida.append({"t": t, "metros": d, "ritmo": dt / (dd / 1000)})
    return salida


def serie(ms, campo: str) -> list[dict]:
    """Serie de un campo cualquiera contra el instante, saltando los nulos."""
    return [{"t": m["timestamp_unix"], "v": m[campo]}
            for m in ms if m[campo] is not None]


def splits(ms) -> list[dict]:
    """Parciales por kilómetro completo.

    Interpola el instante exacto de cada corte en vez de quedarse con la
    muestra más cercana: a 2,2 s de muestreo, redondear mete varios segundos
    de error en cada kilómetro.
    """
    puntos = _con_distancia(ms)
    if len(puntos) < 2:
        return []

    salida = []
    objetivo = 1000.0
    anterior_t = puntos[0][0]
    for (t0, d0), (t1, d1) in zip(puntos, puntos[1:]):
        while d0 <= objetivo <= d1 and d1 > d0:
            t = t0 + (t1 - t0) * (objetivo - d0) / (d1 - d0)
            salida.append({"km": int(objetivo // 1000),
                           "segundos": t - anterior_t, "parcial": False})
            anterior_t = t
            objetivo += 1000.0

    # El trozo final no es un kilómetro: se marca para que nadie lo compare
    # con los demás. Es la trampa que ya nos mordió con My Run Stats.
    fin_t, fin_d = puntos[-1]
    sobra = fin_d - (objetivo - 1000.0)
    if sobra > 50:
        salida.append({"km": len(salida) + 1, "segundos": fin_t - anterior_t,
                       "parcial": True, "metros": sobra})
    return salida


def ruta(ms) -> list[tuple[float, float]]:
    return [(m["latitud"], m["longitud"]) for m in ms
            if m["latitud"] is not None and m["longitud"] is not None]
