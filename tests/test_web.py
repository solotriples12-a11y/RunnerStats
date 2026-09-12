"""Tests de la capa web. El foco está en la autenticación: la web sirve datos
de salud y no tiene ninguna parte pública."""

import io
import json
import re

import pytest

import app as webapp
from runnerstats import db, detalle
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


def test_la_lista_no_lleva_etiqueta_de_detalle(cliente):
    """Distinguia las carreras con muestreos de las que no, pero ya las
    tienen todas: la etiqueta era ruido en cada tarjeta."""
    html = cliente.get("/").get_data(as_text=True)
    assert 'class="run-card"' in html
    assert "has-detail" not in html and 'class="badge"' not in html


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


def _lineas(html: str) -> list[str]:
    """Cada línea de resultado de la importación tal como se lee: sin
    etiquetas y con los espacios de la plantilla colapsados."""
    return [" ".join(re.sub(r"<[^>]+>", "", b).split())
            for b in re.findall(r'<span class="detalle">(.*?)</span>', html, re.S)]


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


def test_el_selector_deja_elegir_todo_lo_que_la_web_lee(cliente):
    """La web lee .tcx desde que entró Nike, pero el selector se quedó en
    .json y .fit y el diálogo de ficheros no ofrecía los .tcx."""
    html = cliente.get("/importar").get_data(as_text=True)
    accept = re.search(r'accept="([^"]+)"', html).group(1)
    assert sorted(accept.split(",")) == [".fit", ".json", ".tcx"]


def test_subir_json_importa(cliente_vacio, export_sintetico):
    r = _subir(cliente_vacio, export_sintetico.read_bytes(), "export.json")
    assert r.status_code == 200
    assert _lineas(r.get_data(as_text=True)) == [
        "Importadas 2 carreras, del 20 ago 2024 al 4 may 2026: todas nuevas."]
    # Y ya se ven en la portada.
    assert "5.03 km" in cliente_vacio.get(
        "/").get_data(as_text=True)


def test_subir_fit_corrupto_da_error_y_no_entra_nada(cliente_vacio):
    r = _subir(cliente_vacio, b"\x0e\x10esto no es un fit", "carrera.fit")
    assert r.status_code == 200
    assert "No se ha importado: no se pudo leer el .fit" in r.get_data(as_text=True)
    assert "Todavía no hay ninguna carrera" in cliente_vacio.get(
        "/").get_data(as_text=True)


def test_subir_fit_real_importa_con_muestreos(cliente_vacio, fit_real):
    r = _subir(cliente_vacio, fit_real.read_bytes(), fit_real.name)
    assert r.status_code == 200
    assert _lineas(r.get_data(as_text=True)) == ["Importada: 2 sep 2026, 8.65 km."]

    # Y en la portada sale con la FC media, que solo sale de los muestreos.
    html = cliente_vacio.get("/").get_data(as_text=True)
    assert "148 ppm" in html


def test_json_corrupto_no_da_500(cliente_vacio):
    r = _subir(cliente_vacio, b"{esto no es json", "roto.json")
    assert r.status_code == 200
    assert "no es un JSON válido" in r.get_data(as_text=True)


def test_json_con_otra_forma_no_da_500(cliente_vacio):
    r = _subir(cliente_vacio, b'{"otra": "cosa"}', "ajeno.json")
    assert r.status_code == 200
    assert "no tiene la forma" in r.get_data(as_text=True)


def test_extension_no_soportada(cliente_vacio):
    r = _subir(cliente_vacio, b"lo que sea", "ruta.gpx")
    assert "formato no soportado" in r.get_data(as_text=True)


def test_subir_tcx_que_no_es_de_nike_da_error_claro(cliente_vacio):
    """El TCX que exporta Zepp está bien formado pero no es de Nike ni de
    Huawei, y salía como "no parece un TCX de Nike (falta la extension nax)"."""
    zepp = (b'<?xml version="1.0"?><TrainingCenterDatabase xmlns="http://'
            b'www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"><Activities>'
            b'<Activity Sport="Running"><Id>2026-09-02T06:06:24Z</Id></Activity>'
            b'</Activities></TrainingCenterDatabase>')
    for contenido in (zepp, b"<x/>"):
        r = _subir(cliente_vacio, contenido, "otro.tcx")
        assert r.status_code == 200
        assert _lineas(r.get_data(as_text=True)) == [
            "No se ha importado: no es un TCX de Nike ni de Huawei, que son los "
            "que se leen; si es del Amazfit, sube el .fit."]


def test_sin_seleccionar_nada(cliente):
    r = cliente.post("/importar",
                     data={}, content_type="multipart/form-data")
    assert "no has seleccionado" in r.get_data(as_text=True)


