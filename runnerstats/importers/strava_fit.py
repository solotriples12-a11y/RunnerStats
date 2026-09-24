"""Importador de los .fit que exporta Strava.

Visto en dos carreras de cinta del 2026-09-21 y 23 ("Correr en interiores"),
exportadas a la vez. El fichero no se parece al del Amazfit:

- `file_id` firma como fabricante `development`, sin producto ni
  dispositivo, y no hay `device_info` ni vueltas.
- Los `record` vienen en dos tandas del mismo tamaño. La primera trae solo
  velocidad, con todas las marcas de tiempo en el instante de inicio. La
  segunda trae cadencia y pulso cada 5 s, con la velocidad a 64,536, que es
  un valor de relleno.
- Ningún `record` trae distancia, y la sesión no trae `max_heart_rate` ni
  `total_timer_time`.

La velocidad se empareja por posición con la segunda tanda, que es la que
tiene hora. Integrada da 5.111 y 5.098 m contra los 5.000 de la sesión, un
+2 % parecido al +1,6 % de la cinta de Huawei. Como allí, se guarda la
velocidad cruda y no se deriva una serie de distancia (DECISIONS.md,
2026-09-06): la carrera no tiene parciales ni récords, pero sí pulso.
"""

import sqlite3
import time

from fitparse import FitFile

from ..modelo import Carrera, Muestreo
from .amazfit_fit import FitInvalido, _cadencia_spm, _unix

FUENTE = "strava_fit"

# Velocidad de relleno en los `record` que sí tienen hora.
VELOCIDAD_RELLENO = 64.536


def parece_strava(contenido: bytes) -> bool:
    """El .fit de Strava firma como `development`; el del Amazfit, no."""
    for m in FitFile(contenido).get_messages("file_id"):
        return m.get_value("manufacturer") == "development"
    return False


def leer(origen) -> tuple[Carrera, list[Muestreo]]:
    mensajes = list(FitFile(origen).get_messages())

    sesiones = [m for m in mensajes if m.name == "session"]
    if not sesiones:
        raise FitInvalido("el fichero no tiene mensaje 'session'")
    s = {c.name: c.value for c in sesiones[0]}
    if s.get("sport") != "running":
        raise FitInvalido(f"no es una carrera (sport={s.get('sport')})")

    registros = [{c.name: c.value for c in m}
                 for m in mensajes if m.name == "record"]
    con_hora = [r for r in registros if r.get("speed") == VELOCIDAD_RELLENO]
    velocidades = [r.get("speed") for r in registros
                   if r.get("speed") != VELOCIDAD_RELLENO]
    # Si las dos tandas no casan, emparejar por posición sería inventar.
    if len(velocidades) != len(con_hora):
        velocidades = [None] * len(con_hora)

    muestreos = [Muestreo(
        timestamp_unix=_unix(r["timestamp"]),
        frecuencia_cardiaca=r.get("heart_rate"),
        cadencia_spm=_cadencia_spm(r.get("cadence")),
        velocidad_ms=v,
    ) for r, v in zip(con_hora, velocidades)]

    pulsos = [m.frecuencia_cardiaca for m in muestreos if m.frecuencia_cardiaca]
    inicio = _unix(s["start_time"])
    carrera = Carrera(
        id=f"{FUENTE}:{inicio}",
        fecha_inicio_unix=inicio,
        distancia_metros=s["total_distance"],
        duracion_segundos=int(s.get("total_timer_time")
                              or s.get("total_elapsed_time") or 0),
        fuente=FUENTE,
        fc_media=s.get("avg_heart_rate"),
        # La sesión no la trae; sale de los mismos pulsos que se guardan.
        fc_maxima=s.get("max_heart_rate") or (max(pulsos) if pulsos else None),
        calorias=s.get("total_calories"),
    )
    return carrera, muestreos


def importar(conn: sqlite3.Connection, origen) -> list[Carrera]:
    """Idempotente, como el del Amazfit: el id sale del instante de inicio."""
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
        INSERT INTO muestreo
            (carrera_id, timestamp_unix, frecuencia_cardiaca, cadencia_spm,
             velocidad_ms)
        VALUES (?,?,?,?,?)
        """,
        [(carrera.id, m.timestamp_unix, m.frecuencia_cardiaca,
          m.cadencia_spm, m.velocidad_ms) for m in muestreos],
    )
    conn.commit()
    return [carrera]
