"""Tests de la capa web. El foco está en la autenticación: la web sirve datos
de salud y no tiene ninguna parte pública."""

import io

import pytest

import app as webapp
from runnerstats import db
from runnerstats.importers import my_run_stats as mrs

PASSWORD = "secreto-de-prueba"


def _entrar(cliente, password: str = PASSWORD):
    """Inicia sesion por el formulario, como haria el navegador."""
    return cliente.post("/login", data={"password": password})


@pytest.fixture
def cliente_sin_sesion(tmp_path, export_sintetico, monkeypatch):
    ruta = tmp_path / "web.db"
    conn = db.conectar(ruta)
    mrs.importar(conn, export_sintetico)
    conn.close()
    monkeypatch.setattr(webapp, "RUTA_DB", str(ruta))
    monkeypatch.setenv("RUNNERSTATS_PASSWORD", PASSWORD)
    webapp.app.config["TESTING"] = True
    return webapp.app.test_client()


@pytest.fixture
def cliente(cliente_sin_sesion):
    _entrar(cliente_sin_sesion)
    return cliente_sin_sesion


def test_sin_sesion_redirige_al_login(cliente_sin_sesion):
    r = cliente_sin_sesion.get("/")
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


def test_el_login_no_pide_usuario(cliente_sin_sesion):
    html = cliente_sin_sesion.get("/login").get_data(as_text=True)
    assert 'name="password"' in html
    assert 'name="usuario"' not in html and 'name="username"' not in html


def test_password_incorrecta(cliente_sin_sesion):
    r = cliente_sin_sesion.post("/login", data={"password": "otra"})
    assert r.status_code == 401
    assert "Contraseña incorrecta" in r.get_data(as_text=True)
    assert cliente_sin_sesion.get("/").status_code == 302


def test_password_correcta_da_sesion(cliente_sin_sesion):
    r = _entrar(cliente_sin_sesion)
    assert r.status_code == 302
    assert cliente_sin_sesion.get("/").status_code == 200


def test_el_next_solo_admite_rutas_internas(cliente_sin_sesion):
    """Un `next` absoluto convertiria el login en un redirector abierto."""
    r = cliente_sin_sesion.post("/login?next=https://evil.example/x",
                                data={"password": PASSWORD})
    assert r.headers["Location"] in ("/", "http://localhost/")
    r = cliente_sin_sesion.post("/login?next=//evil.example",
                                data={"password": PASSWORD})
    assert "evil.example" not in r.headers["Location"]


def test_salir_cierra_la_sesion(cliente):
    assert cliente.get("/").status_code == 200
    cliente.post("/salir")
    assert cliente.get("/").status_code == 302


def test_sin_password_configurada_no_entra_nadie(cliente_sin_sesion, monkeypatch):
    """Falla cerrado: si falta la variable de entorno, nadie pasa.

    Lo contrario (abrir la web cuando no hay password) publicaria el
    historico entero en internet por un despiste de configuracion.
    """
    monkeypatch.setenv("RUNNERSTATS_PASSWORD", "")
    assert cliente_sin_sesion.get("/").status_code == 503
    assert cliente_sin_sesion.post("/login", data={"password": ""}).status_code == 503


def test_con_password_muestra_las_carreras(cliente):
    r = cliente.get("/")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "5.03 km" in html
    assert "3.54 km" in html
    # Los totales viven en las tarjetas, no en la cabecera.
    assert "Kilómetros" in html and "Carreras" in html


def test_marca_las_carreras_sin_detalle(cliente):
    """Ninguna carrera de My Run Stats tiene muestreos: no debe haber badge."""
    html = cliente.get("/").get_data(as_text=True)
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
    c = webapp.app.test_client()
    _entrar(c)
    return c


def _subir(cliente, contenido: bytes, nombre: str):
    return cliente.post(
        "/importar",
                data={"ficheros": (io.BytesIO(contenido), nombre)},
        content_type="multipart/form-data",
    )


def test_base_vacia_no_revienta(cliente_vacio):
    """Sin carreras los agregados de SQL son NULL y los filtros recibirian
    None. La portada tiene que seguir rindiendo."""
    r = cliente_vacio.get("/")
    assert r.status_code == 200
    assert "Todavía no hay ninguna carrera" in r.get_data(as_text=True)


