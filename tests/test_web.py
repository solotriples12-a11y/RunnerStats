"""Tests de la capa web. El foco está en la autenticación: la web sirve datos
de salud y no tiene ninguna parte pública."""

import base64
import io

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
    # Los totales viven en las tarjetas, no en la cabecera.
    assert "Kilómetros" in html and "Carreras" in html


def test_marca_las_carreras_sin_detalle(cliente):
    """Ninguna carrera de My Run Stats tiene muestreos: no debe haber badge."""
    html = cliente.get("/", headers=_cabecera(PASSWORD)).get_data(as_text=True)
    assert 'class="run-card"' in html
    assert "has-detail" not in html


@pytest.fixture
def cliente_vacio(tmp_path, monkeypatch):
    """Base sin ninguna carrera: es el estado con el que nace produccion."""
    ruta = tmp_path / "vacia.db"
    db.conectar(ruta).close()
    monkeypatch.setattr(webapp, "RUTA_DB", str(ruta))
    monkeypatch.setenv("RUNNERSTATS_PASSWORD", PASSWORD)
    webapp.app.config["TESTING"] = True
    return webapp.app.test_client()


def _subir(cliente, contenido: bytes, nombre: str):
    return cliente.post(
        "/importar",
        headers=_cabecera(PASSWORD),
        data={"ficheros": (io.BytesIO(contenido), nombre)},
        content_type="multipart/form-data",
    )


def test_base_vacia_no_revienta(cliente_vacio):
    """Sin carreras los agregados de SQL son NULL y los filtros recibirian
    None. La portada tiene que seguir rindiendo."""
    r = cliente_vacio.get("/", headers=_cabecera(PASSWORD))
    assert r.status_code == 200
    assert "Todavía no hay ninguna carrera" in r.get_data(as_text=True)


def test_importar_requiere_auth(cliente):
    assert cliente.get("/importar").status_code == 401
    assert cliente.post("/importar").status_code == 401


def test_formulario_se_muestra(cliente):
    r = cliente.get("/importar", headers=_cabecera(PASSWORD))
    assert r.status_code == 200
    assert 'name="ficheros"' in r.get_data(as_text=True)


def test_subir_json_importa(cliente_vacio, export_sintetico):
    r = _subir(cliente_vacio, export_sintetico.read_bytes(), "export.json")
    assert r.status_code == 200
    assert "2 carreras importadas" in r.get_data(as_text=True)
    # Y ya se ven en la portada.
    assert "5.03 km" in cliente_vacio.get(
        "/", headers=_cabecera(PASSWORD)).get_data(as_text=True)


def test_subir_fit_corrupto_da_error_y_no_entra_nada(cliente_vacio):
    r = _subir(cliente_vacio, b"\x0e\x10esto no es un fit", "carrera.fit")
    assert r.status_code == 200
    assert "no se pudo leer el .fit" in r.get_data(as_text=True)
    assert "Todavía no hay ninguna carrera" in cliente_vacio.get(
        "/", headers=_cabecera(PASSWORD)).get_data(as_text=True)


def test_subir_fit_real_importa_con_muestreos(cliente_vacio, fit_real):
    r = _subir(cliente_vacio, fit_real.read_bytes(), fit_real.name)
    assert r.status_code == 200
    assert "1 carrera importada" in r.get_data(as_text=True)

    # Y en la portada aparece marcada como carrera con detalle.
    html = cliente_vacio.get("/", headers=_cabecera(PASSWORD)).get_data(as_text=True)
    assert "has-detail" in html
    assert "148 ppm" in html


def test_json_corrupto_no_da_500(cliente_vacio):
    r = _subir(cliente_vacio, b"{esto no es json", "roto.json")
    assert r.status_code == 200
    assert "no es un JSON valido" in r.get_data(as_text=True)


def test_json_con_otra_forma_no_da_500(cliente_vacio):
    r = _subir(cliente_vacio, b'{"otra": "cosa"}', "ajeno.json")
    assert r.status_code == 200
    assert "no tiene la forma" in r.get_data(as_text=True)


def test_extension_no_soportada(cliente_vacio):
    r = _subir(cliente_vacio, b"lo que sea", "ruta.gpx")
    assert "formato no soportado" in r.get_data(as_text=True)


def test_subir_tcx_que_no_es_de_nike_da_error_claro(cliente_vacio):
    r = _subir(cliente_vacio, b"<x/>", "otro.tcx")
    assert r.status_code == 200
    assert "XML invalido" in r.get_data(as_text=True) or \
           "no parece un TCX de Nike" in r.get_data(as_text=True)


def test_sin_seleccionar_nada(cliente):
    r = cliente.post("/importar", headers=_cabecera(PASSWORD),
                     data={}, content_type="multipart/form-data")
    assert "no has seleccionado" in r.get_data(as_text=True)


