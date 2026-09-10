"""Tests del parser de .fit contra un fichero real del Amazfit Cheetah 2 Pro.

Los numeros se contrastan con el mensaje `session` del propio fichero, que es
el resumen que calcula el reloj, no con constantes escritas a mano.
"""

from datetime import datetime, timezone

import pytest
from fitparse import FitFile

from runnerstats import db
from runnerstats.importers import amazfit_fit as fit


@pytest.fixture
def sesion(fit_real):
    """El mensaje `session` en crudo, para contrastar."""
    f = FitFile(str(fit_real))
    s = next(m for m in f.get_messages("session"))
    return {c.name: c.value for c in s}


def test_resumen_cuadra_con_la_sesion_del_reloj(fit_real, sesion):
    carrera, _ = fit.leer(str(fit_real))
    assert carrera.distancia_metros == sesion["total_distance"]
    assert carrera.duracion_segundos == int(sesion["total_elapsed_time"])
    assert carrera.fc_media == sesion["avg_heart_rate"]
    assert carrera.fc_maxima == sesion["max_heart_rate"]
    assert carrera.desnivel_positivo_metros == sesion["total_ascent"]
    assert carrera.calorias == sesion["total_calories"]
    assert carrera.dispositivo == "Amazfit Cheetah 2 Pro"
    assert carrera.fuente == "amazfit_fit"


def test_el_instante_de_inicio_se_interpreta_en_utc(fit_real, sesion):
    carrera, _ = fit.leer(str(fit_real))
    esperado = sesion["start_time"].replace(tzinfo=timezone.utc)
    assert carrera.fecha_inicio_unix == int(esperado.timestamp())
    # La carrera de prueba arranco a las 06:06:24 UTC.
    d = datetime.fromtimestamp(carrera.fecha_inicio_unix, timezone.utc)
    assert d.strftime("%Y-%m-%d %H:%M:%S") == "2026-09-02 06:06:24"


def test_muestreo_a_1hz_sin_huecos(fit_real):
    _, muestreos = fit.leer(str(fit_real))
    assert len(muestreos) == 3603
    ts = [m.timestamp_unix for m in muestreos]
    assert all(b - a == 1 for a, b in zip(ts, ts[1:]))


def test_cadencia_normalizada_a_pasos_por_minuto(fit_real):
    """La trampa del factor 2: `record.cadence` viene por pierna.

    Se contrasta con `total_strides`, que si cuenta pasos: 9302 pasos en
    3602 s son ~155 spm, no ~77.
    """
    carrera, muestreos = fit.leer(str(fit_real))
    cadencias = [m.cadencia_spm for m in muestreos if m.cadencia_spm]
    media = sum(cadencias) / len(cadencias)
    assert 140 < media < 175, f"cadencia media {media:.0f}, se esperaba ~156"

    f = FitFile(str(fit_real))
    s = {c.name: c.value for c in next(f.get_messages("session"))}
    esperada = s["total_strides"] / s["total_elapsed_time"] * 60
    assert abs(media - esperada) < 12


def test_gps_convertido_de_semicirculos_a_grados(fit_real):
    _, muestreos = fit.leer(str(fit_real))
    con_gps = [m for m in muestreos if m.latitud is not None]
    assert len(con_gps) == 3603
    # La carrera es de Madrid: latitud ~40,45 N, longitud ~-3,45 E.
    assert 40.4 < con_gps[0].latitud < 40.5
    assert -3.5 < con_gps[0].longitud < -3.4
    assert all(-90 <= m.latitud <= 90 for m in con_gps)


def test_distancia_acumulada_es_monotona_y_cierra_en_el_total(fit_real, sesion):
    """Es el campo que hace posible los records por ventana rodante."""
    _, muestreos = fit.leer(str(fit_real))
    d = [m.distancia_acumulada_metros for m in muestreos
         if m.distancia_acumulada_metros is not None]
    assert all(a <= b for a, b in zip(d, d[1:]))
    assert d[0] == 0
    assert abs(d[-1] - sesion["total_distance"]) < 1


def test_los_huecos_del_sensor_quedan_a_none(fit_real):
    """No se rellenan ni se ponen a cero: faltar es un dato."""
    _, muestreos = fit.leer(str(fit_real))
    assert sum(1 for m in muestreos if m.frecuencia_cardiaca is None) == 92
    assert sum(1 for m in muestreos if m.cadencia_spm is None) == 49


