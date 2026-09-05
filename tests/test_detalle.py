"""Tests de la vista de detalle de una carrera."""

import pytest

from runnerstats import db, detalle, graficas
from runnerstats.importers import nike_tcx as nike


@pytest.fixture
def conn_carrera(tmp_path, nike_dir):
    conn = db.conectar(tmp_path / "det.db")
    nike.importar(conn, str(nike_dir / "con-fc-y-gps.tcx"))
    cid = conn.execute("SELECT id FROM carrera").fetchone()["id"]
    return conn, cid


def test_la_distancia_acumulada_es_monotona_y_cierra(conn_carrera):
    """Nike da INCREMENTOS por punto; guardarlos sin acumular dejaba la
    columna con valores de 10-60 m que no servian para nada."""
    conn, cid = conn_carrera
    car = detalle.carrera(conn, cid)
    ms = detalle.muestreos(conn, cid)
    d = [m["distancia_acumulada_metros"] for m in ms
         if m["distancia_acumulada_metros"] is not None]
    assert d == sorted(d)
    assert abs(d[-1] - car["distancia_metros"]) / car["distancia_metros"] < 0.01


def test_la_serie_de_ritmo_da_valores_humanos(conn_carrera):
    conn, cid = conn_carrera
    serie = detalle.serie_ritmo(detalle.muestreos(conn, cid))
    assert len(serie) > 50
    ritmos = sorted(x["ritmo"] for x in serie)
    mediana = ritmos[len(ritmos) // 2]
    assert 180 < mediana < 900, f"ritmo mediano {mediana:.0f} s/km"


def test_las_paradas_no_cuentan_como_ritmo(conn_carrera):
    """Parado, el ritmo tiende a infinito y aplasta la escala."""
    conn, cid = conn_carrera
    serie = detalle.serie_ritmo(detalle.muestreos(conn, cid))
    # Con METROS_MINIMOS = 10 sobre una ventana de 20 s el techo son 33 min/km.
    assert max(x["ritmo"] for x in serie) < 2100


def test_los_parciales_cuadran_con_la_carrera(conn_carrera):
    conn, cid = conn_carrera
    car = detalle.carrera(conn, cid)
    sp = detalle.splits(detalle.muestreos(conn, cid))

    completos = [s for s in sp if not s["parcial"]]
    assert len(completos) == int(car["distancia_metros"] // 1000)

    # La suma de los parciales es la duracion, con margen por la interpolacion.
    total = sum(s["segundos"] for s in sp)
    assert abs(total - car["duracion_segundos"]) < car["duracion_segundos"] * 0.1


def _falsos(metros_totales: int, ritmo_s_km: float = 300):
    """Muestreos sinteticos a 1 Hz con ritmo constante."""
    paso = 1000 / ritmo_s_km
    return [{"timestamp_unix": t, "distancia_acumulada_metros": t * paso,
             "latitud": None, "longitud": None}
            for t in range(int(metros_totales / paso) + 1)]


def test_el_ultimo_tramo_se_marca_como_parcial():
    """La trampa que ya nos mordio con los splits de My Run Stats: el resto
    no es un kilometro y no se puede comparar con los demas."""
    sp = detalle.splits(_falsos(5400))
    assert [s["km"] for s in sp if not s["parcial"]] == [1, 2, 3, 4, 5]
    assert sp[-1]["parcial"] is True
    assert 350 < sp[-1]["metros"] < 450


def test_un_resto_insignificante_no_genera_parcial():
    """18 m sobrantes no son un tramo que enseñar."""
    sp = detalle.splits(_falsos(6018))
    assert len(sp) == 6
    assert all(not s["parcial"] for s in sp)


def test_los_kilometros_se_interpolan(conn_carrera):
    """A 2,2 s de muestreo, quedarse con la muestra mas cercana mete varios
    segundos de error en cada kilometro."""
    sp = detalle.splits(_falsos(3000, ritmo_s_km=300))
    for s in sp:
        assert abs(s["segundos"] - 300) < 1.5, s


def test_la_ruta_se_proyecta_dentro_del_lienzo(conn_carrera):
    conn, cid = conn_carrera
    r = graficas.ruta_svg(detalle.ruta(detalle.muestreos(conn, cid)))
    assert not r["vacia"]
    coords = [tuple(map(float, p.split(","))) for p in r["linea"].split()]
    assert all(0 <= x <= r["ancho"] and 0 <= y <= r["alto"] for x, y in coords)
    # El lienzo sigue la proporcion del recorrido, no es cuadrado a la fuerza.
    assert 0.4 < r["alto"] / r["ancho"] < 1.7


def test_una_carrera_sin_muestreos_no_ofrece_series(tmp_path):
    conn = db.conectar(tmp_path / "v.db")
    assert detalle.serie_ritmo([]) == []
    assert detalle.splits([]) == []
    assert detalle.ruta([]) == []
    assert graficas.ruta_svg([])["vacia"] is True
    assert graficas.linea_serie([], 0, 1)["vacia"] is True
