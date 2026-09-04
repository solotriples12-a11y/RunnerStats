"""Importador de ficheros .fit del Amazfit.

Es la fuente de fidelidad completa: muestreo a 1 Hz con GPS, altitud,
frecuencia cardíaca, cadencia, velocidad y distancia acumulada. Ver
DECISIONS.md 2026-09-04 para la comparativa contra el resto de fuentes.
"""

import sqlite3
import time
from datetime import timezone

from fitparse import FitFile

from ..modelo import Carrera, Muestreo

FUENTE = "amazfit_fit"

# El FIT guarda las coordenadas en semicírculos: 2^31 semicírculos = 180°.
SEMICIRCULOS = 180.0 / (2 ** 31)


class FitInvalido(ValueError):
    pass


def _unix(dt) -> int:
    """Los timestamps del FIT son UTC; fitparse los devuelve sin tzinfo."""
    return int(dt.replace(tzinfo=timezone.utc).timestamp())


def _grados(semicirculos):
    return None if semicirculos is None else semicirculos * SEMICIRCULOS


def _cadencia_spm(rpm):
    """`record.cadence` viene por pierna; los pasos por minuto son el doble.

    Ojo: `lap.avg_cadence` YA viene en pasos por minuto y no hay que
    doblarlo. Verificado con `total_strides` (9302 / 3602 s x 60 = 155).
    """
    return None if rpm is None else rpm * 2


def leer(origen) -> tuple[Carrera, list[Muestreo]]:
    fit = FitFile(origen)
    mensajes = list(fit.get_messages())

    sesiones = [m for m in mensajes if m.name == "session"]
    if not sesiones:
        raise FitInvalido("el fichero no tiene mensaje 'session'")
    s = {c.name: c.value for c in sesiones[0]}

    if s.get("sport") != "running":
        raise FitInvalido(f"no es una carrera (sport={s.get('sport')})")

    inicio = _unix(s["start_time"])

    dispositivo = None
    for nombre in ("device_info", "file_id"):
        for m in mensajes:
            if m.name == nombre:
                d = {c.name: c.value for c in m}
                dispositivo = dispositivo or d.get("product_name")

    carrera = Carrera(
        id=f"{FUENTE}:{inicio}",
        fecha_inicio_unix=inicio,
        distancia_metros=s["total_distance"],
        duracion_segundos=int(s.get("total_elapsed_time") or 0),
        fuente=FUENTE,
        fc_media=s.get("avg_heart_rate"),
        fc_maxima=s.get("max_heart_rate"),
        desnivel_positivo_metros=s.get("total_ascent"),
        desnivel_negativo_metros=s.get("total_descent"),
        calorias=s.get("total_calories"),
        dispositivo=dispositivo,
    )

    muestreos = []
    for m in mensajes:
        if m.name != "record":
            continue
        r = {c.name: c.value for c in m}
        if r.get("timestamp") is None:
            continue
        muestreos.append(Muestreo(
            timestamp_unix=_unix(r["timestamp"]),
            distancia_acumulada_metros=r.get("distance"),
            frecuencia_cardiaca=r.get("heart_rate"),
            cadencia_spm=_cadencia_spm(r.get("cadence")),
            velocidad_ms=r.get("enhanced_speed", r.get("speed")),
            altitud_metros=r.get("enhanced_altitude", r.get("altitude")),
            latitud=_grados(r.get("position_lat")),
            longitud=_grados(r.get("position_long")),
        ))

    return carrera, muestreos


def importar(conn: sqlite3.Connection, origen) -> int:
    """Importa una carrera con sus muestreos. Devuelve 1.

    Idempotente: el id sale del instante de inicio, así que reimportar el
    mismo fichero reemplaza la carrera y sus muestreos en lugar de duplicar.
    """
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
    # Reemplazo limpio: si el fichero se reimporta con menos puntos, no deben
    # quedar muestreos huérfanos de la importación anterior.
    conn.execute("DELETE FROM muestreo WHERE carrera_id = ?", (carrera.id,))
    conn.executemany(
        """
        INSERT INTO muestreo
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
