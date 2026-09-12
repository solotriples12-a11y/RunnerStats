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


def test_un_año_filtrado_pinta_los_doce_meses(conn_real):
    """En 2015 solo se corrio en enero, febrero, junio, julio y agosto. El eje
    tiene que ser el año entero: empezar en enero y acabar en agosto esconde
    que de septiembre a diciembre no se salio."""
    v = analisis.volumen(conn_real, "mes", 2015)
    assert [x["clave"] for x in v] == [f"2015-{m:02d}" for m in range(1, 13)]
    assert [x["etiqueta"] for x in v] == list(analisis.MESES_CORTOS)
    con_datos = {x["clave"] for x in v if x["carreras"]}
    assert con_datos == {"2015-01", "2015-02", "2015-06", "2015-07", "2015-08"}
    assert all(x["km"] == 0 for x in v if x["clave"] not in con_datos)


def test_un_año_con_un_solo_mes_tambien_sale_entero(conn_real):
    """2011 solo tiene diciembre: una sola fila, que es justo el caso en el
    que el relleno de huecos se rendia y devolvia la lista tal cual."""
    v = analisis.volumen(conn_real, "mes", 2011)
    assert len(v) == 12
    assert sum(x["carreras"] for x in v) == v[11]["carreras"] > 0


def test_sin_filtro_los_meses_siguen_yendo_del_primero_al_ultimo(conn_real):
    """El relleno del año entero es solo para el año filtrado: en el
    histórico completo no hay año al que estirarse."""
    v = analisis.volumen(conn_real, "mes")
    assert v[0]["carreras"] > 0 and v[-1]["carreras"] > 0


def test_sin_año_los_meses_y_semanas_vacios_no_pintan_barra(conn_real):
    """Con "Todo" el recorte a los ultimos N periodos se gastaba en meses sin
    salir a correr: 178 meses de historico, la mayoria vacios."""
    for agr in ("mes", "semana"):
        v = analisis.volumen(conn_real, agr)
        assert v and all(x["carreras"] for x in v), agr

    # Los años si se siguen rellenando: 2019 esta vacio y tiene que salir.
    assert any(not x["carreras"] for x in analisis.volumen(conn_real, "anio"))
    # Y con un año elegido, los doce meses siguen estando.
    assert len(analisis.volumen(conn_real, "mes", 2015)) == 12


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
    assert analisis.records_rodantes(c) == []
    assert analisis.volumen(c) == []


def test_la_linea_de_medianas_no_cruza_anios_vacios(conn_real):
    """2019 no tiene carreras: la linea debe partirse, no puentearlo."""
    from runnerstats import graficas
    g = graficas.dispersion_ritmo(analisis.ritmos(conn_real))
    anios = [m["periodo"] for m in g["medianas"]]
    assert 2019 not in anios
    # Hay huecos, luego tiene que haber mas de un segmento.
    assert len(g["segmentos"]) + len(g["sueltos"]) > 1


def test_el_ritmo_respeta_el_filtro_de_anio(conn_real, crudo):
    from datetime import datetime, timezone
    r = analisis.ritmos(conn_real, 2015)
    assert r, "2015 tiene carreras"
    assert len(r) < len(analisis.ritmos(conn_real))
    for c in r:
        assert datetime.fromtimestamp(
            c["fecha_inicio_unix"], timezone.utc).year == 2015


def test_dentro_de_un_anio_la_mediana_es_mensual(conn_real):
    """Una sola mediana anual para un año no dibuja ninguna evolución."""
    from runnerstats import graficas
    g = graficas.dispersion_ritmo(analisis.ritmos(conn_real, 2015), 2015)
    assert not g["vacia"]
    # 2015: enero, febrero, junio, julio y agosto.
    assert [m["periodo"] for m in g["medianas"]] == [1, 2, 6, 7, 8]
    assert [m["etiqueta"] for m in g["medianas"]] == ["ene", "feb", "jun", "jul", "ago"]
    # Y la linea se parte en el hueco de marzo a mayo.
    assert len(g["segmentos"]) == 2
    # El eje etiqueta meses, no años, y cada uno cae bajo su nodo de mediana.
    # Julio se salta: su nodo queda pegado al de agosto.
    assert [e["etiqueta"] for e in g["ejex"]] == ["ene", "feb", "jun", "ago"]


