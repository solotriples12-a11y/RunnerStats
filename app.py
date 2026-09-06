import io
import json
import os
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import PurePath

from dotenv import load_dotenv
from fitparse.utils import FitParseError
from flask import (Flask, Response, abort, g, redirect, render_template,
                   request, url_for)

from runnerstats import analisis, auth, consultas, db, dedup, detalle, graficas
from runnerstats.importers import (amazfit_fit, huawei_json, huawei_tcx,
                                   my_run_stats, nike_tcx)

load_dotenv()

app = Flask(__name__)

# El export de Nike son 269 TCX y 152 MB en total, con ficheros sueltos de
# hasta 3,2 MB. 64 permite tandas comodas sin que una subida enorme agote la
# memoria del contenedor, que buferea la peticion entera.
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024

RUTA_DB = os.environ.get("RUNNERSTATS_DB") or "data/runnerstats.db"

MESES = ("ene", "feb", "mar", "abr", "may", "jun",
         "jul", "ago", "sep", "oct", "nov", "dic")


PUBLICAS = {"login", "static"}


@app.before_request
def _exigir_auth():
    """Toda la web va detrás de sesión.

    Aquí no hay ninguna parte pública: son 15 años de entrenamientos,
    frecuencia cardíaca y trazas GPS del domicilio. Por eso el guard es
    global y no ruta por ruta.

    Falla cerrado: sin `RUNNERSTATS_PASSWORD` configurada no se sirve nada.
    """
    if request.endpoint in PUBLICAS:
        return None
    if not auth.configurada():
        return Response("Auth no configurada", 503)
    if auth.sesion_valida(request.cookies.get(auth.COOKIE)):
        return None
    destino = request.full_path if request.query_string else request.path
    return redirect(url_for("login", next=destino))


@app.route("/login", methods=["GET", "POST"])
def login():
    if not auth.configurada():
        return Response("Auth no configurada", 503)

    siguiente = request.args.get("next", "/")
    # Solo rutas internas: un `next` absoluto seria un redirector abierto.
    if not siguiente.startswith("/") or siguiente.startswith("//"):
        siguiente = "/"

    if request.method == "GET":
        if auth.sesion_valida(request.cookies.get(auth.COOKIE)):
            return redirect(siguiente)
        return render_template("login.html", error=None)

    if not auth.password_correcta(request.form.get("password", "")):
        return render_template("login.html", error="Contraseña incorrecta"), 401

    resp = redirect(siguiente)
    resp.set_cookie(
        auth.COOKIE, auth.token(),
        max_age=60 * 60 * 24 * auth.DIAS,
        httponly=True,
        samesite="Lax",
        # Detras de Traefik la peticion llega por HTTP; la cabecera dice si
        # el cliente venia por HTTPS.
        secure=request.headers.get("X-Forwarded-Proto", request.scheme) == "https",
    )
    return resp


@app.route("/salir", methods=["POST"])
def salir():
    resp = redirect(url_for("login"))
    resp.delete_cookie(auth.COOKIE)
    return resp


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = db.conectar(RUTA_DB)
    return g.db


@app.teardown_appcontext
def _cerrar_db(_):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


@app.template_filter("fecha")
def f_fecha(unix: int) -> str:
    d = datetime.fromtimestamp(unix, timezone.utc)
    return f"{d.day} {MESES[d.month - 1]} {d.year}"


