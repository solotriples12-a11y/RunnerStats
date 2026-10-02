"""Instalacion y recepcion de archivos: usa un FIT binario sin datos reales."""

import io
import struct
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

import pytest
from fitparse.records import Crc

import app as webapp
from runnerstats import db


@pytest.fixture
def fit_sintetico():
    """Una sesion running con tres record, las unidades y el CRC del FIT.

    Se codifican los mensajes del perfil FIT: session=18, record=20;
    tiempos en milisegundos, distancia en centimetros y epoch 1989-12-31.
    No sustituye la verificacion del importador contra exports reales.
    """
    def mensaje(local, numero, campos, formato, valores):
        definicion = struct.pack("<BBBHB", 0x40 | local, 0, 0, numero, len(campos))
        definicion += b"".join(bytes(campo) for campo in campos)
        return definicion + bytes([local]) + struct.pack(formato, *valores)

    inicio = int((datetime(2026, 10, 1, 8, tzinfo=timezone.utc)
                  - datetime(1989, 12, 31, tzinfo=timezone.utc)).total_seconds())
    datos = mensaje(0, 0, [(0, 1, 0), (1, 2, 0x84)], "<BH", [4, 1])
    datos += mensaje(1, 18, [(2, 4, 0x86), (5, 1, 0), (7, 4, 0x86),
                             (8, 4, 0x86), (9, 4, 0x86), (16, 1, 2), (17, 1, 2)],
                     "<IBIIIBB", [inicio, 1, 1800000, 1800000, 500000, 150, 165])
    for i in range(3):
        datos += mensaje(2, 20, [(253, 4, 0x86), (5, 4, 0x86), (3, 1, 2), (4, 1, 2)],
                         "<IIBB", [inicio + 900 * i, 250000 * i, 145 + 10 * i, 80])
    cabecera = struct.pack("<BBHI4s", 14, 0x10, 100, len(datos), b".FIT")
    cabecera += struct.pack("<H", Crc.calculate(cabecera))
    contenido = cabecera + datos
    return contenido + struct.pack("<H", Crc.calculate(contenido))


@pytest.fixture
def movil(tmp_path, monkeypatch):
    monkeypatch.setattr(webapp, "RUTA_DB", str(tmp_path / "compartir.db"))
    monkeypatch.setenv("RUNNERSTATS_PASSWORD", "solo-para-tests")
    webapp.app.config["TESTING"] = True
    return webapp.app.test_client()


def test_la_instalacion_es_publica_y_declara_los_formatos(movil):
    pagina = movil.get("/login").get_data(as_text=True)
    assert 'rel="manifest"' in pagina
    assert "js/instalar.js" in pagina
    respuesta = movil.get("/static/manifest.webmanifest")
    assert respuesta.status_code == 200
    manifiesto = respuesta.get_json(force=True)
    destino = manifiesto["share_target"]
    assert destino["method"] == "POST" and destino["enctype"] == "multipart/form-data"
    assert destino["action"] == "/compartir"
    archivo = destino["params"]["files"][0]
    assert archivo["name"] == "ficheros"
    assert {".fit", ".json", ".tcx", "application/octet-stream"} <= set(archivo["accept"])
    for icono in manifiesto["icons"]:
        assert movil.get(icono["src"]).status_code == 200
    worker = movil.get("/sw.js")
    assert worker.status_code == 200 and "javascript" in worker.content_type
    assert worker.headers["Cache-Control"] == "no-cache"


def test_el_login_conserva_el_destino_del_archivo(movil):
    destino = "/compartir?envio=identificador-del-movil"
    r = movil.get(destino)
    assert r.status_code == 302
    assert urlsplit(r.headers["Location"]).path == "/login"
    assert parse_qs(urlsplit(r.headers["Location"]).query)["next"] == [destino]
    r = movil.post(r.headers["Location"], data={"password": "solo-para-tests"})
    assert r.headers["Location"] == destino
    pagina = movil.get(destino)
    assert pagina.status_code == 200
    assert "js/compartir.js" in pagina.get_data(as_text=True)


def test_compartir_no_importa_sin_sesion(movil, fit_sintetico):
    r = movil.post("/compartir", data={"ficheros": (io.BytesIO(fit_sintetico), "carrera.fit")})
    assert r.status_code == 302 and "/login" in r.headers["Location"]
    conn = db.conectar(webapp.RUTA_DB)
    assert conn.execute("SELECT COUNT(*) FROM carrera").fetchone()[0] == 0
    conn.close()


def test_compartir_importa_un_fit_y_repetir_no_duplica(movil, fit_sintetico):
    movil.post("/login", data={"password": "solo-para-tests"})
    for texto in ("Importada:", "Ya estaba importada:"):
        r = movil.post("/compartir", data={"ficheros": (io.BytesIO(fit_sintetico), "carrera.fit")})
        assert r.status_code == 200
        assert texto in r.get_data(as_text=True)
    conn = db.conectar(webapp.RUTA_DB)
    carreras = conn.execute("SELECT * FROM carrera").fetchall()
    assert len(carreras) == 1
    assert carreras[0]["fuente"] == "amazfit_fit"
    assert carreras[0]["distancia_metros"] == 5000
    assert carreras[0]["fc_media"] == 150
    assert conn.execute("SELECT COUNT(*) FROM muestreo").fetchone()[0] == 3
    conn.close()


def test_compartir_respeta_el_limite_de_la_subida(movil, monkeypatch):
    movil.post("/login", data={"password": "solo-para-tests"})
    monkeypatch.setitem(webapp.app.config, "MAX_CONTENT_LENGTH", 200)
    r = movil.post("/compartir", data={"ficheros": (io.BytesIO(b"x" * 201), "grande.fit")})
    assert r.status_code == 413
    assert "64 MB" in r.get_data(as_text=True)


def test_un_fit_roto_compartido_muestra_el_motivo(movil):
    movil.post("/login", data={"password": "solo-para-tests"})
    r = movil.post("/compartir", data={"ficheros": (io.BytesIO(b"no es un FIT"), "roto.fit")})
    assert r.status_code == 200
    assert "No se ha importado:" in r.get_data(as_text=True)
