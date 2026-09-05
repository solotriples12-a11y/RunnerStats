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
    assert analisis.records_rodantes(c) == []
    assert analisis.volumen(c) == []


def test_la_linea_de_medianas_no_cruza_anios_vacios(conn_real):
    """2019 no tiene carreras: la linea debe partirse, no puentearlo."""
    from runnerstats import graficas
    g = graficas.dispersion_ritmo(analisis.ritmos(conn_real))
    anios = [m["anio"] for m in g["medianas"]]
    assert 2019 not in anios
    # Hay huecos, luego tiene que haber mas de un segmento.
    assert len(g["segmentos"]) + len(g["sueltos"]) > 1


def test_records_rodantes_salen_de_dentro_de_la_carrera(conn_real, nike_dir):
    """El mejor 5K no exige que la carrera midiera 5 km."""
    from runnerstats.importers import nike_tcx as nike
    nike.importar(conn_real, str(nike_dir / "con-fc-y-gps.tcx"))

    recs = {r["metros"]: r for r in analisis.records_rodantes(conn_real)}
    assert 1000 in recs and 5000 in recs

    for m, r in recs.items():
        # El tramo cabe dentro de su carrera.
        assert r["distancia_carrera"] >= m
        # Y el ritmo es humano: el record del mundo de 1000 m son 2:11.
        assert r["ritmo"] > 130, f"{m}: {r['ritmo']:.0f} s/km es imposible"
        assert r["ritmo"] < 900

    # Un tramo de 5 km nunca puede ser mas rapido que el mejor kilometro.
    assert recs[5000]["ritmo"] >= recs[1000]["ritmo"]


ANCHO_ETIQUETA = 46   # "28 jul" a 9 px de fuente monoespaciada, con holgura


def test_las_etiquetas_del_eje_no_se_pisan(conn_real, nike_dir):
    """Se repartia cada N barras y ADEMAS se forzaba la ultima, asi que las
    dos ultimas caian pegadas y el texto se solapaba."""
    from runnerstats import graficas
    from runnerstats.importers import nike_tcx as nike
    nike.importar(conn_real, str(nike_dir / "con-fc-y-gps.tcx"))

    for agr in analisis.AGRUPACIONES:
        for anio in (None, 2012):
            g = graficas.barras_volumen(analisis.volumen(conn_real, agr, anio))
            if g["vacia"]:
                continue
            xs = [b["centro"] for b in g["barras"] if b["etiquetada"]]
            assert xs == sorted(xs)
            separaciones = [b - a for a, b in zip(xs, xs[1:])]
            assert all(d >= ANCHO_ETIQUETA for d in separaciones), \
                f"{agr}/{anio}: etiquetas a {min(separaciones):.0f}px"


def test_el_eje_de_anios_del_ritmo_tampoco_se_pisa(conn_real):
    from runnerstats import graficas
    g = graficas.dispersion_ritmo(analisis.ritmos(conn_real))
    xs = [e["x"] for e in g["ejex"]]
    assert xs == sorted(xs), "el eje sale en orden inverso"
    assert all(b - a >= ANCHO_ETIQUETA for a, b in zip(xs, xs[1:]))
