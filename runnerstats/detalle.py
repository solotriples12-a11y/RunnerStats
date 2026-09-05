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


# Un intervalo mayor que esto entre dos puntos con distancia es un hueco:
# el muestreo normal va de 1 a 10 s.
HUECO_S = 30
# Margenes contra el resumen de la carrera, que es el dato fiable.
COBERTURA_MINIMA = 0.85
TOLERANCIA_DISTANCIA = 0.10
TOLERANCIA_DURACION = 0.15


def _serie_fiable(puntos, ms, carrera) -> bool:
    """¿Sirve la serie de distancia como linea temporal de la carrera?

    El resumen (distancia y duracion) es fiable; la serie punto a punto no
    siempre. Vistos tres modos de fallo distintos en el export de Nike:

    - Huecos interiores: 890 s seguidos sin ningun punto en una carrera de
      2400. Los incrementos suman bien el total pero se concentran en el
      tramo con datos, y el acumulado llegaba a 5 km en 1230 s cuando la app
      de Nike marca 2093. Salia un 5K de 20:21 donde el real es 34:53.
    - Distancia incompleta: una serie que solo suma el 36 % de los metros.
    - Linea temporal mas larga que la carrera: 2822 s de muestras para una
      carrera de 1932.

    Sin serie fiable no hay ritmo, ni parciales, ni records para esa carrera;
    el resumen se sigue mostrando.
    """
    if len(puntos) < 3:
        return False

    span = puntos[-1][0] - puntos[0][0]
    if span <= 0:
        return False

    # 1. Sin huecos: el tiempo realmente cubierto frente al de la carrera.
    duracion = ms[-1]["timestamp_unix"] - ms[0]["timestamp_unix"] or span
    cubierto = sum(b - a for (a, _), (b, _) in zip(puntos, puntos[1:])
                   if b - a <= HUECO_S)
    if cubierto / duracion < COBERTURA_MINIMA:
        return False

    if carrera is None:
        return True

    # 2. La serie debe sumar los metros que declara la carrera.
    declarada = carrera["distancia_metros"]
    if declarada > 0:
        if abs((puntos[-1][1] - puntos[0][1]) - declarada) / declarada > TOLERANCIA_DISTANCIA:
            return False

    # 3. Y ocupar el tiempo que declara la carrera.
    dur = carrera["duracion_segundos"]
    if dur > 0 and abs(span - dur) / dur > TOLERANCIA_DURACION:
        return False

    return True


def _con_distancia(ms, carrera=None) -> list[tuple[int, float]]:
    """Instantes con distancia acumulada, derivandola del GPS si hace falta.

    Nike escribe la distancia por punto en unas carreras y solo el total en
    otras. Cuando falta pero hay traza, se deriva: es la misma tecnica
    validada con un 0,3 % de error, y sin ella estas carreras se quedarian
    sin ritmo ni parciales pese a tener 800 puntos de GPS.
    """
    propia = [(m["timestamp_unix"], m["distancia_acumulada_metros"])
              for m in ms if m["distancia_acumulada_metros"] is not None]
    if _serie_fiable(propia, ms, carrera):
        return propia

    acum = geo.acumular([(m["timestamp_unix"], m["latitud"], m["longitud"])
                         for m in ms])
    derivada = sorted(acum.items())
    return derivada if _serie_fiable(derivada, ms, carrera) else []


def serie_ritmo(ms, carrera=None) -> list[dict]:
    """Ritmo en s/km sobre una ventana móvil, con su distancia y su instante."""
    puntos = _con_distancia(ms, carrera)
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


def splits(ms, carrera=None) -> list[dict]:
    """Parciales por kilómetro completo, con la FC media de cada tramo.

    Interpola el instante exacto de cada corte en vez de quedarse con la
    muestra más cercana: a 2,2 s de muestreo, redondear mete varios segundos
    de error en cada kilómetro.
    """
    puntos = _con_distancia(ms, carrera)
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


def ventanas(ms, carrera=None) -> dict[int, tuple]:
    """Mejor ventana de cada distancia dentro de una carrera."""
    puntos = _sin_saltos(_con_distancia(ms, carrera))
    return {m: v for m in DISTANCIAS
            if (v := mejor_ventana(puntos, m)) is not None}
