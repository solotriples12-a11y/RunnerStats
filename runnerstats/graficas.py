"""Geometría de las gráficas. Devuelve coordenadas; el SVG lo pinta la
plantilla.

Ambas gráficas son de una sola serie, así que no llevan leyenda: el título
ya dice qué se está pintando. El color va solo en las marcas; las etiquetas
usan los tokens de texto.
"""

from datetime import datetime, timezone

ANCHO = 640
ALTO = 190
PAD_IZQ = 34
PAD_DER = 8
PAD_SUP = 12
PAD_INF = 22

GROSOR_MAX = 24   # las barras nunca llenan su banda: el aire lo da la banda
RADIO = 4         # extremo redondeado arriba, cuadrado en la base
HUECO = 2         # separación en color de superficie entre barras vecinas


def _escala(vmin: float, vmax: float, destino_min: float, destino_max: float):
    rango = (vmax - vmin) or 1
    return lambda v: destino_min + (v - vmin) / rango * (destino_max - destino_min)


def _ticks(vmax: float, n: int = 3) -> list[float]:
    """Valores redondos para la rejilla."""
    if vmax <= 0:
        return [0]
    paso = vmax / n
    magnitud = 10 ** (len(str(int(paso))) - 1) if paso >= 1 else 1
    paso = max(magnitud, round(paso / magnitud) * magnitud)
    return [t for t in (paso * i for i in range(n + 2)) if t <= vmax * 1.05]


def barras_volumen(datos: list[dict], resaltar: str | None = None) -> dict:
    """Columnas de km por periodo.

    El numero de barras varia mucho segun la agrupacion (16 años, 52 semanas,
    50 carreras), asi que el grosor y el hueco se adaptan: por debajo de 6 px
    de banda el hueco desaparece, porque un separador de 2 px sobre una barra
    de 3 px se comeria la marca.
    """
    if not datos:
        return {"vacia": True}

    kmax = max(d["km"] for d in datos) or 1
    y = _escala(0, kmax, ALTO - PAD_INF, PAD_SUP)

    banda = (ANCHO - PAD_IZQ - PAD_DER) / len(datos)
    hueco = HUECO if banda >= 6 else 0
    ancho = max(1.0, min(GROSOR_MAX, banda - hueco))

    # Como maximo 8 etiquetas, generadas desde el final hacia atras. Repartir
    # desde el principio y ademas forzar la ultima dejaba las dos ultimas
    # pegadas y el texto se pisaba.
    n = len(datos)
    paso = max(1, round(n / 8))
    visibles = set(range(n - 1, -1, -paso))

    barras = []
    for i, d in enumerate(datos):
        x = PAD_IZQ + banda * i + (banda - ancho) / 2
        alto = (ALTO - PAD_INF) - y(d["km"])
        r = min(RADIO, ancho / 2, alto)
        barras.append({
            "etiqueta": d["etiqueta"],
            "clave": d["clave"],
            "km": d["km"],
            "carreras": d["carreras"],
            "centro": round(x + ancho / 2, 1),
            "etiquetada": i in visibles,
            # Un periodo sin carreras no dibuja barra: el hueco es el dato.
            "d": None if d["km"] <= 0 else (
                f"M{x:.1f},{ALTO - PAD_INF} L{x:.1f},{y(d['km']) + r:.1f} "
                f"Q{x:.1f},{y(d['km']):.1f} {x + r:.1f},{y(d['km']):.1f} "
                f"L{x + ancho - r:.1f},{y(d['km']):.1f} "
                f"Q{x + ancho:.1f},{y(d['km']):.1f} {x + ancho:.1f},{y(d['km']) + r:.1f} "
                f"L{x + ancho:.1f},{ALTO - PAD_INF} Z"
            ),
        })

    return {
        "vacia": False,
        "ancho": ANCHO, "alto": ALTO,
        "base": ALTO - PAD_INF,
        "barras": barras,
        "resaltar": resaltar,
        "rejilla": [{"y": round(y(t), 1), "etiqueta": f"{int(t)}"} for t in _ticks(kmax)],
    }


