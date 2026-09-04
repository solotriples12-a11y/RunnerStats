"""Importador del export JSON de My Run Stats.

Fuente de fidelidad baja: solo resúmenes, sin muestreos. A cambio es la única
con histórico largo (207 carreras desde 2011).

Dos campos del JSON se descartan a propósito, ver DECISIONS.md 2026-09-04:

- `pace`: redundante, se deriva de duración y distancia. Verificado coherente
  en las 207 carreras del export real.
- `km_splits`: no fiables. Solo los tienen 101 de 207 carreras, su suma nunca
  cuadra con la duración, y el último split de cada carrera es la fracción
  sobrante cuyo `time` es tiempo bruto, no ritmo. Cogerlos sin filtrar da un
  "mejor kilómetro" de 3:01 que en realidad son 580 m.
"""

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from ..modelo import Carrera

FUENTE = "my_run_stats"


def a_segundos(texto: str) -> int:
    """Convierte 'HH:MM:SS' o 'MM:SS' a segundos."""
    partes = [int(p) for p in texto.split(":")]
    if len(partes) == 3:
        h, m, s = partes
        return h * 3600 + m * 60 + s
    m, s = partes
    return m * 60 + s


def _fecha_a_unix(fecha: str) -> int:
    """Medianoche UTC del día indicado.

    My Run Stats solo da la fecha, sin hora. Se guarda a medianoche UTC para
    que la fecha siga siendo correcta al mostrarla en Europe/Madrid, que va
    por delante de UTC.
    """
    dia = datetime.strptime(fecha, "%Y-%m-%d")
    return int(dia.replace(tzinfo=timezone.utc).timestamp())


def leer(origen) -> list[Carrera]:
    """Lee desde una ruta o desde un fichero ya abierto.

    Aceptar streams permite importar lo que sube el navegador sin escribir
    nada en disco, que ademas evita tener que sanear rutas.
    """
    datos = json.load(origen) if hasattr(origen, "read") else json.loads(
        Path(origen).read_text()
    )
    return [
        Carrera(
            id=f"{FUENTE}:{c['id']}",
            fecha_inicio_unix=_fecha_a_unix(c["date"]),
            distancia_metros=c["distance"] * 1000,
            duracion_segundos=a_segundos(c["duration"]),
            fuente=FUENTE,
        )
        for c in datos["runs"]
    ]


def importar(conn: sqlite3.Connection, ruta: str | Path) -> int:
    """Importa el export y devuelve cuántas carreras se han escrito.

    Idempotente: reimportar un export actualizado reemplaza las carreras que
    ya estaban en lugar de duplicarlas.
    """
    carreras = leer(ruta)
    ahora = int(time.time())
    conn.executemany(
        """
        INSERT OR REPLACE INTO carrera
            (id, fecha_inicio_unix, distancia_metros, duracion_segundos,
             fuente, importado_en)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (c.id, c.fecha_inicio_unix, c.distancia_metros,
             c.duracion_segundos, c.fuente, ahora)
            for c in carreras
        ],
    )
    conn.commit()
    return len(carreras)
