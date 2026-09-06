"""Tests del importador de Huawei Health.

Los que van contra las muestras reales se saltan si no están en `data/`. El
resto usan un fichero sintético con la forma exacta del export, trampas
incluidas: claves sin comillas y el detalle dentro de `attribute`.
"""

import json

import pytest

from runnerstats import db, detalle
from runnerstats.importers import huawei_json as hw


@pytest.fixture
def conn(tmp_path):
    return db.conectar(tmp_path / "h.db")


def test_solo_entran_las_carreras(huawei_sintetico):
    """El paseo (sportType 5) no es una carrera y no tiene que colarse."""
    carreras = hw.leer(huawei_sintetico)
    assert len(carreras) == 2
    assert {c.distancia_metros for c, _ in carreras} == {5000.0, 4000.0}


def test_lee_el_detalle_de_dentro_de_attribute(huawei_sintetico):
    """El resumen va en campos normales pero las series van en un texto."""
    (car, ms), (cinta, ms_cinta) = hw.leer(huawei_sintetico)

    assert car.duracion_segundos == 1800
    assert car.fc_media == 152 and car.fc_maxima == 155      # 150..155
    assert car.calorias == 300
    assert car.dispositivo == "Huawei Health"

    # La carrera de fuera trae GPS; la de cinta, no.
    assert any(m.latitud for m in ms)
    assert not any(m.latitud for m in ms_cinta)
    # Y las dos traen pulso, cadencia y altitud.
    for muestreos in (ms, ms_cinta):
        assert any(m.frecuencia_cardiaca for m in muestreos)
        assert any(m.cadencia_spm for m in muestreos)
        assert any(m.altitud_metros for m in muestreos)


def test_las_claves_sin_comillas_no_lo_rompen(huawei_sintetico):
    """`partTimeMap` viene como {1.0:380.0}: eso no es JSON valido."""
    with pytest.raises(json.JSONDecodeError):
        json.loads(huawei_sintetico.read_text())
    assert hw.leer(huawei_sintetico)          # el importador si lo lee


def test_un_export_de_my_run_stats_no_cuela(tmp_path):
    """Comparten extension, asi que la web los distingue por la forma."""
    ajeno = tmp_path / "export.json"
    ajeno.write_text('{"app": "My Run Stats", "runs": []}')
    assert not hw.parece_huawei(ajeno.read_text())
    with pytest.raises(hw.HuaweiInvalido):
        hw.leer(ajeno)


def test_un_fichero_vacio_no_es_un_error(tmp_path):
    """Tres de los 24 ficheros del export vienen con una lista vacia."""
    vacio = tmp_path / "vacio.json"
    vacio.write_text("[]")
    assert hw.leer(vacio) == []


def test_importar_es_idempotente(conn, huawei_sintetico):
    """Cada actividad viene repetida en tres ficheros del export."""
    assert hw.importar(conn, huawei_sintetico) == 2
    hw.importar(conn, huawei_sintetico)
    assert conn.execute("SELECT COUNT(*) FROM carrera").fetchone()[0] == 2
    # Y los muestreos no se duplican al reimportar.
    n = conn.execute("SELECT COUNT(*) FROM muestreo").fetchone()[0]
    hw.importar(conn, huawei_sintetico)
    assert conn.execute("SELECT COUNT(*) FROM muestreo").fetchone()[0] == n


def test_muestra_real(conn, huawei_dir):
    """Contra el export de verdad: 4 carreras al aire libre y 3 de cinta."""
    n = hw.importar(conn, huawei_dir / "carreras-y-cinta.json")
    assert n == 7

    con_gps = conn.execute(
        "SELECT COUNT(DISTINCT carrera_id) FROM muestreo WHERE latitud IS NOT NULL"
    ).fetchone()[0]
    con_fc = conn.execute(
        "SELECT COUNT(DISTINCT carrera_id) FROM muestreo"
        " WHERE frecuencia_cardiaca IS NOT NULL").fetchone()[0]
    assert con_gps == 4 and con_fc == 7      # la cinta tambien trae pulso

    for c in conn.execute("SELECT * FROM carrera"):
        assert 120 < c["fc_media"] < 200, c["id"]
        assert c["fc_maxima"] >= c["fc_media"]
        # Ritmo humano: entre 3 y 12 minutos el kilometro.
        ritmo = c["duracion_segundos"] / (c["distancia_metros"] / 1000)
        assert 180 < ritmo < 720, f"{c['id']}: {ritmo:.0f} s/km"


def test_el_fichero_vacio_real_tampoco_revienta(conn, huawei_dir):
    assert hw.importar(conn, huawei_dir / "vacio.json") == 0


def test_los_parciales_reales_cuadran_con_los_del_reloj(conn, huawei_dir):
    """Huawei trae sus propios tiempos por kilometro en `partTimeMap`, que no
    se importan: sirven de contraste independiente para los que calculamos
    nosotros desde el GPS.

    Se comparan solo las carreras sin tiempo parado, porque nuestros parciales
    lo descuentan a proposito y los del reloj no.
    """
    import re
    crudo = (huawei_dir / "carreras-y-cinta.json").read_text()
    oficial = {
        a["startTime"] // 1000: {int(float(k)): v for k, v in a["partTimeMap"].items()}
        for a in json.loads(re.sub(r'([{,])\s*(-?\d+(?:\.\d+)?)\s*:', r'\1"\2":', crudo))
        if a["sportType"] in hw.DEPORTES and a.get("partTimeMap")
    }
    hw.importar(conn, huawei_dir / "carreras-y-cinta.json")

    comparadas = 0
    for car in conn.execute("SELECT * FROM carrera"):
        ref = oficial.get(car["fecha_inicio_unix"])
        ms = detalle.muestreos(conn, car["id"])
        parciales = [s for s in detalle.splits(ms, car) if not s["parcial"]]
        if not ref or not parciales:
            continue
        puntos = detalle._con_distancia(ms, car)
        movimiento = detalle.en_movimiento(puntos)
        parado = (puntos[-1][0] - puntos[0][0]) - movimiento[-1][0]
        if parado >= 30:
            continue

        comparadas += 1
        acumulado = 0
        for s in parciales:
            acumulado += s["segundos"]
            if s["km"] in ref:
                assert abs(acumulado - ref[s["km"]]) < 45, (
                    f"{car['id']} km {s['km']}: {acumulado:.0f} s contra "
                    f"{ref[s['km']]:.0f} s del reloj")
    assert comparadas, "ninguna carrera sin pausas que comparar"
