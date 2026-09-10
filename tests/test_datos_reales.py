"""Tests contra el export real de My Run Stats.

Verifican sobre datos de verdad las afirmaciones en las que se apoyan las
decisiones de DECISIONS.md (2026-09-04). Se saltan si el export no está en
data/, que es lo normal en un clon limpio: son datos de salud y no se
versionan.
"""

import json
from datetime import datetime, timezone

from runnerstats import db
from runnerstats.importers import my_run_stats as mrs


def test_el_export_tiene_207_carreras(export_real):
    assert len(mrs.leer(export_real)) == 207


def test_cubre_quince_anios(export_real):
    fechas = sorted(
        datetime.fromtimestamp(c.fecha_inicio_unix, timezone.utc).date()
        for c in mrs.leer(export_real)
    )
    assert str(fechas[0]) == "2011-12-26"
    assert str(fechas[-1]) == "2026-05-04"


def test_ids_unicos(export_real):
    carreras = mrs.leer(export_real)
    assert len({c.id for c in carreras}) == len(carreras)


def test_el_pace_del_json_es_redundante(export_real):
    """Justifica no almacenar el ritmo: se deriva sin pérdida.

    El `pace` del JSON coincide con duración/distancia en las 207 carreras,
    así que guardarlo sería duplicar un dato derivable.
    """
    crudo = json.loads(export_real.read_text())["runs"]
    carreras = {c.id.split(":", 1)[1]: c for c in mrs.leer(export_real)}

    for r in crudo:
        derivado = carreras[r["id"]].ritmo_seg_por_km
        assert abs(derivado - mrs.a_segundos(r["pace"])) <= 3, r["date"]


def test_los_km_splits_producirian_records_falsos(export_real):
    """Justifica descartar km_splits (DECISIONS.md, trampa 2).

    El último split de cada carrera es la fracción sobrante y su `time` es
    tiempo bruto, no ritmo. Coger el split más rápido sin filtrar da un
    "mejor kilómetro" que en realidad es medio kilómetro.
    """
    crudo = json.loads(export_real.read_text())["runs"]

    ingenuo, real = [], []
    for r in crudo:
        splits = r.get("km_splits") or []
        for i, s in enumerate(splits):
            t = mrs.a_segundos(s["time"])
            ingenuo.append(t)
            fraccion_final = r["distance"] - (len(splits) - 1)
            es_parcial = i == len(splits) - 1 and fraccion_final < 0.95
            if not es_parcial:
                real.append(t)

    assert min(ingenuo) == 181  # 3:01, pero son 580 m
    assert min(real) == 245     # 4:05, el mejor kilómetro de verdad
    # 64 s/km de diferencia: el error que se evita descartándolos.
    assert min(real) - min(ingenuo) == 64


def test_importa_las_207_a_sqlite(tmp_path, export_real):
    conn = db.conectar(tmp_path / "real.db")
    assert len(mrs.importar(conn, export_real)) == 207

    fila = conn.execute(
        "SELECT COUNT(*) n, SUM(distancia_metros) d, SUM(duracion_segundos) t"
        " FROM carrera"
    ).fetchone()
    assert fila["n"] == 207
    assert round(fila["d"] / 1000, 1) == 1098.8   # km totales
    assert round(fila["t"] / 3600, 1) == 112.3    # horas totales
