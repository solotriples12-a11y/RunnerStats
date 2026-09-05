"""Tests de la deduplicacion entre fuentes."""

import json

from runnerstats import analisis, consultas, db, dedup
from runnerstats.importers import my_run_stats as mrs, nike_tcx as nike


def _mrs_con(tmp_path, fecha, km, dur="00:20:00"):
    f = tmp_path / f"mrs-{fecha}-{km}.json"
    f.write_text(json.dumps({
        "app": "My Run Stats", "version": 1, "count": 1,
        "runs": [{"id": f"x{km}", "date": fecha, "duration": dur,
                  "distance": km, "pace": "5:00", "km_splits": None}]}))
    return f


def test_gana_la_que_tiene_muestreos(tmp_path, nike_dir):
    conn = db.conectar(tmp_path / "d.db")
    c, _ = nike.leer(str(nike_dir / "con-fc-y-gps.tcx"))
    nike.importar(conn, str(nike_dir / "con-fc-y-gps.tcx"))

    from datetime import datetime, timezone
    dia = datetime.fromtimestamp(c.fecha_inicio_unix, timezone.utc).date().isoformat()
    mrs.importar(conn, _mrs_con(tmp_path, dia, round(c.distancia_metros / 1000, 2)))

    fus = dedup.marcar_duplicadas(conn)
    assert len(fus) == 1
    assert fus[0]["gana"] == "nike_tcx" and fus[0]["pierde"] == "my_run_stats"

    # No se borra nada: la perdedora sigue en la tabla, solo marcada.
    assert conn.execute("SELECT COUNT(*) FROM carrera").fetchone()[0] == 2
    assert len(consultas.listar_carreras(conn)) == 1
    assert analisis.resumen(conn)["carreras"] == 1


def test_fuera_de_tolerancia_no_se_fusiona(tmp_path):
    conn = db.conectar(tmp_path / "d.db")
    mrs.importar(conn, _mrs_con(tmp_path, "2020-05-05", 5.00))
    mrs.importar(conn, _mrs_con(tmp_path, "2020-05-05", 5.80))   # 16 %
    assert dedup.marcar_duplicadas(conn, tolerancia=0.05) == []
    assert analisis.resumen(conn)["carreras"] == 2


def test_dentro_de_tolerancia_si(tmp_path):
    conn = db.conectar(tmp_path / "d.db")
    mrs.importar(conn, _mrs_con(tmp_path, "2020-05-05", 5.00))
    mrs.importar(conn, _mrs_con(tmp_path, "2020-05-05", 5.20))   # 4 %
    assert len(dedup.marcar_duplicadas(conn, tolerancia=0.05)) == 1
    assert analisis.resumen(conn)["carreras"] == 1


def test_dias_distintos_nunca_se_fusionan(tmp_path):
    conn = db.conectar(tmp_path / "d.db")
    mrs.importar(conn, _mrs_con(tmp_path, "2020-05-05", 5.00))
    mrs.importar(conn, _mrs_con(tmp_path, "2020-05-06", 5.00))
    assert dedup.marcar_duplicadas(conn) == []


def test_es_idempotente_y_recalcula_desde_cero(tmp_path):
    conn = db.conectar(tmp_path / "d.db")
    mrs.importar(conn, _mrs_con(tmp_path, "2020-05-05", 5.00))
    mrs.importar(conn, _mrs_con(tmp_path, "2020-05-05", 5.10))
    assert len(dedup.marcar_duplicadas(conn)) == 1
    assert len(dedup.marcar_duplicadas(conn)) == 1
    assert analisis.resumen(conn)["carreras"] == 1
