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


def barras_volumen(datos: list[dict]) -> dict:
    """Columnas de km por año."""
    if not datos:
        return {"vacia": True}

    alto_util = ALTO - PAD_SUP - PAD_INF
    kmax = max(d["km"] for d in datos)
    y = _escala(0, kmax, ALTO - PAD_INF, PAD_SUP)

    banda = (ANCHO - PAD_IZQ - PAD_DER) / len(datos)
    ancho = min(GROSOR_MAX, banda - HUECO)

    barras = []
    for i, d in enumerate(datos):
        x = PAD_IZQ + banda * i + (banda - ancho) / 2
        alto = (ALTO - PAD_INF) - y(d["km"])
        r = min(RADIO, ancho / 2, alto)
        barras.append({
            "anio": d["anio"],
            "km": d["km"],
            "carreras": d["carreras"],
            "x": round(x, 1),
            "centro": round(x + ancho / 2, 1),
            # Esquinas superiores redondeadas, base recta contra el eje.
            "d": (
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

    ejex = []
    for a in sorted(por_anio):
        if a % 3 == 0 or a == max(por_anio):
            ts = datetime(a, 7, 1, tzinfo=timezone.utc).timestamp()
            if tmin <= ts <= tmax:
                ejex.append({"x": round(fx(ts), 1), "etiqueta": str(a)})

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
