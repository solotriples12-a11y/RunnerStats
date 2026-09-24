"""Tests del parser de .fit de Strava contra las dos carreras de cinta reales.

Como en el del Amazfit, se contrasta con el mensaje `session` del propio
fichero.
"""

from fitparse import FitFile

from runnerstats import db
from runnerstats.importers import strava_fit as strava


def _sesion(ruta):
    s = next(FitFile(str(ruta)).get_messages("session"))
    return {c.name: c.value for c in s}


def test_se_distingue_del_fit_del_amazfit(fits_strava, fit_real):
    assert all(strava.parece_strava(f.read_bytes()) for f in fits_strava)
    assert not strava.parece_strava(fit_real.read_bytes())


def test_resumen_cuadra_con_la_sesion(fits_strava):
    for ruta in fits_strava:
        carrera, muestreos = strava.leer(str(ruta))
        s = _sesion(ruta)
        assert carrera.distancia_metros == s["total_distance"] == 5000
        assert carrera.duracion_segundos == int(s["total_elapsed_time"])
        assert carrera.fc_media == s["avg_heart_rate"]
        assert carrera.fuente == "strava_fit"
        # La sesión no trae la máxima: sale de los pulsos guardados.
        assert carrera.fc_maxima == max(m.frecuencia_cardiaca for m in muestreos
                                        if m.frecuencia_cardiaca)


def test_un_muestreo_cada_5_s_con_instantes_distintos(fits_strava):
    """La tanda de solo velocidad lleva todos el instante de inicio; si se
    guardara tal cual chocaría con la clave de `muestreo`."""
    for ruta in fits_strava:
        _, muestreos = strava.leer(str(ruta))
        instantes = [m.timestamp_unix for m in muestreos]
        assert len(set(instantes)) == len(instantes) > 390
        pasos = [b - a for a, b in zip(instantes, instantes[1:])]
        assert sorted(pasos)[len(pasos) // 2] == 5


def test_velocidad_emparejada_sin_el_relleno(fits_strava):
    """Integrada, la velocidad se pasa un 2 % de los 5 km: es la del sensor,
    no una serie ajustada al total."""
    for ruta in fits_strava:
        _, muestreos = strava.leer(str(ruta))
        velocidades = [m.velocidad_ms for m in muestreos]
        assert None not in velocidades
        assert max(velocidades) < 5
        assert 5000 < sum(velocidades) * 5 < 5150


def test_sin_distancia_por_punto(fits_strava):
    """Cinta: no se inventa una serie de distancia (DECISIONS.md 2026-09-06)."""
    _, muestreos = strava.leer(str(fits_strava[0]))
    assert all(m.distancia_acumulada_metros is None for m in muestreos)


def test_cadencia_en_pasos_por_minuto(fits_strava):
    _, muestreos = strava.leer(str(fits_strava[0]))
    cad = [m.cadencia_spm for m in muestreos if m.cadencia_spm]
    assert 140 < sum(cad) / len(cad) < 170


def test_importar_y_reimportar(tmp_path, fits_strava):
    conn = db.conectar(tmp_path / "strava.db")
    for _ in range(2):
        for ruta in fits_strava:
            strava.importar(conn, str(ruta))
    assert conn.execute("SELECT COUNT(*) FROM carrera").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM muestreo").fetchone()[0] == 397 + 393