@app.template_filter("duracion")
def f_duracion(segundos: int) -> str:
    h, resto = divmod(int(segundos), 3600)
    m, s = divmod(resto, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


@app.template_filter("km")
def f_km(metros: float) -> str:
    return f"{metros / 1000:.2f}"


@app.template_filter("km_entero")
def f_km_entero(metros: float) -> str:
    """Kilometros al entero, redondeando .5 hacia arriba.

    `round` de Python redondea al par (round(0.5) == 0), que no es lo que se
    espera de un total. Las distancias nunca son negativas, asi que truncar
    x + 0,5 es el redondeo de toda la vida.
    """
    return str(int(metros / 1000 + 0.5))


@app.template_filter("unidad_duracion")
def f_unidad_duracion(segundos: int) -> str:
    """La unidad mayor que aplica, para acompañar a la cifra como el km."""
    return "h" if segundos >= 3600 else "min"


@app.template_filter("ritmo")
def f_ritmo(seg_por_km: float) -> str:
    m, s = divmod(round(seg_por_km), 60)
    return f"{m}:{s:02d}"


def _importar_uno(conn, fichero) -> tuple[str, int | None, str | None]:
    """Devuelve (nombre, carreras importadas, error).

    Solo se usa la extension del nombre subido, nunca la ruta: el contenido
    se lee del stream y no se escribe nada en disco.
    """
    nombre = fichero.filename or "(sin nombre)"
    ext = PurePath(nombre).suffix.lower()

    if ext == ".fit":
        try:
            return nombre, amazfit_fit.importar(conn, fichero.stream), None
        except amazfit_fit.FitInvalido as e:
            return nombre, None, str(e)
        except (FitParseError, KeyError, TypeError, ValueError) as e:
            return nombre, None, f"no se pudo leer el .fit ({e})"

    if ext == ".tcx":
        # Nike y Huawei exportan los dos en TCX. Huawei firma el fichero como
        # creator="Health"; Nike no pone creator y mete su extension `nax`.
        contenido = fichero.stream.read()
        try:
            if huawei_tcx.parece_huawei(contenido):
                return nombre, huawei_tcx.importar(conn, contenido), None
            return nombre, nike_tcx.importar(conn, io.BytesIO(contenido)), None
        except (nike_tcx.TcxInvalido, huawei_tcx.TcxInvalido) as e:
            return nombre, None, str(e)
        except ET.ParseError as e:
            return nombre, None, f"XML invalido ({e})"

    if ext != ".json":
        return nombre, None, f"formato no soportado ({ext or 'sin extension'})"

    # Huawei y My Run Stats comparten extension, asi que se distinguen por
    # dentro: el de Huawei es una lista de actividades y el otro un objeto.
    try:
        contenido = fichero.stream.read()
        if huawei_json.parece_huawei(contenido.decode("utf-8")):
            return nombre, huawei_json.importar(conn, contenido), None
        return nombre, my_run_stats.importar(conn, io.BytesIO(contenido)), None
    except huawei_json.HuaweiInvalido as e:
        return nombre, None, str(e)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return nombre, None, f"no es un JSON valido ({e})"
    except (KeyError, TypeError, ValueError) as e:
        return nombre, None, f"no tiene la forma de un export de My Run Stats ({e})"


@app.errorhandler(413)
def _demasiado_grande(_):
    return render_template(
        "importar.html",
        resultados=[("", None, "la tanda supera el limite de 64 MB, subela en varias veces")],
        fusiones=0,
    ), 413


@app.route("/importar", methods=["GET", "POST"])
def importar():
    if request.method == "GET":
        return render_template("importar.html", resultados=None, fusiones=0)

    ficheros = [f for f in request.files.getlist("ficheros") if f.filename]
    if not ficheros:
        return render_template(
            "importar.html",
            resultados=[("", None, "no has seleccionado ningun fichero")],
            fusiones=0,
        )

    conn = get_db()
    resultados = [_importar_uno(conn, f) for f in ficheros]
    hubo_cambios = any(r[1] for r in resultados)
    fusiones = dedup.marcar_duplicadas(conn) if hubo_cambios else []
    if hubo_cambios:
        detalle.recalcular_records(conn)
    return render_template("importar.html", resultados=resultados,
                           fusiones=len(fusiones))


@app.route("/periodo/<agrupacion>/<clave>")
def periodo(agrupacion, clave):
    """Las carreras de un mes o de una semana, al tocar su barra.

    El año no llega aqui: ya tiene su propia vista, la portada filtrada, que
    ademas trae records y graficas.
    """
    tramo = analisis.rango(agrupacion, clave) if agrupacion != "anio" else None
    if tramo is None:
        abort(404)

    carreras = consultas.carreras_en(get_db(), *tramo)
    metros = sum(c["distancia_metros"] for c in carreras)
    return render_template(
        "periodo.html",
        titulo=analisis.titulo_periodo(agrupacion, clave),
        anio=datetime.fromtimestamp(tramo[0], timezone.utc).year,
        carreras=carreras,
        resumen={"carreras": len(carreras), "metros": metros},
    )


# El contacto con el suelo se mueve en unas decenas de milisegundos sobre un
# valor de 300: el eje se fija para que una serie plana se vea plana.
EJE_CONTACTO = 100.0


@app.route("/carrera/<path:carrera_id>")
def carrera(carrera_id):
    conn = get_db()
    car = detalle.carrera(conn, carrera_id)
    if car is None:
        abort(404)

    ms = detalle.muestreos(conn, carrera_id)
    ctx = {"c": car, "muestreos": len(ms), "ritmo": None, "pulso": None,
           "ruta": None, "splits": [], "altitud": None,
           "potencia": None, "contacto": None, "zonas": None}

    if ms:
        t0, t1 = ms[0]["timestamp_unix"], ms[-1]["timestamp_unix"]
        serie = [{"t": x["t"], "v": x["ritmo"]} for x in detalle.serie_ritmo(ms, car)]
        # El ritmo se invierte: mas rapido, mas arriba.
        ctx["ritmo"] = graficas.linea_serie(serie, t0, t1, invertir=True,
                                            formato=f_ritmo)
        ctx["pulso"] = graficas.linea_serie(
            detalle.serie(ms, "frecuencia_cardiaca"), t0, t1)
        # Sin desnivel real no hay nada que enseñar: una carrera de cinta
        # trae la altitud como -1 constante.
        ctx["altitud"] = graficas.linea_serie(
            detalle.serie(ms, "altitud_metros"), t0, t1,
            formato=lambda v: f"{v:.0f} m",
            rango_minimo=graficas.RANGO_MINIMO["altitud_metros"])
        ctx["ruta"] = graficas.ruta_svg(detalle.ruta(ms))
        ctx["splits"] = detalle.splits(ms, car)
        # Solo las trae el .fit del Amazfit; el resto de fuentes las dejan
        # vacias y sus bloques no se pintan.
        ctx["potencia"] = graficas.linea_serie(
            detalle.serie(ms, "potencia_vatios"), t0, t1,
            formato=lambda v: f"{v:.0f} W")
        # 34 ms de rango real: sin eje minimo, un temblor de 1 ms llena el alto.
        ctx["contacto"] = graficas.linea_serie(
            detalle.serie(ms, "tiempo_contacto_ms"), t0, t1,
            formato=lambda v: f"{v:.0f} ms", eje_minimo=EJE_CONTACTO)
        ctx["zonas"] = graficas.barras_zonas(detalle.zonas_fc(conn, carrera_id))

    # Media y maxima acompañan al titulo de su grafica en vez de ocupar
    # tarjetas propias.
    partes = []
    if car["fc_media"]:
        partes.append(f"media {car['fc_media']}")
    if car["fc_maxima"]:
        partes.append(f"máx {car['fc_maxima']}")
    ctx["fc_resumen"] = " · ".join(partes) + (" ppm" if partes else "")

    # Medias de las dos series nuevas, junto a su titulo.
    def _media(campo, unidad):
        v = [m[campo] for m in ms if m[campo] is not None]
        return f"media {round(sum(v) / len(v))} {unidad}" if v else None

    ctx["potencia_resumen"] = _media("potencia_vatios", "W")
    ctx["contacto_resumen"] = _media("tiempo_contacto_ms", "ms")

    return render_template("carrera.html", **ctx)


@app.route("/")
def index():
    conn = get_db()
    anio = request.args.get("anio", type=int)
    disponibles = analisis.anios(conn)
    if anio not in disponibles:
        anio = None

    # Con un año elegido, agrupar por año pintaria los quince: la grafica
    # tiene que hablar del año filtrado, y su unidad natural es el mes.
    agr = request.args.get("agr", "")
    if agr not in analisis.AGRUPACIONES or (anio and agr == "anio"):
        agr = "mes" if anio else "anio"

    datos = analisis.volumen(conn, agr, anio)
    return render_template(
        "index.html",
        carreras=consultas.listar_carreras(conn, anio),
        resumen=analisis.resumen(conn, anio),
        rodantes=analisis.records_rodantes(conn, anio),
        mas_larga=analisis.carrera_mas_larga(conn, anio),
        anios=disponibles,
        anio=anio,
        agr=agr,
        recortado=bool(datos and datos[0]["recortado"]),
        volumen=graficas.barras_volumen(datos),
        evolucion=graficas.dispersion_ritmo(analisis.ritmos(conn, anio), anio),
    )


if __name__ == "__main__":
    app.run(debug=True, port=5001)
