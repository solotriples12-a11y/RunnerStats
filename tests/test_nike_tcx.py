"""Tests del importador de Nike contra ficheros reales del export."""

import pytest

from runnerstats import db, dedup
from runnerstats.importers import nike_tcx as nike


def test_lee_resumen_y_muestreos(nike_dir):
    c, m = nike.leer(str(nike_dir / "con-fc-y-gps.tcx"))
    assert c.fuente == "nike_tcx"
    assert c.dispositivo == "Nike Run Club"
    assert c.distancia_metros > 0 and c.duracion_segundos > 0
    assert c.fc_media and c.fc_maxima and c.fc_maxima >= c.fc_media
    assert any(x.frecuencia_cardiaca for x in m)
    assert any(x.latitud for x in m)


def test_la_cadencia_no_se_dobla(nike_dir):
    """Nike ya da pasos por minuto; el .fit del Amazfit viene por pierna.

    Misma etiqueta `Cadence`, convencion distinta. Doblar aqui daria ~300 spm.
    """
    _, m = nike.leer(str(nike_dir / "con-fc-y-gps.tcx"))
    cads = [x.cadencia_spm for x in m if x.cadencia_spm]
    assert cads, "el fichero de muestra deberia traer cadencia"
    media = sum(cads) / len(cads)
    assert 130 < media < 190, f"cadencia media {media:.0f}, fuera de rango humano"


def test_los_trackpoints_del_mismo_segundo_se_fusionan(nike_dir):
    """Nike escribe un punto por sensor con marca de milisegundos.

    La clave es (carrera, segundo): sin fusionar se perderia el 41 % en
    silencio, y ademas cada fila quedaria casi vacia.
    """
    _, m = nike.leer(str(nike_dir / "con-fc-y-gps.tcx"))
    ts = [x.timestamp_unix for x in m]
    assert len(ts) == len(set(ts)), "hay segundos repetidos: se pisarian al insertar"

    campos = sum(
        sum(v is not None for v in (x.distancia_acumulada_metros, x.frecuencia_cardiaca,
                                    x.cadencia_spm, x.velocidad_ms, x.altitud_metros,
                                    x.latitud))
        for x in m
    )
    assert campos / len(m) > 2, "la fusion deberia dejar >2 campos con dato por fila"


def test_deriva_la_distancia_del_gps_cuando_nike_no_la_da(nike_dir):
    """1 de las 269 carreras trae la traza pero DistanceMeters a 0."""
    c, m = nike.leer(str(nike_dir / "sin-distancia.tcx"))
    assert c.distancia_metros > 3000
    ritmo = c.duracion_segundos / (c.distancia_metros / 1000)
    assert 240 < ritmo < 600, f"ritmo derivado absurdo: {ritmo:.0f} s/km"
    acum = [x.distancia_acumulada_metros for x in m
            if x.distancia_acumulada_metros is not None]
    assert acum == sorted(acum), "la distancia derivada debe ser monotona"


def test_una_carrera_solo_resumen_tambien_entra(nike_dir):
    c, m = nike.leer(str(nike_dir / "solo-resumen.tcx"))
    assert c.distancia_metros > 0
    assert len(m) <= 5


def test_se_reconoce_por_su_extension(nike_dir):
    """La web decide por aquí antes de parsear, como con el `creator` de
    Huawei. Los 269 TCX del export declaran `nax`; ni los de Huawei ni el de
    Zepp la mencionan."""
    for f in nike_dir.glob("*.tcx"):
        assert nike.parece_nike(f.read_bytes()), f.name
    assert not nike.parece_nike(
        b'<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/'
        b'TrainingCenterDatabase/v2"/>')


def test_rechaza_un_tcx_que_no_es_de_nike(tmp_path):
    """Un TCX de Huawei tiene la misma forma y quedaria mal etiquetado."""
    f = tmp_path / "otro.tcx"
    f.write_text(
        '<?xml version="1.0"?><TrainingCenterDatabase '
        'xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">'
        "<Activities><Activity><Lap><DistanceMeters>1000</DistanceMeters>"
        "</Lap></Activity></Activities></TrainingCenterDatabase>")
    with pytest.raises(nike.TcxInvalido, match="nax"):
        nike.leer(str(f))


def test_importa_y_reimportar_no_duplica(tmp_path, nike_dir):
    conn = db.conectar(tmp_path / "n.db")
    nike.importar(conn, str(nike_dir / "con-fc-y-gps.tcx"))
    n1 = conn.execute("SELECT COUNT(*) FROM muestreo").fetchone()[0]
    nike.importar(conn, str(nike_dir / "con-fc-y-gps.tcx"))
    assert conn.execute("SELECT COUNT(*) FROM carrera").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM muestreo").fetchone()[0] == n1
