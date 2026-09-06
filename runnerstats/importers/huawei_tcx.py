"""Importador del TCX que exporta la app de Huawei Health, carrera a carrera.

Es la otra mitad de Huawei. El export de privacidad
(`huawei_json`) trae las carreras normales con GPS, pulso y cadencia, pero
**deja fuera las "carreras de prueba"**: seis actividades que su resumen
diario sí cuenta y que no aparecen en `Motion path detail data`. De esas, la
app sí deja exportar un TCX, y ese TCX trae el recorrido.

Lo que hay dentro es poco pero es justo lo que falta: posición y altitud por
segundo, y el desnivel acumulado del resumen. **No trae pulso, ni cadencia,
ni distancia por punto** —solo el total del Lap—, así que la distancia se
deriva del GPS como en los demás casos, y el pulso lo pone la otra versión de
la carrera al fusionarse.
"""

import sqlite3
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from ..modelo import Carrera, Muestreo

FUENTE = "huawei_tcx"

T = "{http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2}"


class TcxInvalido(ValueError):
    pass


def parece_huawei(contenido: bytes) -> bool:
    """Huawei firma el fichero como `creator="Health"`; Nike no pone creator."""
    return b'creator="Health"' in contenido[:600]


def _num(padre, camino):
    el = padre.find(camino) if padre is not None else None
    if el is None or not (el.text or "").strip():
        return None
    try:
        return float(el.text.strip())
    except ValueError:
        return None


def _unix(iso: str) -> int:
    return int(datetime.fromisoformat(
        iso.replace("Z", "+00:00")).astimezone(timezone.utc).timestamp())


def leer(origen) -> tuple[Carrera, list[Muestreo]]:
    arbol = ET.parse(origen) if not isinstance(origen, (bytes, bytearray)) \
        else ET.ElementTree(ET.fromstring(origen))
    raiz = arbol.getroot()
    if raiz.get("creator") != "Health":
        raise TcxInvalido("no parece un TCX de Huawei Health")

    lap = raiz.find(f"{T}Activities/{T}Activity/{T}Lap")
    if lap is None:
        raise TcxInvalido("el TCX no tiene ningun Lap")
    inicio_iso = lap.get("StartTime")
    if not inicio_iso:
        raise TcxInvalido("el TCX no tiene instante de inicio")

    inicio = _unix(inicio_iso)
    muestreos = []
    for p in lap.iterfind(f"{T}Track/{T}Trackpoint"):
        cuando = (p.find(f"{T}Time").text or "").strip() if p.find(f"{T}Time") is not None else ""
        lat = _num(p, f"{T}Position/{T}LatitudeDegrees")
        lon = _num(p, f"{T}Position/{T}LongitudeDegrees")
        if not cuando or lat is None or lon is None:
            continue
        muestreos.append(Muestreo(
            timestamp_unix=_unix(cuando),
            latitud=lat, longitud=lon,
            altitud_metros=_num(p, f"{T}AltitudeMeters"),
        ))

    distancia = _num(lap, f"{T}DistanceMeters")
    duracion = _num(lap, f"{T}TotalTimeSeconds")
    if not distancia or not duracion:
        raise TcxInvalido("el TCX no declara distancia o duracion")

    carrera = Carrera(
        id=f"{FUENTE}:{inicio}",
        fecha_inicio_unix=inicio,
        distancia_metros=distancia,
        duracion_segundos=int(duracion),
        fuente=FUENTE,
        desnivel_positivo_metros=_num(lap, f"{T}CumulativeClimb"),
        desnivel_negativo_metros=_num(lap, f"{T}CumulativeDecrease"),
        dispositivo="Huawei Health",
    )
    return carrera, muestreos


def importar(conn: sqlite3.Connection, origen) -> int:
    carrera, muestreos = leer(origen)
    ahora = int(time.time())

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
    return 1
