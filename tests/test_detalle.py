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
             "latitud": None, "longitud": None, "frecuencia_cardiaca": None}
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


def test_la_ventana_rodante_interpola_el_arranque():
    """Ritmo constante: cualquier ventana de 1 km debe dar el mismo tiempo."""
    p = [(t, t * (1000 / 300)) for t in range(0, 1200)]   # 5:00/km
    v = detalle.mejor_ventana(p, 1000)
    assert v is not None
    assert abs(v[0] - 300) < 1.0, v


def test_no_hay_ventana_si_la_carrera_no_llega(conn_carrera):
    conn, cid = conn_carrera
    ms = detalle.muestreos(conn, cid)
    assert detalle.mejor_ventana(detalle._con_distancia(ms), 50000) is None


def test_los_saltos_imposibles_no_inventan_records():
    """Un pico de GPS daba un "mejor kilometro" de 1:25, mas rapido que el
    record del mundo. Se descuenta el tramo, no la carrera entera."""
    # 600 s a 5:00/km, con un salto de 400 m en 1 s por el medio.
    p, d = [], 0.0
    for t in range(600):
        d += 1000 / 300
        if t == 300:
            d += 400
        p.append((t, d))
    limpio = detalle._sin_saltos(p)
    v = detalle.mejor_ventana(limpio, 1000)
    assert v is not None and v[0] > 280, f"el salto se ha colado: {v}"


def test_cada_parcial_lleva_su_fc_media(conn_carrera):
    conn, cid = conn_carrera
    ms = detalle.muestreos(conn, cid)
    sp = detalle.splits(ms)
    con_fc = [s for s in sp if s["fc"]]
    assert len(con_fc) == len(sp), "faltan parciales sin FC en una carrera que si la tiene"

    # Cada media cae dentro del rango real de la carrera.
    pulsos = [m["frecuencia_cardiaca"] for m in ms if m["frecuencia_cardiaca"]]
    assert all(min(pulsos) <= s["fc"] <= max(pulsos) for s in con_fc)

    # Y la media de las medias se parece a la media global.
    global_ = sum(pulsos) / len(pulsos)
    medias = sum(s["fc"] for s in con_fc) / len(con_fc)
    assert abs(medias - global_) < 12


def test_sin_pulso_los_parciales_no_lo_inventan():
    p = [(t, t * (1000 / 300)) for t in range(900)]
    ms = [{"timestamp_unix": t, "distancia_acumulada_metros": d,
           "frecuencia_cardiaca": None, "latitud": None, "longitud": None}
          for t, d in p]
    assert all(s["fc"] is None for s in detalle.splits(ms))


def test_una_altitud_plana_no_dibuja_grafica():
    """En cinta la altitud viene como -1 constante: un centinela, no una
    medida. Dibujar una raya no aporta nada."""
    plana = [{"t": t, "v": -1.0} for t in range(300)]
    assert graficas.linea_serie(plana, 0, 299, rango_minimo=3.0)["vacia"] is True

    # Con desnivel real si se dibuja.
    real = [{"t": t, "v": 20 + t / 30} for t in range(300)]
    assert graficas.linea_serie(real, 0, 299, rango_minimo=3.0)["vacia"] is False


def test_el_pulso_no_se_oculta_por_ser_estable():
    """El umbral es solo de la altitud: una FC plana sigue siendo un dato."""
    estable = [{"t": t, "v": 150} for t in range(300)]
    assert graficas.linea_serie(estable, 0, 299)["vacia"] is False


def _serie(metros_por_punto, n, carrera_km=None, carrera_s=None, hueco_en=None):
    """Muestreos sinteticos a 1 Hz, opcionalmente con un hueco sin distancia."""
    ms, d = [], 0.0
    for t in range(n):
        hay = not (hueco_en and hueco_en[0] <= t < hueco_en[1])
        if hay:
            d += metros_por_punto
        ms.append({"timestamp_unix": t,
                   "distancia_acumulada_metros": d if hay else None,
                   "latitud": None, "longitud": None, "frecuencia_cardiaca": None})
    car = None
    if carrera_km is not None:
        car = {"distancia_metros": carrera_km * 1000,
               "duracion_segundos": carrera_s if carrera_s else n}
    return ms, car


