"""Tests del TCX que exporta la app de Huawei Health.

Es la mitad que le falta al export de privacidad: las "carreras de prueba" no
están en `Motion path detail data`, y su TCX trae el recorrido que Nike no
guardó.
"""

import pytest

from runnerstats import db, geo
from runnerstats.importers import huawei_tcx as ht


@pytest.fixture
def tcx(huawei_dir):
    ficheros = sorted(huawei_dir.glob("*.tcx"))
    if not ficheros:
        pytest.skip("no hay TCX de Huawei en data/huawei")
    return ficheros


def test_trae_recorrido_y_altitud_pero_no_pulso(tcx):
    """Es exactamente lo contrario que el TCX de Nike de esas carreras."""
    carrera, ms = ht.leer(str(tcx[0]))
    assert carrera.fuente == "huawei_tcx"
    assert carrera.dispositivo == "Huawei Health"
    assert ms and all(m.latitud and m.longitud for m in ms)
    assert all(m.altitud_metros is not None for m in ms)
    assert not any(m.frecuencia_cardiaca for m in ms)
    # El desnivel sí viene, del resumen del Lap.
    assert carrera.desnivel_positivo_metros > 0


def test_la_distancia_declarada_cuadra_con_el_gps(tcx):
    """No hay distancia por punto, solo el total: se deriva del GPS, y para
    eso el GPS tiene que cerrar. Uno de los cinco pierde señal y se queda un
    21 % corto; `_serie_fiable` es quien lo rechaza luego."""
    cuadran = 0
    for f in tcx:
        carrera, ms = ht.leer(str(f))
        acumulada = geo.acumular([(m.timestamp_unix, m.latitud, m.longitud)
                                  for m in ms])
        recorrido = list(acumulada.values())[-1]
        if abs(recorrido - carrera.distancia_metros) <= 0.05 * carrera.distancia_metros:
            cuadran += 1
    assert cuadran >= len(tcx) - 1


def test_no_se_traga_un_tcx_de_nike(nike_dir):
    ajeno = str(nike_dir / "con-fc-y-gps.tcx")
    assert not ht.parece_huawei(open(ajeno, "rb").read())
    with pytest.raises(ht.TcxInvalido):
        ht.leer(ajeno)


def test_se_reconoce_por_el_creator(tcx):
    assert ht.parece_huawei(tcx[0].read_bytes())


def test_importar_es_idempotente(tmp_path, tcx):
    conn = db.conectar(tmp_path / "t.db")
    assert len(ht.importar(conn, str(tcx[0]))) == 1
    n = conn.execute("SELECT COUNT(*) FROM muestreo").fetchone()[0]
    ht.importar(conn, str(tcx[0]))
    assert conn.execute("SELECT COUNT(*) FROM carrera").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM muestreo").fetchone()[0] == n


def test_un_tcx_sin_lap_da_error_claro(tmp_path):
    f = tmp_path / "vacio.tcx"
    f.write_text('<?xml version="1.0"?><TrainingCenterDatabase creator="Health"'
                 ' xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">'
                 "<Activities/></TrainingCenterDatabase>")
    with pytest.raises(ht.TcxInvalido):
        ht.leer(str(f))