def test_un_mes_suelto_no_parte_la_linea_de_medianas(conn_real):
    """Partir por un solo mes en blanco dejaba puntos sueltos que se leian
    como un fallo de pintado, no como un parón."""
    from runnerstats import graficas
    # 2022: de enero a junio, agosto, y de octubre a diciembre. Los dos
    # huecos son de un mes (julio y septiembre): la linea no se parte.
    g = graficas.dispersion_ritmo(analisis.ritmos(conn_real, 2022), 2022)
    assert [m["periodo"] for m in g["medianas"]] == [1, 2, 3, 4, 5, 6, 8, 10, 11, 12]
    assert len(g["segmentos"]) == 1 and not g["sueltos"]

    # 2015 si: de marzo a mayo son tres meses seguidos sin correr.
    g15 = graficas.dispersion_ritmo(analisis.ritmos(conn_real, 2015), 2015)
    assert len(g15["segmentos"]) == 2


def test_la_distancia_cuenta_tambien_las_de_menos_de_un_km(tmp_path):
    """El ritmo las deja fuera porque en 500 m no hay un ritmo que leer. La
    distancia sí es un dato, y las tarjetas y la gráfica de kilómetros ya las
    cuentan."""
    c = db.conectar(tmp_path / "d.db")
    c.executemany(
        "INSERT INTO carrera (id, fecha_inicio_unix, distancia_metros,"
        " duracion_segundos, fuente, importado_en) VALUES (?,?,?,?,?,0)",
        [("a", 1_700_000_000, 500, 240, "my_run_stats"),
         ("b", 1_700_100_000, 5000, 1500, "my_run_stats")])
    assert len(analisis.ritmos(c)) == 1
    assert [d["km"] for d in analisis.distancias(c)] == [0.5, 5.0]


@pytest.mark.parametrize("anio", [None, 2013])
def test_el_eje_de_la_distancia_va_de_cero_a_la_mas_larga(conn_real, anio):
    """El del ritmo recorta el 2 % extremo, que son paseos. Aquí ese extremo
    son las carreras más largas: salen donde tocan, a escala desde cero."""
    from runnerstats import graficas
    g = graficas.dispersion_distancia(analisis.distancias(conn_real, anio), anio)
    base, techo = graficas.ALTO - graficas.PAD_INF, graficas.PAD_SUP
    assert g["rejilla"][0] == {"y": base, "etiqueta": "0 km"}

    larga = max(g["puntos"], key=lambda p: p["km"])
    assert larga["cy"] == techo
    for p in g["puntos"]:
        assert abs((base - p["cy"]) - (base - techo) * p["km"] / larga["km"]) <= 0.1


def test_records_rodantes_salen_de_dentro_de_la_carrera(conn_real, nike_dir):
    """El mejor 5K no exige que la carrera midiera 5 km."""
    from runnerstats import detalle
    from runnerstats.importers import nike_tcx as nike
    nike.importar(conn_real, str(nike_dir / "con-fc-y-gps.tcx"))

    detalle.recalcular_records(conn_real)
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


# Ancho de un caracter a 9 px de fuente monoespaciada, estimado por lo alto
# (produccion cuenta 5,4) mas un respiro entre etiquetas vecinas.
ANCHO_CARACTER = 5.6
AIRE = 4


def _sitio_que_pide(etiquetas: list[str]) -> float:
    """Separacion minima entre centros para que dos etiquetas no se toquen."""
    return max(len(e) for e in etiquetas) * ANCHO_CARACTER + AIRE


def test_las_etiquetas_del_eje_no_se_pisan(conn_real, nike_dir):
    """Se repartia cada N barras y ADEMAS se forzaba la ultima, asi que las
    dos ultimas caian pegadas y el texto se solapaba."""
    from runnerstats import graficas
    from runnerstats.importers import nike_tcx as nike
    nike.importar(conn_real, str(nike_dir / "con-fc-y-gps.tcx"))

    for agr in analisis.AGRUPACIONES:
        for anio in (None, 2012, 2015):
            g = graficas.barras_volumen(analisis.volumen(conn_real, agr, anio))
            if g["vacia"]:
                continue
            etiquetadas = [b for b in g["barras"] if b["etiquetada"]]
            xs = [b["centro"] for b in etiquetadas]
            assert xs == sorted(xs)
            minima = _sitio_que_pide([b["etiqueta"] for b in etiquetadas])
            separaciones = [b - a for a, b in zip(xs, xs[1:])]
            assert all(d >= minima for d in separaciones), \
                f"{agr}/{anio}: etiquetas a {min(separaciones):.0f}px, piden {minima:.0f}"


