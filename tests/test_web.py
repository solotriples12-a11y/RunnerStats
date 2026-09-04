"""Tests de la capa web. El foco está en la autenticación: la web sirve datos
de salud y no tiene ninguna parte pública."""

import base64

import pytest

import app as webapp
from runnerstats import db
from runnerstats.importers import my_run_stats as mrs

PASSWORD = "secreto-de-prueba"


def _cabecera(password: str) -> dict:
    cred = base64.b64encode(f"javi:{password}".encode()).decode()
    return {"Authorization": f"Basic {cred}"}


@pytest.fixture
def cliente(tmp_path, export_sintetico, monkeypatch):
    ruta = tmp_path / "web.db"
    conn = db.conectar(ruta)
    mrs.importar(conn, export_sintetico)
    conn.close()

    monkeypatch.setattr(webapp, "RUTA_DB", str(ruta))
    monkeypatch.setenv("RUNNERSTATS_PASSWORD", PASSWORD)
    webapp.app.config["TESTING"] = True
    return webapp.app.test_client()


def test_sin_credenciales_401(cliente):
    r = cliente.get("/")
    assert r.status_code == 401
    assert "Basic" in r.headers["WWW-Authenticate"]


def test_password_incorrecta_401(cliente):
    assert cliente.get("/", headers=_cabecera("otra")).status_code == 401


def test_sin_password_configurada_no_entra_nadie(cliente, monkeypatch):
    """Falla cerrado: si falta la variable de entorno, nadie pasa.

    Lo contrario (abrir la web cuando no hay password) publicaría el
    histórico entero en internet por un despiste de configuración.
    """
    monkeypatch.setenv("RUNNERSTATS_PASSWORD", "")
    assert cliente.get("/", headers=_cabecera("")).status_code == 401
    assert cliente.get("/", headers=_cabecera(PASSWORD)).status_code == 401


def test_con_password_muestra_las_carreras(cliente):
    r = cliente.get("/", headers=_cabecera(PASSWORD))
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "5.03 km" in html
    assert "3.54 km" in html
    assert "2 carreras" in html


def test_marca_las_carreras_sin_detalle(cliente):
    """Ninguna carrera de My Run Stats tiene muestreos: no debe haber badge."""
    html = cliente.get("/", headers=_cabecera(PASSWORD)).get_data(as_text=True)
    assert 'class="run-card"' in html
    assert "has-detail" not in html
