"""Tests del análisis. Los que van contra el export real recalculan el
resultado por su cuenta desde el JSON y lo comparan con el que da SQL, en vez
de clavar números a mano."""

import json

import pytest

from runnerstats import analisis, db
from runnerstats.importers import my_run_stats as mrs


@pytest.fixture
def conn_real(tmp_path, export_real):
    c = db.conectar(tmp_path / "a.db")
    mrs.importar(c, export_real)
    return c


@pytest.fixture
def crudo(export_real):
    return json.loads(export_real.read_text())["runs"]


def test_resumen_cuadra_con_el_json(conn_real, crudo):
    r = analisis.resumen(conn_real)
    assert r["carreras"] == len(crudo)
    assert round(r["metros"] / 1000, 1) == round(sum(c["distance"] for c in crudo), 1)
    assert r["segundos"] == sum(mrs.a_segundos(c["duration"]) for c in crudo)


def test_filtro_por_anio(conn_real, crudo):
    de2012 = [c for c in crudo if c["date"].startswith("2012")]
    r = analisis.resumen(conn_real, 2012)
    assert r["carreras"] == len(de2012) == 33
    assert round(r["metros"] / 1000, 1) == 227.4


def test_anios_disponibles_no_inventa_huecos(conn_real, crudo):
    """2019 no tiene ninguna carrera y no debe aparecer."""
    esperados = sorted({c["date"][:4] for c in crudo}, reverse=True)
    assert [str(a) for a in analisis.anios(conn_real)] == esperados
    assert 2019 not in analisis.anios(conn_real)


def test_mejor_ritmo_coincide_con_el_calculo_directo(conn_real, crudo):
    mejor = min(
        mrs.a_segundos(c["duration"]) / c["distance"]
        for c in crudo if c["distance"] >= 3
    )
    assert abs(analisis.resumen(conn_real)["mejor_ritmo"] - mejor) < 1


def test_records_por_banda(conn_real, crudo):
    recs = {r["banda"]: r for r in analisis.records(conn_real)}
    assert "5K" in recs and "10K" in recs
    # La banda "Media" no existe: la carrera más larga son 14,99 km.
    assert "Media" not in recs

    for banda, lo, hi in (("5K", 5, 6), ("10K", 10, 11)):
        esperado = min(
            mrs.a_segundos(c["duration"]) / c["distance"]
            for c in crudo if lo <= c["distance"] < hi
        )
        assert abs(recs[banda]["ritmo"] - esperado) < 1
        assert lo * 1000 <= recs[banda]["distancia_metros"] < hi * 1000


def test_volumen_por_anio_suma_el_total(conn_real, crudo):
    v = analisis.volumen(conn_real, "anio")
    assert round(sum(x["km"] for x in v), 1) == round(sum(c["distance"] for c in crudo), 1)
    assert sum(x["carreras"] for x in v) == len(crudo)


def test_los_periodos_sin_carreras_salen_a_cero(conn_real):
    """Omitir 2019 pegaria 2018 con 2020 y el eje mentiria sobre el tiempo."""
    v = {x["clave"]: x for x in analisis.volumen(conn_real, "anio")}
    assert "2019" in v
    assert v["2019"]["km"] == 0 and v["2019"]["carreras"] == 0
    # Y la serie es continua, sin saltos.
    claves = [int(k) for k in v]
    assert claves == list(range(min(claves), max(claves) + 1))


def test_la_semana_empieza_en_lunes(conn_real):
    from datetime import date
    v = analisis.volumen(conn_real, "semana", 2012)
    for x in v:
        assert date.fromisoformat(x["clave"]).weekday() == 0, x["clave"]
    # Semanas consecutivas, siete dias exactos entre una y la siguiente.
    fechas = [date.fromisoformat(x["clave"]) for x in v]
    assert all((b - a).days == 7 for a, b in zip(fechas, fechas[1:]))


def test_agrupar_por_carrera_da_una_barra_por_carrera(conn_real, crudo):
    de2012 = [c for c in crudo if c["date"].startswith("2012")]
    v = analisis.volumen(conn_real, "carrera", 2012)
    assert len(v) == len(de2012) == 33
    assert all(x["carreras"] == 1 for x in v)
    assert round(sum(x["km"] for x in v), 2) == round(sum(c["distance"] for c in de2012), 2)


def test_agrupar_por_mes_respeta_el_filtro_de_anio(conn_real):
    v = analisis.volumen(conn_real, "mes", 2012)
    assert len(v) == 12          # el año entero, con los vacios a cero
    assert not v[0]["recortado"]


def test_sin_anio_las_agrupaciones_finas_se_recortan(conn_real):
    """El histórico completo por semanas serian ~770 barras ilegibles."""
    for agr, tope in (("mes", 36), ("semana", 52)):
        v = analisis.volumen(conn_real, agr)
        assert len(v) == tope
        assert v[0]["recortado"] is True


def test_agrupacion_desconocida_cae_en_anio(conn_real):
    assert analisis.volumen(conn_real, "loquesea") == analisis.volumen(conn_real, "anio")


def test_resumen_vacio_no_revienta(tmp_path):
    c = db.conectar(tmp_path / "v.db")
    r = analisis.resumen(c)
    assert r["carreras"] == 0 and r["metros"] == 0
    assert r["mejor_ritmo"] is None
    assert analisis.records(c) == []
    assert analisis.volumen(c) == []


def test_la_linea_de_medianas_no_cruza_anios_vacios(conn_real):
    """2019 no tiene carreras: la linea debe partirse, no puentearlo."""
    from runnerstats import graficas
    g = graficas.dispersion_ritmo(analisis.ritmos(conn_real))
    anios = [m["anio"] for m in g["medianas"]]
    assert 2019 not in anios
    # Hay huecos, luego tiene que haber mas de un segmento.
    assert len(g["segmentos"]) + len(g["sueltos"]) > 1


def test_los_records_traen_el_tiempo_real_de_la_carrera(conn_real, crudo):
    """El tiempo mostrado es el de esa carrera, no una proyeccion."""
    porid = {c["id"]: c for c in crudo}
    for r in analisis.records(conn_real):
        original = porid[r["id"].split(":", 1)[1]]
        assert r["duracion_segundos"] == mrs.a_segundos(original["duration"])
        # Y cuadra con ritmo x distancia.
        assert abs(r["ritmo"] * r["distancia_metros"] / 1000
                   - r["duracion_segundos"]) < 1