def test_los_doce_meses_de_un_año_van_todos_etiquetados(conn_real):
    """Caben de sobra: dejar enero sin poner era un tope fijo de 8 etiquetas,
    no una cuestion de sitio."""
    from runnerstats import graficas
    g = graficas.barras_volumen(analisis.volumen(conn_real, "mes", 2022))
    assert [b["etiqueta"] for b in g["barras"] if b["etiquetada"]] == \
        list(analisis.MESES_CORTOS)


def test_las_semanas_de_un_año_si_se_recortan(conn_real):
    """53 etiquetas de "28 jul" no caben: ahi el paso sigue haciendo falta."""
    from runnerstats import graficas
    g = graficas.barras_volumen(analisis.volumen(conn_real, "semana", 2022))
    assert len(g["barras"]) > 50
    assert len([b for b in g["barras"] if b["etiquetada"]]) < 20


@pytest.mark.parametrize("anio", [None, 2012, 2015, 2022])
def test_el_eje_del_ritmo_tampoco_se_pisa(conn_real, anio):
    from runnerstats import graficas
    g = graficas.dispersion_ritmo(analisis.ritmos(conn_real, anio), anio)
    xs = [e["x"] for e in g["ejex"]]
    assert xs == sorted(xs), "el eje sale en orden inverso"
    minima = _sitio_que_pide([e["etiqueta"] for e in g["ejex"]])
    assert all(b - a >= minima for a, b in zip(xs, xs[1:]))

    # Y ninguna se sale del lienzo: van centradas en su nodo, y el ultimo
    # nodo cae casi pegado al borde derecho.
    for e in g["ejex"]:
        # Con el ancho que asume produccion: es su promesa, no una estimacion.
        media = len(e["etiqueta"]) * graficas.ANCHO_CARACTER / 2
        assert 0 <= e["x"] - media and e["x"] + media <= graficas.ANCHO


def test_ningun_record_es_mas_rapido_de_lo_que_permite_su_carrera(conn_real, nike_dir):
    """La invariante que fallo: un record salio a 4:04/km dentro de una
    carrera cuya media era 7:07/km, porque la serie de distancia mentia."""
    import glob
    from runnerstats import detalle, dedup
    from runnerstats.importers import nike_tcx as nike
    for f in glob.glob(str(nike_dir / "*.tcx")):
        try:
            nike.importar(conn_real, f)
        except Exception:
            pass
    dedup.marcar_duplicadas(conn_real)
    detalle.recalcular_records(conn_real)

    for r in analisis.records_rodantes(conn_real):
        car = detalle.carrera(conn_real, r["carrera_id"])
        media = car["duracion_segundos"] / (car["distancia_metros"] / 1000)
        # Un tramo puede ser mas rapido que la media, pero no cinco veces.
        assert r["ritmo"] > media * 0.55, (
            f"{r['nombre']}: {r['ritmo']:.0f} s/km dentro de una carrera "
            f"de media {media:.0f} s/km")


def test_toda_serie_usada_concuerda_con_su_resumen(conn_real, nike_dir):
    """Auditoria: si mostramos ritmo o parciales de una carrera, su serie de
    distancia tiene que implicar el mismo ritmo que su resumen."""
    import glob
    from runnerstats import detalle
    from runnerstats.importers import nike_tcx as nike
    for f in glob.glob(str(nike_dir / "*.tcx")):
        try:
            nike.importar(conn_real, f)
        except Exception:
            pass

    revisadas = 0
    for car in conn_real.execute("SELECT * FROM carrera WHERE sustituida_por IS NULL"):
        ms = detalle.muestreos(conn_real, car["id"])
        p = detalle._con_distancia(ms, car) if ms else []
        if len(p) < 3 or not car["duracion_segundos"]:
            continue
        revisadas += 1
        serie = (p[-1][0] - p[0][0]) / ((p[-1][1] - p[0][1]) / 1000)
        declarado = car["duracion_segundos"] / (car["distancia_metros"] / 1000)
        assert abs(serie - declarado) / declarado <= 0.15, (
            f"{car['id']}: serie {serie:.0f} s/km vs resumen {declarado:.0f} s/km")
    assert revisadas > 0
