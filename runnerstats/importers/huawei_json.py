"""Importador del export de privacidad de Huawei Health.

De todo el export solo sirve `Motion path detail data`: una lista de
actividades donde el resumen va en campos normales, pero el detalle segundo a
segundo se esconde dentro de `attribute`, en un formato propio de líneas

    tp=<tipo>;k=<clave>;v=<valor>;

con un tipo por serie: `h-r` frecuencia cardíaca, `alti` altitud, `s-r`
cadencia, `rs` velocidad y `lbs` los puntos de GPS, que además llevan su
propio `lat`, `lon` y `t`.

Dos trampas del formato, las dos comprobadas sobre el export real:

- **No es JSON válido.** `partTimeMap` trae las claves numéricas sin comillas
  (`{1.0:380.0}`), así que hay que entrecomillarlas antes de parsear.
- **Cada actividad viene repetida.** Las 104 del export salen tres veces
  repartidas entre los 24 ficheros. Como el id sale del instante de inicio,
  el `INSERT OR REPLACE` las colapsa solo.
"""

import json
import pathlib
import re
import sqlite3
import time

from ..modelo import Carrera, Muestreo

FUENTE = "huawei_json"

# sportType. No hay documentación en el export, así que se identifican por sus
# propios datos: el 4 son 26 actividades de 5,1 km de mediana a 6:25/km y con
# GPS, y el 101 otras 11 de 5,0 km a 6:23/km sin GPS, o sea la cinta. Que el
# 4 es correr lo confirma que diez de esas fechas y distancias ya estaban en
# el histórico propio. El 5 y el 102 van a 20:00/km: son paseos.
AIRE_LIBRE, CINTA = 4, 101
DEPORTES = (AIRE_LIBRE, CINTA)

_CLAVE_SUELTA = re.compile(r'([{,])\s*(-?\d+(?:\.\d+)?)\s*:')
_MUESTRA = re.compile(r"tp=([a-z0-9\-]+);k=(-?\d+);v=(-?[\d.]+);")
_PUNTO_GPS = re.compile(
    r"tp=lbs;k=-?\d+;lat=(-?[\d.]+);lon=(-?[\d.]+);alt=(-?[\d.eE+]+);t=([\d.eE+]+);")


class HuaweiInvalido(ValueError):
    """El fichero no es un 'Motion path detail data' de Huawei Health."""


def _texto(origen) -> str:
    if isinstance(origen, (bytes, bytearray)):
        return origen.decode("utf-8")
    if hasattr(origen, "read"):
        datos = origen.read()
        return datos.decode("utf-8") if isinstance(datos, bytes) else datos
    return pathlib.Path(origen).read_text()


def parece_huawei(texto: str) -> bool:
    """El export de My Run Stats es un objeto y el de Huawei una lista.

    Comparten extensión, así que la web tiene que distinguirlos por dentro.
    """
    return texto.lstrip()[:1] == "["


def _series(attribute: str) -> dict[str, list[tuple[int, float]]]:
    """Las series `tp=...` agrupadas por tipo, con la clave tal cual viene."""
    series: dict[str, list[tuple[int, float]]] = {}
    for tipo, k, v in _MUESTRA.findall(attribute):
        series.setdefault(tipo, []).append((int(k), float(v)))
    return series


def _gps(attribute: str) -> list[tuple[int, float, float]]:
    """(instante, latitud, longitud) de cada punto, uno por segundo.

    La altitud de los puntos de GPS viene siempre a 0: la buena está en la
    serie `alti`, así que aquí se ignora.
    """
    puntos = []
    for lat, lon, _alt, t in _PUNTO_GPS.findall(attribute):
        lat, lon = float(lat), float(lon)
        if lat or lon:          # (0,0) es "sin cobertura", no el golfo de Guinea
            puntos.append((round(float(t)), lat, lon))
    return puntos