def _mrs_bytes(fecha: str, km: float, ident: str) -> bytes:
    """Un export de My Run Stats de una sola carrera, para subir por la web."""
    return json.dumps({
        "app": "My Run Stats", "version": 1, "count": 1,
        "runs": [{"id": ident, "date": fecha, "duration": "00:25:00",
                  "distance": km, "pace": "5:00", "km_splits": None}],
    }).encode()


def test_subir_una_carrera_dice_cual_y_nada_de_duplicadas(cliente_vacio):
    """El caso de la captura del 10 de septiembre: la base ya tenía carreras
    juntadas de importaciones anteriores, y al subir un .fit que no chocaba
    con nada salía "206 duplicadas entre fuentes, ocultas". Era el total de la
    base y no decía nada de lo subido."""
    _subir(cliente_vacio, _mrs_bytes("2026-05-04", 5.03, "a"), "a.json")
    _subir(cliente_vacio, _mrs_bytes("2026-05-04", 5.05, "b"), "b.json")
    html = _subir(cliente_vacio, _mrs_bytes("2026-06-01", 7.00, "c"),
                  "c.json").get_data(as_text=True)
    assert _lineas(html) == ["Importada: 1 jun 2026, 7.00 km."]
    assert 'href="/carrera/my_run_stats:c"' in html
    assert "duplicada" not in html


def test_la_que_ya_tenias_de_otra_fuente_se_junta_y_se_dice(cliente_vacio,
                                                           huawei_sintetico):
    """El Huawei sintético trae una carrera el 25 de marzo y otra de cinta el
    26. La de My Run Stats del 25 es la misma carrera apuntada en otra app."""
    html = _subir(cliente_vacio, huawei_sintetico.read_bytes(),
                  "huawei.json").get_data(as_text=True)
    assert _lineas(html) == [
        "Importadas 2 carreras, del 25 mar 2026 al 26 mar 2026: todas nuevas."]

    html = _subir(cliente_vacio, _mrs_bytes("2026-03-25", 5.00, "a"),
                  "a.json").get_data(as_text=True)
    assert _lineas(html) == ["Importada: 25 mar 2026, 5.00 km. Ya la tenías "
                             "de Huawei: se juntan en una sola carrera."]
    # El enlace lleva a la versión que se ve, la de Huawei, que trae muestreos.
    assert 'href="/carrera/huawei_json:1774422857"' in html

    html = _subir(cliente_vacio, _mrs_bytes("2026-03-25", 5.00, "a"),
                  "a.json").get_data(as_text=True)
    assert _lineas(html) == ["Ya estaba importada: 25 mar 2026, 5.00 km."]

    html = _subir(cliente_vacio, huawei_sintetico.read_bytes(),
                  "huawei.json").get_data(as_text=True)
    assert _lineas(html) == ["Importadas 2 carreras, del 25 mar 2026 al "
                             "26 mar 2026: ya las tenías todas."]


def test_una_tanda_cuenta_cada_carrera_una_vez(cliente_vacio, export_sintetico):
    """El export de Huawei trae cada actividad tres veces repartida entre
    ficheros: la segunda copia no es una carrera nueva. Y la del 4 de mayo del
    sintético de My Run Stats es la misma que la del primer fichero."""
    a = _mrs_bytes("2026-05-04", 5.03, "a")
    r = cliente_vacio.post("/importar", data={"ficheros": [
        (io.BytesIO(a), "a.json"),
        (io.BytesIO(a), "copia.json"),
        (io.BytesIO(export_sintetico.read_bytes()), "export.json"),
        (io.BytesIO(b"[]"), "vacio.json"),
    ]}, content_type="multipart/form-data")
    assert _lineas(r.get_data(as_text=True)) == [
        "Importada: 4 may 2026, 5.03 km.",
        "Ya estaba importada: 4 may 2026, 5.03 km.",
        "Importadas 2 carreras, del 20 ago 2024 al 4 may 2026: 1 nueva y 1 que ya tenías.",
        "No se ha importado nada: el fichero no trae ninguna carrera.",
    ]


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
    detalle.recalcular_records(conn)
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
    detalle.recalcular_records(conn)
    conn.close()

    html = cliente_vacio.get("/").get_data(as_text=True)
    bloque = html.split('class="records"')[1]
    assert "Más larga" in bloque
    # Y va antes que cualquier record de distancia.
    assert bloque.index("Más larga") < bloque.index(">1K<")
    assert ">3K<" not in bloque