def dispersion_ritmo(datos: list[dict]) -> dict:
    """Ritmo de cada carrera en el tiempo, con la mediana anual encima.

    Los puntos son contexto (gris) y la mediana es la historia (acento): es
    el patrón de énfasis, no dos series que compitan.
    """
    if len(datos) < 2:
        return {"vacia": True}

    ritmos = [d["ritmo"] for d in datos]
    # Recorta el 2 % extremo para que un paseo suelto no aplaste la escala.
    orden = sorted(ritmos)
    rmin, rmax = orden[0], orden[int(len(orden) * 0.98)]

    tmin = min(d["fecha_inicio_unix"] for d in datos)
    tmax = max(d["fecha_inicio_unix"] for d in datos)
    fx = _escala(tmin, tmax, PAD_IZQ, ANCHO - PAD_DER)
    fy = _escala(rmin, rmax, PAD_SUP, ALTO - PAD_INF)  # más rápido, más arriba

    puntos = [{
        "cx": round(fx(d["fecha_inicio_unix"]), 1),
        "cy": round(fy(min(d["ritmo"], rmax)), 1),
        "ritmo": d["ritmo"],
        "fecha": datetime.fromtimestamp(d["fecha_inicio_unix"], timezone.utc).date().isoformat(),
        "km": d["distancia_metros"] / 1000,
    } for d in datos]

    # Mediana por año.
    por_anio: dict[str, list] = {}
    for d in datos:
        a = datetime.fromtimestamp(d["fecha_inicio_unix"], timezone.utc).year
        por_anio.setdefault(a, []).append((d["fecha_inicio_unix"], d["ritmo"]))

    medianas = []
    for a in sorted(por_anio):
        vals = sorted(v for _, v in por_anio[a])
        med = vals[len(vals) // 2]
        centro = sum(t for t, _ in por_anio[a]) / len(por_anio[a])
        medianas.append({
            "anio": a, "ritmo": med,
            "x": round(fx(centro), 1),
            "y": round(fy(min(med, rmax)), 1),
        })

    # Parte la linea en los anios sin carreras: unir 2018 con 2020 dibujaria
    # continuidad donde no hay ni un dato (2019 esta vacio).
    segmentos, actual = [], []
    for m in medianas:
        if actual and m["anio"] != actual[-1]["anio"] + 1:
            segmentos.append(actual)
            actual = []
        actual.append(m)
    if actual:
        segmentos.append(actual)

    # Igual que en las barras: desde el año mas reciente hacia atras, para que
    # el ultimo siempre salga sin quedar pegado al anterior.
    anios = sorted(por_anio)
    paso_a = max(1, round(len(anios) / 6))
    ejex = []
    for a in anios[::-1][::paso_a]:
        ts = datetime(a, 7, 1, tzinfo=timezone.utc).timestamp()
        if tmin <= ts <= tmax:
            ejex.append({"x": round(fx(ts), 1), "etiqueta": str(a)})
    ejex.sort(key=lambda e: e["x"])

    def mmss(s):
        return f"{int(s) // 60}:{int(s) % 60:02d}"

    return {
        "vacia": False,
        "ancho": ANCHO, "alto": ALTO,
        "puntos": puntos,
        "segmentos": [
            " ".join(f"{m['x']},{m['y']}" for m in seg)
            for seg in segmentos if len(seg) > 1
        ],
        "sueltos": [m for seg in segmentos if len(seg) == 1 for m in seg],
        "medianas": medianas,
        "rejilla": [
            {"y": round(fy(r), 1), "etiqueta": mmss(r)}
            for r in (rmin, (rmin + rmax) / 2, rmax)
        ],
        "ejex": ejex,
    }


ALTO_DETALLE = 130


def linea_serie(puntos: list[dict], t0: int, t1: int, invertir: bool = False,
                formato=None) -> dict:
    """Serie temporal de una carrera: x = segundos desde el inicio.

    Las dos gráficas de detalle comparten el eje X para poder leerse juntas.
    Van apiladas y no superpuestas a propósito: ritmo y pulso tienen escalas
    distintas, y un segundo eje Y inventaría una correlación que no está en
    los datos.

    `invertir` pone los valores bajos arriba, que es como se lee un ritmo.
    """
    if len(puntos) < 2:
        return {"vacia": True}

    # La escala se recorta a los percentiles 2-98: un unico pico deja el
    # resto de la serie aplastado contra el eje.
    orden = sorted(p["v"] for p in puntos)
    vmin = orden[int(len(orden) * 0.02)]
    vmax = orden[min(len(orden) - 1, int(len(orden) * 0.98))]
    if vmax <= vmin:
        vmin, vmax = orden[0], orden[-1] or orden[0] + 1
    if vmax == vmin:
        vmax = vmin + 1

    alto = ALTO_DETALLE
    fx = _escala(t0, t1 or t0 + 1, PAD_IZQ, ANCHO - PAD_DER)
    fy = (_escala(vmin, vmax, PAD_SUP, alto - PAD_INF) if invertir
          else _escala(vmin, vmax, alto - PAD_INF, PAD_SUP))

    fmt = formato or (lambda v: f"{v:.0f}")
    return {
        "vacia": False,
        "ancho": ANCHO, "alto": alto,
        "linea": " ".join(
            f"{fx(p['t']):.1f},{fy(min(max(p['v'], vmin), vmax)):.1f}"
            for p in puntos),
        "rejilla": [{"y": round(fy(v), 1), "etiqueta": fmt(v)}
                    for v in (vmin, (vmin + vmax) / 2, vmax)],
        "ejex": [{"x": round(fx(t0 + (t1 - t0) * f), 1),
                  "etiqueta": f"{int((t1 - t0) * f) // 60}'"}
                 for f in (0.25, 0.5, 0.75, 1.0)],
        "min": vmin, "max": vmax,
    }


def ruta_svg(puntos: list[tuple[float, float]], lado: int = 320) -> dict:
    """Traza GPS proyectada, ajustada al lienzo conservando proporciones.

    Proyección equirectangular con corrección por latitud: a escala de una
    carrera el error es despreciable y evita depender de una librería de
    mapas. Se dibuja en local a propósito: pedir teselas a un servidor
    externo enviaría las coordenadas de dónde corres a un tercero.
    """
    if len(puntos) < 2:
        return {"vacia": True}

    import math
    lat0 = sum(p[0] for p in puntos) / len(puntos)
    k = math.cos(math.radians(lat0))
    xs = [p[1] * k for p in puntos]
    ys = [-p[0] for p in puntos]          # norte arriba

    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    ancho_g, alto_g = (x1 - x0) or 1e-9, (y1 - y0) or 1e-9

    # El lienzo toma la proporcion del recorrido en vez de ser cuadrado: una
    # ruta apaisada dejaba media caja vacia. Se limita para que una traza casi
    # recta no salga como una tira de un pixel.
    proporcion = min(max(alto_g / ancho_g, 0.45), 1.6)
    ancho_c, alto_c = lado, lado * proporcion
    escala = min((ancho_c - 16) / ancho_g, (alto_c - 16) / alto_g)
    dx = (ancho_c - ancho_g * escala) / 2
    dy = (alto_c - alto_g * escala) / 2

    pts = [f"{(x - x0) * escala + dx:.1f},{(y - y0) * escala + dy:.1f}"
           for x, y in zip(xs, ys)]
    return {"vacia": False, "ancho": round(ancho_c), "alto": round(alto_c),
            "linea": " ".join(pts), "inicio": pts[0], "fin": pts[-1]}