def test_importar_requiere_sesion(cliente_sin_sesion):
    assert cliente_sin_sesion.get("/importar").status_code == 302
    assert cliente_sin_sesion.post("/importar").status_code == 302


def test_formulario_se_muestra(cliente):
    r = cliente.get("/importar")
    assert r.status_code == 200
    assert 'name="ficheros"' in r.get_data(as_text=True)


def test_subir_json_importa(cliente_vacio, export_sintetico):
    r = _subir(cliente_vacio, export_sintetico.read_bytes(), "export.json")
    assert r.status_code == 200
    assert "2 carreras importadas" in r.get_data(as_text=True)
    # Y ya se ven en la portada.
    assert "5.03 km" in cliente_vacio.get(
        "/").get_data(as_text=True)


def test_subir_fit_corrupto_da_error_y_no_entra_nada(cliente_vacio):
    r = _subir(cliente_vacio, b"\x0e\x10esto no es un fit", "carrera.fit")
    assert r.status_code == 200
    assert "no se pudo leer el .fit" in r.get_data(as_text=True)
    assert "Todavía no hay ninguna carrera" in cliente_vacio.get(
        "/").get_data(as_text=True)


def test_subir_fit_real_importa_con_muestreos(cliente_vacio, fit_real):
    r = _subir(cliente_vacio, fit_real.read_bytes(), fit_real.name)
    assert r.status_code == 200
    assert "1 carrera importada" in r.get_data(as_text=True)

    # Y en la portada aparece marcada como carrera con detalle.
    html = cliente_vacio.get("/").get_data(as_text=True)
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
    r = cliente.post("/importar",
                     data={}, content_type="multipart/form-data")
    assert "no has seleccionado" in r.get_data(as_text=True)


def test_la_lista_enlaza_al_detalle(cliente):
    """Se colo una vez: la sustitucion en la plantilla no coincidio por la
    indentacion y fallo en silencio, dejando las tarjetas sin enlace."""
    html = cliente.get("/").get_data(as_text=True)
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
                             ).get_data(as_text=True)
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
                       ).get_data(as_text=True)
    assert '<span class="uni">min</span>' in html


def test_los_records_llevan_el_ritmo_junto_al_tiempo(cliente_vacio, nike_dir):
    from runnerstats import dedup
    from runnerstats.importers import nike_tcx as nike
    conn = db.conectar(webapp.RUTA_DB)
    nike.importar(conn, str(nike_dir / "con-fc-y-gps.tcx"))
    dedup.marcar_duplicadas(conn)
    conn.close()

    html = cliente_vacio.get("/").get_data(as_text=True)
    assert 'class="record-linea"' in html
    # Tiempo y ritmo en el mismo contenedor, no en lineas separadas.
    bloque = html.split('class="record-linea"')[1].split("</span>\n            </span>")[0]
    assert "record-tiempo" in bloque and "record-ritmo" in bloque


def test_la_portada_solo_tiene_tres_tarjetas(cliente):
    html = cliente.get("/").get_data(as_text=True)
    assert html.count('class="tile"') == 3
    for etiqueta in ("Carreras", "Kilómetros", "Media por carrera"):
        assert etiqueta in html
    for fuera in ("Mejor ritmo", "FC media"):
        assert fuera not in html


def test_la_carrera_mas_larga_abre_los_records(cliente_vacio, nike_dir):
    from runnerstats import dedup
    from runnerstats.importers import nike_tcx as nike
    conn = db.conectar(webapp.RUTA_DB)
    nike.importar(conn, str(nike_dir / "con-fc-y-gps.tcx"))
    dedup.marcar_duplicadas(conn)
    conn.close()

    html = cliente_vacio.get("/").get_data(as_text=True)
    bloque = html.split('class="records"')[1]
    assert "Más larga" in bloque
    # Y va antes que cualquier record de distancia.
    assert bloque.index("Más larga") < bloque.index(">1K<")
    assert ">3K<" not in bloque