def test_un_anio_sin_carreras_largas_no_revienta(tmp_path, monkeypatch):
    """`mejor_ritmo` solo mira carreras de 3 km o mas y puede ser None.

    Sin guarda, el filtro de ritmo recibia None y devolvia un 500.
    """
    import json

    ruta = tmp_path / "cortas.db"
    export = tmp_path / "cortas.json"
    export.write_text(json.dumps({
        "app": "My Run Stats", "version": 1, "count": 1,
        "runs": [{"id": "c1", "date": "2020-01-05", "duration": "00:10:00",
                  "distance": 1.5, "pace": "6:40", "km_splits": None}],
    }))
    conn = db.conectar(ruta)
    mrs.importar(conn, export)
    conn.close()

    monkeypatch.setattr(webapp, "RUTA_DB", str(ruta))
    monkeypatch.setenv("RUNNERSTATS_PASSWORD", PASSWORD)
    webapp.app.config["TESTING"] = True
    r = webapp.app.test_client().get("/", headers=_cabecera(PASSWORD))
    assert r.status_code == 200
    assert "Mejor ritmo" in r.get_data(as_text=True)


def test_el_detalle_requiere_auth(cliente):
    assert cliente.get("/carrera/loquesea").status_code == 401


def test_detalle_de_carrera_inexistente_da_404(cliente):
    r = cliente.get("/carrera/no-existe", headers=_cabecera(PASSWORD))
    assert r.status_code == 404


def test_detalle_de_una_carrera_solo_resumen(cliente):
    """Las de My Run Stats no tienen muestreos: la pagina debe decirlo en vez
    de enseñar graficas vacias."""
    cid = "my_run_stats:aaaa-1111"
    r = cliente.get(f"/carrera/{cid}", headers=_cabecera(PASSWORD))
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "solo tiene resumen" in html
    assert "5.03" in html


def test_detalle_completo(cliente_vacio, nike_dir):
    from runnerstats.importers import nike_tcx as nike
    conn = db.conectar(webapp.RUTA_DB)
    nike.importar(conn, str(nike_dir / "con-fc-y-gps.tcx"))
    cid = conn.execute("SELECT id FROM carrera").fetchone()["id"]
    conn.close()

    html = cliente_vacio.get(f"/carrera/{cid}",
                             headers=_cabecera(PASSWORD)).get_data(as_text=True)
    for seccion in ("Ritmo", "Frecuencia cardíaca", "Parciales"):
        assert seccion in html, f"falta la seccion {seccion}"
    # El recorrido es la miniatura de la cabecera, no una seccion.
    assert 'class="ruta-mini"' in html
    assert html.count('class="traza"') == 1
    # Duracion, distancia y ritmo van en la cabecera, no en tarjetas.
    assert 'class="cab-cifras"' in html
    assert "cifra-grande" in html and "cifra-media" in html
    assert 'class="tile"' not in html
    # La FC acompaña al titulo de su grafica.
    assert 'class="h2-extra"' in html
    assert "solo tiene resumen" not in html


def test_la_lista_enlaza_al_detalle(cliente):
    """Se colo una vez: la sustitucion en la plantilla no coincidio por la
    indentacion y fallo en silencio, dejando las tarjetas sin enlace."""
    html = cliente.get("/", headers=_cabecera(PASSWORD)).get_data(as_text=True)
    assert 'href="/carrera/' in html
    assert "<article class=\"run-card" not in html


def test_una_carrera_de_cinta_no_enseña_altitud_ni_ritmo(cliente_vacio, nike_dir):
    """Sin GPS no hay ritmo ni recorrido, y la altitud llega como -1 fijo."""
    import glob
    from runnerstats.importers import nike_tcx as nike
    conn = db.conectar(webapp.RUTA_DB)

    # Cualquier TCX de los de muestra que no traiga GPS.
    cid = None
    for f in glob.glob(str(nike_dir / "*.tcx")):
        try:
            car, ms = nike.leer(f)
        except Exception:
            continue
        if ms and not any(m.latitud for m in ms) and any(m.frecuencia_cardiaca for m in ms):
            nike.importar(conn, f); cid = car.id; break
    conn.close()
    if cid is None:
        pytest.skip("no hay ninguna muestra sin GPS")

    html = cliente_vacio.get(f"/carrera/{cid}",
                             headers=_cabecera(PASSWORD)).get_data(as_text=True)
    assert ">Altitud" not in html
    assert ">Ritmo" not in html
    assert 'class="ruta-mini"' not in html
    assert "Frecuencia cardíaca" in html


def test_la_duracion_lleva_su_unidad_mayor(cliente):
    """Como el km: 'h' si pasa de la hora, 'min' si no."""
    assert webapp.f_unidad_duracion(3599) == "min"
    assert webapp.f_unidad_duracion(3600) == "h"
    assert webapp.f_unidad_duracion(7200) == "h"

    # 00:27:55 en el export sintetico -> min
    html = cliente.get("/carrera/my_run_stats:aaaa-1111",
                       headers=_cabecera(PASSWORD)).get_data(as_text=True)
    assert '<span class="uni">min</span>' in html
