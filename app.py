import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import PurePath

from dotenv import load_dotenv
from fitparse.utils import FitParseError
from flask import Flask, Response, g, render_template, request

from runnerstats import analisis, consultas, db, graficas
from runnerstats.importers import amazfit_fit, my_run_stats

load_dotenv()

app = Flask(__name__)

# El export mas grande visto hasta ahora ronda los 2 MB. 32 evita que una
# subida enorme agote la memoria del contenedor.
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024

RUTA_DB = os.environ.get("RUNNERSTATS_DB") or "data/runnerstats.db"

MESES = ("ene", "feb", "mar", "abr", "may", "jun",
         "jul", "ago", "sep", "oct", "nov", "dic")


def _auth_ok() -> bool:
    esperado = os.environ.get("RUNNERSTATS_PASSWORD", "")
    auth = request.authorization
    return bool(esperado) and auth is not None and auth.password == esperado


@app.before_request
def _exigir_auth():
    """Toda la web va detrás de auth.

    A diferencia de javimendoza.com, aquí no hay ninguna parte pública: son
    15 años de entrenamientos, frecuencia cardíaca y trazas GPS del
    domicilio. Por eso el guard es global y no ruta por ruta.

    Falla cerrado: sin `RUNNERSTATS_PASSWORD` configurado nadie entra.
    """
    if not _auth_ok():
        return Response(
            "Auth required", 401,
            {"WWW-Authenticate": 'Basic realm="RunnerStats"'},
        )


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

    if ext != ".json":
        return nombre, None, f"formato no soportado ({ext or 'sin extension'})"

    try:
        return nombre, my_run_stats.importar(conn, fichero.stream), None
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return nombre, None, f"no es un JSON valido ({e})"
    except (KeyError, TypeError, ValueError) as e:
        return nombre, None, f"no tiene la forma de un export de My Run Stats ({e})"


@app.errorhandler(413)
def _demasiado_grande(_):
    return render_template(
        "importar.html",
        resultados=[("", None, "el fichero supera el limite de 32 MB")],
    ), 413


@app.route("/importar", methods=["GET", "POST"])
def importar():
    if request.method == "GET":
        return render_template("importar.html", resultados=None)

    ficheros = [f for f in request.files.getlist("ficheros") if f.filename]
    if not ficheros:
        return render_template(
            "importar.html",
            resultados=[("", None, "no has seleccionado ningun fichero")],
        )

    conn = get_db()
    return render_template(
        "importar.html",
        resultados=[_importar_uno(conn, f) for f in ficheros],
    )


@app.route("/")
def index():
    conn = get_db()
    anio = request.args.get("anio", type=int)
    disponibles = analisis.anios(conn)
    if anio not in disponibles:
        anio = None

    agr = request.args.get("agr", "anio")
    if agr not in analisis.AGRUPACIONES:
        agr = "anio"

    datos = analisis.volumen(conn, agr, anio)
    return render_template(
        "index.html",
        carreras=consultas.listar_carreras(conn, anio),
        resumen=analisis.resumen(conn, anio),
        records=analisis.records(conn, anio),
        anios=disponibles,
        anio=anio,
        agr=agr,
        recortado=bool(datos and datos[0]["recortado"]),
        # Agrupando por año la gráfica mantiene la vista larga y resalta el
        # año filtrado: 15 años de contexto valen más que un año aislado.
        volumen=graficas.barras_volumen(
            datos, resaltar=str(anio) if anio and agr == "anio" else None),
        evolucion=graficas.dispersion_ritmo(analisis.ritmos(conn)),
    )


if __name__ == "__main__":
    app.run(debug=True, port=5001)