def _muestreos(actividad: dict) -> list[Muestreo]:
    """Un muestreo por segundo con datos, fusionando todas las series.

    El GPS va a 1 Hz y el resto a 0,2 Hz, así que la mayoría de segundos solo
    traen posición. Se fusiona por instante en vez de rellenar: un hueco es un
    hueco, y las gráficas ya los interpolan.
    """
    attribute = actividad.get("attribute") or ""
    series = _series(attribute)
    campos = {}

    for instante, lat, lon in _gps(attribute):
        campos.setdefault(instante, {}).update(latitud=lat, longitud=lon)

    # `k` en milisegundos para estas tres; `v` a 0 o negativo es sensor mudo.
    for tipo, campo, minimo in (("h-r", "frecuencia_cardiaca", 1),
                                ("s-r", "cadencia_spm", 1),
                                ("alti", "altitud_metros", None)):
        for k, v in series.get(tipo, []):
            if minimo is not None and v < minimo:
                continue
            campos.setdefault(k // 1000, {})[campo] = (
                int(v) if campo != "altitud_metros" else v)

    # La velocidad va en decimetros por segundo y su `k` son segundos desde el
    # inicio, no un instante. Integrarla reproduce la distancia declarada con
    # un 1,6 % de exceso, asi que sirve de contraste pero no de serie.
    inicio = actividad["startTime"] // 1000
    for k, v in series.get("rs", []):
        if v > 0:
            campos.setdefault(inicio + k, {})["velocidad_ms"] = v / 10

    return [Muestreo(timestamp_unix=t, **campos[t]) for t in sorted(campos)]


def _carrera(actividad: dict, muestreos: list[Muestreo]) -> Carrera:
    inicio = actividad["startTime"] // 1000
    pulsos = [m.frecuencia_cardiaca for m in muestreos if m.frecuencia_cardiaca]
    return Carrera(
        id=f"{FUENTE}:{inicio}",
        fecha_inicio_unix=inicio,
        distancia_metros=float(actividad["totalDistance"]),
        duracion_segundos=actividad["totalTime"] // 1000,
        fuente=FUENTE,
        # Huawei no da media ni maxima en el resumen: salen de la serie.
        fc_media=round(sum(pulsos) / len(pulsos)) if pulsos else None,
        fc_maxima=max(pulsos) if pulsos else None,
        calorias=(actividad.get("totalCalories") or 0) // 1000 or None,
        dispositivo="Huawei Health",
    )


def leer(origen) -> list[tuple[Carrera, list[Muestreo]]]:
    """Las carreras de un fichero. Los paseos y el gimnasio se descartan."""
    texto = _texto(origen)
    if not parece_huawei(texto):
        return _falla("no parece un 'Motion path detail data' de Huawei")
    try:
        actividades = json.loads(_CLAVE_SUELTA.sub(r'\1"\2":', texto))
    except json.JSONDecodeError as e:
        return _falla(f"JSON invalido ({e})")
    if not isinstance(actividades, list):
        return _falla("se esperaba una lista de actividades")

    salida = []
    for a in actividades:
        if not isinstance(a, dict) or "sportType" not in a:
            return _falla("a las actividades les falta sportType")
        if a["sportType"] not in DEPORTES:
            continue
        if not a.get("totalDistance") or not a.get("totalTime"):
            continue      # actividad sin resumen: no da ni ritmo ni distancia
        muestreos = _muestreos(a)
        salida.append((_carrera(a, muestreos), muestreos))
    return salida


def _falla(motivo: str):
    raise HuaweiInvalido(motivo)


def importar(conn: sqlite3.Connection, origen) -> int:
    carreras = leer(origen)
    ahora = int(time.time())

    for carrera, muestreos in carreras:
        conn.execute(
            """
            INSERT OR REPLACE INTO carrera
                (id, fecha_inicio_unix, distancia_metros, duracion_segundos,
                 fuente, fc_media, fc_maxima, desnivel_positivo_metros,
                 desnivel_negativo_metros, calorias, dispositivo, importado_en)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (carrera.id, carrera.fecha_inicio_unix, carrera.distancia_metros,
             carrera.duracion_segundos, carrera.fuente, carrera.fc_media,
             carrera.fc_maxima, carrera.desnivel_positivo_metros,
             carrera.desnivel_negativo_metros, carrera.calorias,
             carrera.dispositivo, ahora),
        )
        conn.execute("DELETE FROM muestreo WHERE carrera_id = ?", (carrera.id,))
        conn.executemany(
            """
            INSERT OR REPLACE INTO muestreo
                (carrera_id, timestamp_unix, distancia_acumulada_metros,
                 frecuencia_cardiaca, cadencia_spm, velocidad_ms,
                 altitud_metros, latitud, longitud)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            [(carrera.id, m.timestamp_unix, m.distancia_acumulada_metros,
              m.frecuencia_cardiaca, m.cadencia_spm, m.velocidad_ms,
              m.altitud_metros, m.latitud, m.longitud) for m in muestreos],
        )
    conn.commit()
    return len(carreras)