def test_se_descarta_la_serie_con_un_hueco_interior():
    """Caso real: 890 s seguidos sin distancia en una carrera de 2400, con los
    incrementos concentrados en el tramo con datos. El acumulado llegaba a
    5 km en 1230 s cuando la app de Nike marcaba 2093."""
    ms, car = _serie(3.3, 2400, carrera_km=7.9, carrera_s=2400, hueco_en=(800, 1690))
    assert detalle._con_distancia(ms, car) == []
    assert detalle.serie_ritmo(ms, car) == []
    assert detalle.splits(ms, car) == []
    assert detalle.ventanas(ms, car) == {}


def test_se_descarta_la_serie_que_no_suma_la_distancia_declarada():
    """Vista una serie que solo sumaba el 36 % de los metros de su carrera."""
    ms, car = _serie(3.3, 1000, carrera_km=9.0)   # la serie da 3,3 km
    assert detalle._con_distancia(ms, car) == []


def test_se_descarta_la_serie_mas_larga_que_la_carrera():
    """Vista una serie de 2822 s para una carrera que declara 1932."""
    ms, car = _serie(3.3, 2800, carrera_km=9.24, carrera_s=1900)
    assert detalle._con_distancia(ms, car) == []


def test_una_serie_coherente_con_su_carrera_se_acepta():
    paso = 1000 / 300
    ms, car = _serie(paso, 1200, carrera_km=1200 * paso / 1000, carrera_s=1200)
    assert len(detalle._con_distancia(ms, car)) == 1200
    ms = [{"timestamp_unix": t, "distancia_acumulada_metros": t * paso,
           "latitud": None, "longitud": None, "frecuencia_cardiaca": None}
          for t in range(1200)]
    assert detalle.ventanas(ms)[1000][0] == pytest.approx(300, abs=1)


def test_media_y_maraton_solo_salen_si_se_cubren():
    """Estan declaradas pero no aparecen hasta que una carrera las cubra."""
    assert 21097 in detalle.DISTANCIAS and 42195 in detalle.DISTANCIAS
    paso = 1000 / 300
    corta = [{"timestamp_unix": t, "distancia_acumulada_metros": t * paso,
              "latitud": None, "longitud": None, "frecuencia_cardiaca": None}
             for t in range(1800)]          # 6 km
    v = detalle.ventanas(corta)
    assert set(v) == {1000, 5000}
    assert 21097 not in v and 42195 not in v


def _con_parada(metros_por_s=3.3, corriendo=600, parado=300):
    """Corre, se para (el GPS tiembla un poco) y sigue."""
    ms, d = [], 0.0
    t = 0
    for _ in range(corriendo):
        d += metros_por_s; ms.append((t, d)); t += 1
    for _ in range(parado):
        d += 0.05        # 0,05 m/s: temblor de GPS, no avance
        ms.append((t, d)); t += 1
    for _ in range(corriendo):
        d += metros_por_s; ms.append((t, d)); t += 1
    return ms


def test_el_tiempo_parado_no_cuenta():
    """Nike lo excluye de su duracion; sin esto los parciales salian mas
    lentos que en la app."""
    puntos = _con_parada()
    mov = detalle.en_movimiento(puntos)
    assert mov[0] == (0.0, puntos[0][1])
    # 1200 s corriendo de los 1500 transcurridos.
    assert 1190 < mov[-1][0] < 1210, mov[-1][0]
    # La distancia no se toca.
    assert mov[-1][1] == puntos[-1][1]


