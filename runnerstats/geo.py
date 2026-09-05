"""Distancia a partir del GPS.

Validado contra dos ficheros con distancia declarada: 0,32 % de error en un
TCX de Nike y 0,49 % en uno de Huawei. Los dos relojes discrepan entre sí un
1,2 % sobre la misma carrera, así que el valor derivado cae dentro del ruido
que ya hay entre dispositivos.
"""

import math

RADIO_TIERRA = 6371008.8

# Un salto mayor que esto entre dos muestras consecutivas es error de GPS,
# no carrera: 12 m/s son 43 km/h.
VELOCIDAD_ABSURDA = 12.0


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * RADIO_TIERRA * math.asin(math.sqrt(h))


def acumular(puntos: list[tuple[int, float | None, float | None]]) -> dict[int, float]:
    """(timestamp, lat, lon) ordenados -> distancia acumulada por timestamp.

    Los puntos sin coordenadas no rompen la serie: se saltan y el siguiente
    con GPS mide contra el último válido.
    """
    salida: dict[int, float] = {}
    acumulado = 0.0
    anterior = None
    for ts, lat, lon in puntos:
        if lat is None or lon is None:
            continue
        if anterior is not None:
            t0, la0, lo0 = anterior
            d = haversine(la0, lo0, lat, lon)
            if d <= VELOCIDAD_ABSURDA * max(ts - t0, 1):
                acumulado += d
        salida[ts] = acumulado
        anterior = (ts, lat, lon)
    return salida