def test_al_filtrar_un_año_el_grafico_pasa_a_meses(cliente):
    """El export sintetico solo tiene una carrera en 2026, en mayo."""
    html = cliente.get("/?anio=2026").get_data(as_text=True)
    assert 'class="chip on">Mes<' in html
    # Agrupar por año con un año elegido pintaria los quince: el chip se va.
    assert ">Año<" not in html

    barras = html.split('aria-label="Kilómetros recorridos por periodo"')[1]
    # El eje llega a diciembre aunque no se corriera despues de mayo.
    assert ">dic<" in barras


def test_sin_filtro_se_sigue_agrupando_por_anio(cliente):
    html = cliente.get("/").get_data(as_text=True)
    assert 'class="chip on">Año<' in html


def test_forzar_agr_anio_con_un_año_elegido_no_cuela(cliente):
    """Por URL se podia pedir la vista de quince años dentro de un filtro."""
    html = cliente.get("/?anio=2026&agr=anio").get_data(as_text=True)
    assert 'class="chip on">Mes<' in html


def test_la_evolucion_del_ritmo_solo_pinta_el_año(cliente):
    """El sintetico tiene una carrera en 2024 y otra en 2026: con 2026
    filtrado queda un solo punto y no hay evolución que dibujar."""
    assert "Evolución del ritmo" in cliente.get("/").get_data(as_text=True)
    assert "Evolución del ritmo" not in cliente.get(
        "/?anio=2026").get_data(as_text=True)


def test_la_evolucion_de_la_distancia_va_antes_que_la_del_ritmo(cliente):
    html = cliente.get("/").get_data(as_text=True)
    assert html.index("Evolución de la distancia") < html.index("Evolución del ritmo")
    nube = html.split("Evolución de la distancia")[1].split("</svg>")[0]
    # Las dos carreras del sintético y la mediana de cada año, cada marca con
    # su zona de dedo.
    assert nube.count('class="punto"') == 2 and nube.count('class="nodo"') == 2
    assert nube.count('class="zona"') == nube.count('class="marca"') == 4
    assert 'data-tip="2026-05-04 · 5.03 km · 27:55"' in nube
    assert 'data-tip="Mediana 2024: 3.5 km"' in nube
    # Con un solo punto en 2026 no hay evolución que dibujar.
    assert "Evolución de la distancia" not in cliente.get(
        "/?anio=2026").get_data(as_text=True)


def test_las_marcas_llevan_el_dato_encima_y_no_un_title(cliente):
    """El <title> de SVG lo pinta el navegador con un segundo de retardo y en
    tactil no aparece nunca. El dato va en data-tip y lo pinta el JS."""
    html = cliente.get("/?anio=2026").get_data(as_text=True)
    assert html.count("<title>") == 1, "solo el de la cabecera del documento"
    assert "js/tip.js" in html

    # Una banda por mes, con su zona sensible, tenga carreras o no.
    assert html.count('class="banda"') == 12
    assert html.count('class="zona"') == 12
    assert 'data-tip="may: 5.0 km en 1 carrera"' in html
    assert 'data-tip="ene: sin carreras"' in html


def test_los_puntos_del_ritmo_tienen_blanco_de_dedo(cliente):
    html = cliente.get("/").get_data(as_text=True)
    nube = html.split("Evolución del ritmo")[1]
    # Cada punto visible de 3 px va dentro de una marca con su zona ancha.
    assert nube.count('class="marca"') == nube.count('class="punto"') + \
        nube.count('class="nodo"')
    assert nube.count('class="zona"') == nube.count('class="marca"')


def test_el_favicon_esta_declarado_y_se_sirve(cliente_sin_sesion):
    """El login tambien lo lleva: es la primera pagina que se ve, y el icono
    se sirve sin sesion porque `static` es publico."""
    for ruta, entrar_antes in (("/login", False), ("/", True)):
        if entrar_antes:
            _entrar(cliente_sin_sesion)
        html = cliente_sin_sesion.get(ruta).get_data(as_text=True)
        assert 'rel="icon" href="/static/favicon.ico"' in html, ruta
        assert 'rel="apple-touch-icon"' in html, ruta

    r = cliente_sin_sesion.get("/static/favicon.ico")
    assert r.status_code == 200
    assert r.data[:4] == b"\x00\x00\x01\x00"   # cabecera ICO


def test_las_barras_llevan_a_su_periodo(cliente):
    """Tocar una barra filtra: al año, al mes, o al detalle de la carrera."""
    import re
    def enlaces(agr):
        html = cliente.get(f"/?agr={agr}").get_data(as_text=True)
        return re.findall(r'<a class="banda" href="([^"]+)"', html)

    assert all(e.startswith("/?anio=") for e in enlaces("anio"))
    assert all(e.startswith("/periodo/mes/") for e in enlaces("mes"))
    assert all(e.startswith("/periodo/semana/") for e in enlaces("semana"))
    # El sintetico tiene una carrera en mayo de 2026 y otra en agosto de 2024.
    assert sorted(enlaces("mes")) == ["/periodo/mes/2024-08", "/periodo/mes/2026-05"]
    # Agrupando por carrera se va directo a su detalle.
    assert all(e.startswith("/carrera/") for e in enlaces("carrera"))