def test_los_parciales_se_cronometran_sin_las_paradas():
    puntos = _con_parada()
    ms = [{"timestamp_unix": t, "distancia_acumulada_metros": d,
           "latitud": None, "longitud": None, "frecuencia_cardiaca": None}
          for t, d in puntos]
    car = {"distancia_metros": puntos[-1][1], "duracion_segundos": 1200}
    sp = detalle.splits(ms, car)
    completos = [s for s in sp if not s["parcial"]]
    assert completos, "deberia haber kilometros completos"
    # A 3,3 m/s un kilometro son ~303 s. Con la parada dentro serian ~600.
    for s in completos:
        assert 280 < s["segundos"] < 340, f"km {s['km']}: {s['segundos']:.0f}s"


def test_un_record_no_incluye_el_tiempo_parado():
    puntos = _con_parada()
    v = detalle.mejor_ventana(detalle.en_movimiento(puntos), 1000)
    assert v is not None
    assert 280 < v[0] < 340, v[0]


def _version(conn, cid, inicio, filas, sustituye=None):
    """Mete una version de una carrera con los muestreos que se le digan.

    Cada fila es (segundo, fc, lat, altitud); None donde esa fuente no aporte.
    """
    conn.execute(
        "INSERT INTO carrera (id, fecha_inicio_unix, distancia_metros,"
        " duracion_segundos, fuente, sustituida_por, importado_en)"
        " VALUES (?,?,?,?,?,?,0)",
        (cid, inicio, 5000.0, 1800, cid.split(":")[0], sustituye))
    conn.executemany(
        "INSERT INTO muestreo (carrera_id, timestamp_unix, frecuencia_cardiaca,"
        " latitud, longitud, altitud_metros) VALUES (?,?,?,?,?,?)",
        [(cid, inicio + seg, fc, lat, None if lat is None else -3.7, alt)
         for seg, fc, lat, alt in filas])
    conn.commit()


def test_los_muestreos_fusionan_las_versiones_de_la_carrera(tmp_path):
    """Nike trajo el pulso de la carrera del 19 de abril y Huawei el
    recorrido: por separado ninguna de las dos vale, juntas si."""
    conn = db.conectar(tmp_path / "f.db")
    _version(conn, "nike_tcx:1000", 1000,
             [(i, 150 + i, None, None) for i in range(10)])
    _version(conn, "huawei_tcx:1002", 1002,
             [(i, None, 40.0 + i / 1000, 600 + i) for i in range(10)],
             sustituye="nike_tcx:1000")

    ms = detalle.muestreos(conn, "nike_tcx:1000")
    assert sum(1 for m in ms if m["frecuencia_cardiaca"] is not None) == 10
    assert sum(1 for m in ms if m["latitud"] is not None) == 10
    assert sum(1 for m in ms if m["altitud_metros"] is not None) == 10
    # La longitud viaja con la latitud: media coordenada no es media posicion.
    assert all((m["latitud"] is None) == (m["longitud"] is None) for m in ms)


def test_una_version_que_no_solapa_no_se_fusiona(tmp_path):
    """La deduplicacion agrupa por dia y distancia, asi que dos entrenamientos
    parecidos del mismo dia caen juntos. Vistos desfases de 1.833 s y de
    53.216 s con cero solape: no son la misma carrera."""
    conn = db.conectar(tmp_path / "f.db")
    _version(conn, "nike_tcx:1000", 1000,
             [(i, 150, None, None) for i in range(10)])
    _version(conn, "huawei_json:60000", 60000,
             [(i, None, 40.0, 600) for i in range(10)],
             sustituye="nike_tcx:1000")

    ms = detalle.muestreos(conn, "nike_tcx:1000")
    assert len(ms) == 10
    assert not any(m["latitud"] for m in ms)


