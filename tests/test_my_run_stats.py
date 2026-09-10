from datetime import datetime, timezone

from runnerstats import db
from runnerstats.importers import my_run_stats as mrs


def test_a_segundos():
    assert mrs.a_segundos("00:27:55") == 1675
    assert mrs.a_segundos("01:10:50") == 4250
    assert mrs.a_segundos("5:33") == 333


def test_lee_los_campos_que_importan(export_sintetico):
    carreras = mrs.leer(export_sintetico)
    assert len(carreras) == 2

    c = carreras[0]
    assert c.id == "my_run_stats:aaaa-1111"
    assert c.distancia_metros == 5030
    assert c.duracion_segundos == 1675
    assert c.fuente == "my_run_stats"

    fecha = datetime.fromtimestamp(c.fecha_inicio_unix, timezone.utc)
    assert (fecha.year, fecha.month, fecha.day) == (2026, 5, 4)


def test_sin_muestreos_ni_datos_de_fidelidad_alta(export_sintetico):
    """My Run Stats no aporta FC, desnivel ni dispositivo: quedan a None."""
    c = mrs.leer(export_sintetico)[0]
    assert c.fc_media is None
    assert c.fc_maxima is None
    assert c.desnivel_positivo_metros is None
    assert c.calorias is None


def test_ritmo_se_deriva_no_se_almacena(export_sintetico):
    """El `pace` del JSON se descarta; el ritmo se calcula."""
    c = mrs.leer(export_sintetico)[0]
    assert round(c.ritmo_seg_por_km) == 333  # 5:33, igual que el pace del JSON


def test_importar_escribe_en_sqlite(tmp_path, export_sintetico):
    conn = db.conectar(tmp_path / "test.db")
    assert len(mrs.importar(conn, export_sintetico)) == 2

    filas = conn.execute(
        "SELECT * FROM carrera ORDER BY fecha_inicio_unix DESC"
    ).fetchall()
    assert len(filas) == 2
    assert filas[0]["id"] == "my_run_stats:aaaa-1111"
    assert filas[0]["distancia_metros"] == 5030


def test_reimportar_no_duplica(tmp_path, export_sintetico):
    conn = db.conectar(tmp_path / "test.db")
    mrs.importar(conn, export_sintetico)
    mrs.importar(conn, export_sintetico)
    assert conn.execute("SELECT COUNT(*) FROM carrera").fetchone()[0] == 2


def test_no_se_crean_muestreos(tmp_path, export_sintetico):
    conn = db.conectar(tmp_path / "test.db")
    mrs.importar(conn, export_sintetico)
    assert conn.execute("SELECT COUNT(*) FROM muestreo").fetchone()[0] == 0