def test_un_periodo_vacio_no_es_clicable(cliente):
    """2025 no tiene carreras: su barra existe pero no lleva a ningun sitio."""
    html = cliente.get("/?agr=anio").get_data(as_text=True)
    assert '<g class="banda"' in html          # sin href
    assert "/?anio=2025" not in html


def test_la_pagina_de_un_mes_lista_solo_ese_mes(cliente):
    r = cliente.get("/periodo/mes/2026-05")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Mayo de 2026" in html
    assert html.count('class="run-card"') == 1
    assert "5.03 km" in html and "3.54 km" not in html
    # Y se vuelve al año, que es la vista con el resto del contexto.
    assert 'href="/?anio=2026"' in html


def test_un_periodo_sin_carreras_lo_dice(cliente):
    html = cliente.get("/periodo/mes/2026-06").get_data(as_text=True)
    assert "No hay ninguna carrera" in html
    assert 'class="run-card"' not in html


def test_periodos_que_no_existen_dan_404(cliente):
    # El año tiene su propia vista, la portada filtrada.
    assert cliente.get("/periodo/anio/2026").status_code == 404
    assert cliente.get("/periodo/mes/2026-13").status_code == 404
    assert cliente.get("/periodo/mes/pepe").status_code == 404
    # Las semanas empiezan en lunes; 2026-05-05 es martes.
    assert cliente.get("/periodo/semana/2026-05-05").status_code == 404


def test_la_pagina_de_periodo_pide_sesion(cliente_sin_sesion):
    r = cliente_sin_sesion.get("/periodo/mes/2026-05")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_la_web_distingue_el_tcx_de_huawei_del_de_nike(cliente_vacio, huawei_dir):
    """Los dos exportan en TCX y comparten extension."""
    tcx = sorted(huawei_dir.glob("*.tcx"))
    if not tcx:
        pytest.skip("no hay TCX de Huawei en data/huawei")
    r = _subir(cliente_vacio, tcx[0].read_bytes(), "carrera de prueba.tcx")
    assert _lineas(r.get_data(as_text=True))[0].startswith("Importada: ")

    conn = db.conectar(webapp.RUTA_DB)
    fuentes = [x[0] for x in conn.execute("SELECT fuente FROM carrera")]
    conn.close()
    assert fuentes == ["huawei_tcx"]


def test_la_web_reconoce_el_tcx_de_nike(cliente_vacio, nike_dir):
    """Se decide por la firma antes de parsear, como con el de Huawei."""
    r = _subir(cliente_vacio, (nike_dir / "con-fc-y-gps.tcx").read_bytes(),
               "nike.tcx")
    assert _lineas(r.get_data(as_text=True))[0].startswith("Importada: ")


def test_la_carrera_del_fit_enseña_esfuerzo_potencia_y_contacto(cliente_vacio, fit_real):
    """Los tres bloques que solo puede llenar el .fit del Amazfit."""
    _subir(cliente_vacio, fit_real.read_bytes(), fit_real.name)
    conn = db.conectar(webapp.RUTA_DB)
    cid = conn.execute("SELECT id FROM carrera").fetchone()[0]
    conn.close()

    html = cliente_vacio.get(f"/carrera/{cid}").get_data(as_text=True)
    assert ">Esfuerzo<" in html and 'class="zona-punto"' in html
    assert ">Potencia" in html and "Contacto con el suelo" in html
    # Los parciales van antes que el esfuerzo, y este antes que las graficas.
    assert html.index(">Parciales<") < html.index(">Esfuerzo<") < html.index(">Ritmo<")


def test_una_carrera_sin_fit_no_enseña_esos_bloques(cliente_vacio, nike_dir):
    """La regla del proyecto: la interfaz dice de que subconjunto habla."""
    from runnerstats.importers import nike_tcx as nike
    conn = db.conectar(webapp.RUTA_DB)
    nike.importar(conn, str(nike_dir / "con-fc-y-gps.tcx"))
    cid = conn.execute("SELECT id FROM carrera").fetchone()[0]
    conn.close()

    html = cliente_vacio.get(f"/carrera/{cid}").get_data(as_text=True)
    assert ">Esfuerzo<" not in html
    assert ">Potencia" not in html and "Contacto con el suelo" not in html
    # Pero las de siempre siguen ahi.
    assert ">Ritmo<" in html and "Frecuencia cardíaca" in html