def test_una_serie_constante_pierde_contra_una_que_varia(tmp_path):
    """La altitud de Nike en esa carrera son 3.442 ceros y la de Huawei 3.440
    metros de verdad: por contar valores ganaba la plana."""
    conn = db.conectar(tmp_path / "f.db")
    _version(conn, "nike_tcx:1000", 1000,
             [(i, 150, None, 0.0) for i in range(12)])
    _version(conn, "huawei_tcx:1000", 1000,
             [(i, None, None, 600 + i) for i in range(10)],
             sustituye="nike_tcx:1000")

    alt = [m["altitud_metros"] for m in detalle.muestreos(conn, "nike_tcx:1000")
           if m["altitud_metros"] is not None]
    assert len(alt) == 10 and max(alt) - min(alt) == 9


def test_sin_otras_versiones_los_muestreos_salen_tal_cual(conn_carrera):
    conn, cid = conn_carrera
    crudos = conn.execute(
        "SELECT * FROM muestreo WHERE carrera_id = ? ORDER BY timestamp_unix",
        (cid,)).fetchall()
    assert detalle.muestreos(conn, cid) == crudos


def test_una_serie_casi_plana_no_llena_el_lienzo(tmp_path):
    """El contacto con el suelo vive en 34 ms de rango sobre un valor de 305:
    reescalando al percentil 2-98, un temblor de 1 ms parecia una montaña."""
    pts = [{"t": t, "v": 305 + (t % 3)} for t in range(200)]
    sin_minimo = graficas.linea_serie(pts, 0, 199)
    con_minimo = graficas.linea_serie(pts, 0, 199, eje_minimo=100.0)

    def alto(g):
        ys = [float(p.split(",")[1]) for p in g["linea"].split()]
        return max(ys) - min(ys)

    assert alto(sin_minimo) > 80, "sin eje minimo la serie llena el lienzo"
    assert alto(con_minimo) < 5, "con eje minimo se ve lo plana que es"
    # Y el eje sigue centrado en los datos.
    etiquetas = [float(r["etiqueta"]) for r in con_minimo["rejilla"]]
    assert min(etiquetas) < 305 < max(etiquetas)


def test_las_zonas_de_fc_salen_de_las_versiones_sustituidas(tmp_path):
    """Mismo motivo que los muestreos: si gana una version sin zonas y otra
    las tiene, esconderla entera las tira."""
    conn = db.conectar(tmp_path / "z.db")
    for cid, sus in (("nike_tcx:1", None), ("amazfit_fit:2", "nike_tcx:1")):
        conn.execute(
            "INSERT INTO carrera (id, fecha_inicio_unix, distancia_metros,"
            " duracion_segundos, fuente, sustituida_por, importado_en)"
            " VALUES (?,1000,5000,1800,?,?,0)", (cid, cid.split(":")[0], sus))
    conn.executemany("INSERT INTO zona_fc (carrera_id, zona, segundos) VALUES (?,?,?)",
                     [("amazfit_fit:2", 3, 600), ("amazfit_fit:2", 4, 900)])
    conn.commit()

    assert detalle.zonas_fc(conn, "nike_tcx:1") == [
        {"zona": 3, "segundos": 600}, {"zona": 4, "segundos": 900}]


def test_la_barra_de_zonas_reparte_el_ancho_por_tiempo(tmp_path):
    zonas = [{"zona": 3, "segundos": 600}, {"zona": 4, "segundos": 1800}]
    g = graficas.barras_zonas(zonas)
    assert not g["vacia"] and len(g["tramos"]) == 2
    assert [round(t["parte"], 2) for t in g["tramos"]] == [0.25, 0.75]
    # La zona 4 es mas intensa y va mas clara: la rampa es de un solo tono.
    assert g["tramos"][0]["color"] != g["tramos"][1]["color"]
    # Una carrera sin zonas no pinta barra.
    assert graficas.barras_zonas([])["vacia"]
    assert graficas.barras_zonas([{"zona": 1, "segundos": 0}])["vacia"]