def test_importa_a_sqlite_con_sus_muestreos(tmp_path, fit_real):
    conn = db.conectar(tmp_path / "fit.db")
    assert len(fit.importar(conn, str(fit_real))) == 1

    carrera = conn.execute("SELECT * FROM carrera").fetchone()
    assert carrera["fuente"] == "amazfit_fit"
    assert carrera["fc_media"] == 148
    n = conn.execute(
        "SELECT COUNT(*) FROM muestreo WHERE carrera_id = ?", (carrera["id"],)
    ).fetchone()[0]
    assert n == 3603


def test_reimportar_no_duplica_ni_deja_huerfanos(tmp_path, fit_real):
    conn = db.conectar(tmp_path / "fit.db")
    fit.importar(conn, str(fit_real))
    fit.importar(conn, str(fit_real))
    assert conn.execute("SELECT COUNT(*) FROM carrera").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM muestreo").fetchone()[0] == 3603


def test_borrar_la_carrera_arrastra_los_muestreos(tmp_path, fit_real):
    conn = db.conectar(tmp_path / "fit.db")
    fit.importar(conn, str(fit_real))
    conn.execute("DELETE FROM carrera")
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM muestreo").fetchone()[0] == 0


def test_un_fichero_que_no_es_fit_da_error_claro(tmp_path):
    basura = tmp_path / "falso.fit"
    basura.write_bytes(b"esto no es un fit")
    with pytest.raises(Exception):
        fit.leer(str(basura))


def test_la_duracion_es_el_cronometro_y_no_el_reloj_de_pared(fit_real):
    """`total_elapsed_time` cuenta tambien las pausas. En la carrera del
    2026-09-06 son 3.132 s contra los 2.521 que marca la app: diez minutos de
    mas que estropeaban el ritmo medio, 8:31/km en vez de 6:51."""
    import glob
    con_pausas = None
    for f in sorted(glob.glob(str(fit_real.parent / "*.fit"))):
        s = {x.name: x.value for x in next(FitFile(f).get_messages("session"))}
        if s.get("total_timer_time") and s["total_elapsed_time"] - s["total_timer_time"] > 60:
            con_pausas = (f, s)
            break
    if con_pausas is None:
        pytest.skip("no hay ningun .fit con pausas en data/")

    ruta, sesion = con_pausas
    carrera, _ = fit.leer(ruta)
    assert carrera.duracion_segundos == int(sesion["total_timer_time"])
    assert carrera.duracion_segundos < int(sesion["total_elapsed_time"])


def test_lee_potencia_y_contacto_con_el_suelo(fit_real):
    """Dos series que no tiene ninguna otra fuente."""
    _, muestreos = fit.leer(str(fit_real))
    potencia = [m.potencia_vatios for m in muestreos if m.potencia_vatios]
    contacto = [m.tiempo_contacto_ms for m in muestreos if m.tiempo_contacto_ms]
    assert len(potencia) > len(muestreos) * 0.9
    assert len(contacto) > len(muestreos) * 0.9
    assert all(50 < p < 900 for p in potencia)        # vatios de correr
    assert all(150 < c < 600 for c in contacto)       # milisegundos de apoyo


def test_las_zonas_de_fc_vienen_del_reloj(tmp_path, fit_real):
    """El .fit las trae calculadas; deducirlas aqui exigiria saber la FCMax.

    El primero de los seis cubos es el tiempo por debajo de la zona 1 y no es
    una zona: si se colase, la suma no cuadraria con la duracion.
    """
    carrera, _ = fit.leer(str(fit_real))
    assert len(carrera.zonas_fc) == 5

    conn = db.conectar(tmp_path / "z.db")
    fit.importar(conn, str(fit_real))
    filas = conn.execute(
        "SELECT zona, segundos FROM zona_fc ORDER BY zona").fetchall()
    assert filas and all(1 <= f["zona"] <= 5 for f in filas)
    assert all(f["segundos"] > 0 for f in filas)
    # Las zonas cubren la carrera entera salvo el tiempo por debajo de la 1.
    total = sum(f["segundos"] for f in filas)
    assert 0.9 < total / carrera.duracion_segundos <= 1.05
