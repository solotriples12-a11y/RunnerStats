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


# Fraccion de la carrera que deben cubrir los puntos con distancia para que
# la serie sirva de linea temporal.
COBERTURA_MINIMA = 0.85


def _cubre_la_carrera(puntos, ms) -> bool:
    """La serie de distancia debe abarcar casi toda la carrera.

    Visto en 2 de 206 carreras: Nike escribio distancia cada 10 s hasta el
    segundo 850 y luego dejo de hacerlo, pero atribuyo a ese tramo los 4282 m
    completos. El resumen de la carrera sigue siendo fiable; su linea temporal
    no. Derivar ritmo de ahi daba 3:19/km cuando la media real era 4:47.
    """
    duracion = ms[-1]["timestamp_unix"] - ms[0]["timestamp_unix"]
    if duracion <= 0:
        return True
    return (puntos[-1][0] - puntos[0][0]) / duracion >= COBERTURA_MINIMA


def _con_distancia(ms) -> list[tuple[int, float]]:
    """Instantes con distancia acumulada, derivándola del GPS si hace falta.

    Nike escribe la distancia por punto en unas carreras y solo el total en
    otras. Cuando falta pero hay traza, se deriva: es la misma técnica
    validada con un 0,3 % de error, y sin ella estas carreras se quedarían
    sin ritmo ni parciales pese a tener 800 puntos de GPS.
    """
    propia = [(m["timestamp_unix"], m["distancia_acumulada_metros"])
              for m in ms if m["distancia_acumulada_metros"] is not None]
    if len(propia) > 2 and _cubre_la_carrera(propia, ms):
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
    """Parciales por kilómetro completo, con la FC media de cada tramo.

    Interpola el instante exacto de cada corte en vez de quedarse con la
    muestra más cercana: a 2,2 s de muestreo, redondear mete varios segundos
    de error en cada kilómetro.
    """
    puntos = _con_distancia(ms)
    if len(puntos) < 2:
        return []

    pulsos = [(m["timestamp_unix"], m["frecuencia_cardiaca"]) for m in ms
              if m["frecuencia_cardiaca"] is not None]

    def fc_media(t0: float, t1: float) -> int | None:
        dentro = [v for t, v in pulsos if t0 <= t <= t1]
        return round(sum(dentro) / len(dentro)) if dentro else None

    salida = []
    objetivo = 1000.0
    anterior_t = puntos[0][0]
    for (t0, d0), (t1, d1) in zip(puntos, puntos[1:]):
        while d0 <= objetivo <= d1 and d1 > d0:
            t = t0 + (t1 - t0) * (objetivo - d0) / (d1 - d0)
            salida.append({"km": int(objetivo // 1000),
                           "segundos": t - anterior_t, "parcial": False,
                           "fc": fc_media(anterior_t, t)})
            anterior_t = t
            objetivo += 1000.0

    # El trozo final no es un kilómetro: se marca para que nadie lo compare
    # con los demás. Es la trampa que ya nos mordió con My Run Stats.
    fin_t, fin_d = puntos[-1]
    sobra = fin_d - (objetivo - 1000.0)
    if sobra > 50:
        salida.append({"km": len(salida) + 1, "segundos": fin_t - anterior_t,
                       "parcial": True, "metros": sobra,
                       "fc": fc_media(anterior_t, fin_t)})
    return salida


def ruta(ms) -> list[tuple[float, float]]:
    return [(m["latitud"], m["longitud"]) for m in ms
            if m["latitud"] is not None and m["longitud"] is not None]


# Distancias para las que se busca la mejor ventana dentro de una carrera.
# Media y maratón se declaran ya: no aparecen hasta que alguna carrera las
# cubra, porque `mejor_ventana` devuelve None si no se llega a la distancia.
DISTANCIAS = (1000, 3000, 5000, 10000, 21097, 42195)

NOMBRES = {1000: "1K", 3000: "3K", 5000: "5K", 10000: "10K",
           21097: "Media maratón", 42195: "Maratón"}


def _sin_saltos(puntos: list[tuple[int, float]]) -> list[tuple[int, float]]:
    """Serie de distancia descontando los tramos imposibles.

    Los incrementos de Nike traen picos aislados: en una carrera de 2018 hay
    37 tramos por encima de 12 m/s, con maximos de 79 km/h. Sin descontarlos
    el "mejor kilometro" salia en 1:25, mas rapido que el record del mundo.

    Es raro (179 de 206 carreras no tienen ni uno) pero basta un pico para
    inventar un record. Se usa el mismo umbral que para el GPS derivado.
    """
    if len(puntos) < 2:
        return puntos
    limpio = [(puntos[0][0], 0.0)]
    acumulado = 0.0
    for (t0, d0), (t1, d1) in zip(puntos, puntos[1:]):
        paso = d1 - d0
        if 0 <= paso <= geo.VELOCIDAD_ABSURDA * max(t1 - t0, 1):
            acumulado += paso
        limpio.append((t1, acumulado))
    return limpio


def mejor_ventana(puntos: list[tuple[int, float]], metros: float):
    """Tramo más rápido que cubre `metros` dentro de una carrera.

    Barrido de dos punteros sobre la distancia acumulada. El instante de
    inicio se **interpola**: a 2,2 s de muestreo, empezar a contar en la
    muestra más cercana mete varios segundos en un récord de 1 km.

    Devuelve (segundos, inicio_unix, fin_unix) o None si la carrera no llega
    a esa distancia.
    """
    if len(puntos) < 2 or puntos[-1][1] - puntos[0][1] < metros:
        return None

    mejor = None
    i = 0
    for j in range(1, len(puntos)):
        tj, dj = puntos[j]
        objetivo = dj - metros
        while i + 1 < j and puntos[i + 1][1] <= objetivo:
            i += 1
        ti, di = puntos[i]
        if di > objetivo:
            continue
        ti1, di1 = puntos[i + 1]
        inicio = (ti + (ti1 - ti) * (objetivo - di) / (di1 - di)
                  if di1 > di else ti)
        segundos = tj - inicio
        if segundos > 0 and (mejor is None or segundos < mejor[0]):
            mejor = (segundos, inicio, tj)
    return mejor


def ventanas(ms) -> dict[int, tuple]:
    """Mejor ventana de cada distancia dentro de una carrera."""
    puntos = _sin_saltos(_con_distancia(ms))
    return {m: v for m in DISTANCIAS
            if (v := mejor_ventana(puntos, m)) is not None}
