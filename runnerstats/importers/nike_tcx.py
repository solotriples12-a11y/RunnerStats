"""Importador de los TCX del export de Nike Run Club.

Fidelidad variable: de las 269 carreras del export analizado, 202 traen
distancia por punto, 158 GPS, 99 cadencia y 98 frecuencia cardíaca. Las
primeras (2011-2012) son solo resumen. Ver DECISIONS.md 2026-09-05.

Trampa de unidades: la cadencia de Nike **ya viene en pasos por minuto**
(media 153,9 en el corpus). En el `.fit` del Amazfit los `record` vienen por
pierna y hay que doblarlos. Misma etiqueta, convención distinta.
"""

import sqlite3
import time
from dataclasses import replace
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from .. import geo
from ..modelo import Carrera, Muestreo

FUENTE = "nike_tcx"

T = "{http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2}"
AX = "{http://www.garmin.com/xmlschemas/ActivityExtension/v2}"
NAX = "{https://www.nike.com/xmlschemas/NikeActivityExtension/v1}"


class TcxInvalido(ValueError):
    pass


def _txt(padre, camino):
    """Texto de un hijo. Nike mete los valores en lineas aparte con espacios."""
    el = padre.find(camino) if padre is not None else None
    if el is None or el.text is None:
        return None
    v = el.text.strip()
    return v or None


def _num(padre, camino, tipo=float):
    v = _txt(padre, camino)
    if v is None:
        return None
    try:
        return tipo(float(v))
    except ValueError:
        return None


def _positivo(v):
    """Nike escribe 0 cuando no hubo sensor. Un 0 de pulso no es un dato."""
    return v if v else None


def _unix(iso: str) -> int:
    return int(datetime.fromisoformat(iso.strip().replace("Z", "+00:00"))
               .astimezone(timezone.utc).timestamp())


def leer(origen) -> tuple[Carrera, list[Muestreo]]:
    raiz = ET.parse(origen).getroot()

    # Un TCX de Huawei tiene la misma forma y se parsearia igual, quedando
    # mal etiquetado. La extension `nax` solo la escribe Nike, y su
    # ActivityType vive a nivel de actividad, asi que se encuentra pronto.
    if raiz.find(f".//{NAX}ActivityType") is None:
        raise TcxInvalido("no parece un TCX de Nike (falta la extension nax)")

    lap = raiz.find(f"{T}Activities/{T}Activity/{T}Lap")
    if lap is None:
        raise TcxInvalido("el TCX no tiene ningun Lap")

    inicio_iso = lap.get("StartTime") or _txt(
        raiz, f"{T}Activities/{T}Activity/{T}Id")
    if not inicio_iso:
        raise TcxInvalido("el TCX no tiene instante de inicio")
    inicio = _unix(inicio_iso)

    ext = lap.find(f"{T}Extensions")
    carrera = Carrera(
        id=f"{FUENTE}:{inicio}",
        fecha_inicio_unix=inicio,
        distancia_metros=_num(lap, f"{T}DistanceMeters") or 0.0,
        duracion_segundos=_num(lap, f"{T}TotalTimeSeconds", int) or 0,
        fuente=FUENTE,
        fc_media=_positivo(_num(lap, f"{T}AverageHeartRateBpm/{T}Value", int)),
        fc_maxima=_positivo(_num(lap, f"{T}MaximumHeartRateBpm/{T}Value", int)),
        desnivel_positivo_metros=_num(ext, f".//{NAX}AscentInMeters"),
        desnivel_negativo_metros=_num(ext, f".//{NAX}DescentInMeters"),
        calorias=_num(lap, f"{T}Calories", int),
        dispositivo="Nike Run Club",
    )

    # Nike escribe un trackpoint por sensor, no un punto completo por
    # instante: uno lleva solo el pulso, el siguiente solo la posicion. Y con
    # marca de milisegundos, asi que el 41 % cae dentro de un segundo que ya
    # tiene otro punto. Como la clave es (carrera, segundo), sin fusionar se
    # perderian en silencio. Al unirlos se dobla ademas la densidad de campos.
    por_segundo: dict[int, dict] = {}
    for tp in lap.iterfind(f"{T}Track/{T}Trackpoint"):
        t = _txt(tp, f"{T}Time")
        if t is None:
            continue
        pos = tp.find(f"{T}Position")
        campos = {
            "distancia_acumulada_metros": _num(tp, f"{T}DistanceMeters"),
            "frecuencia_cardiaca": _positivo(
                _num(tp, f"{T}HeartRateBpm/{T}Value", int)),
            # Sin doblar: Nike ya da pasos por minuto.
            "cadencia_spm": _positivo(_num(tp, f"{T}Cadence", int)),
            "velocidad_ms": _num(tp, f".//{AX}Speed"),
            "altitud_metros": _num(tp, f"{T}AltitudeMeters"),
            "latitud": _num(pos, f"{T}LatitudeDegrees") if pos is not None else None,
            "longitud": _num(pos, f"{T}LongitudeDegrees") if pos is not None else None,
        }
        acumulado = por_segundo.setdefault(_unix(t), {})
        for k, v in campos.items():
            if v is not None and acumulado.get(k) is None:
                acumulado[k] = v

    muestreos = [Muestreo(timestamp_unix=seg, **campos)
                 for seg, campos in sorted(por_segundo.items())]

    # Nike a veces guarda la traza pero no la distancia (visto en 1 de 269:
    # 465 puntos, 321 con GPS y DistanceMeters a 0). Se deriva del GPS en vez
    # de tirar una carrera real.
    if carrera.distancia_metros <= 0:
        acum = geo.acumular([(m.timestamp_unix, m.latitud, m.longitud)
                             for m in muestreos])
        if not acum:
            raise TcxInvalido("sin distancia declarada y sin GPS del que derivarla")
        muestreos = [
            m if m.distancia_acumulada_metros is not None or m.timestamp_unix not in acum
            else replace(m, distancia_acumulada_metros=acum[m.timestamp_unix])
            for m in muestreos
        ]
        carrera = replace(carrera, distancia_metros=max(acum.values()))

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
