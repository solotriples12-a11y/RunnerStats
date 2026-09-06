"""Deduplicación entre fuentes.

Las fuentes se solapan: 199 de las fechas de Nike coinciden con My Run Stats,
y la carrera del 2026-09-02 está en Huawei y en el Amazfit. No se borra nada;
la perdedora se marca con `sustituida_por` y las consultas la ocultan.

Dos carreras son la misma si comparten día y su distancia difiere menos que
la tolerancia. Gana la que más muestreos tenga: es la que permite gráficas,
zonas de FC y récords por ventana rodante.
"""

import sqlite3
from collections import defaultdict
from datetime import datetime, timezone

TOLERANCIA = 0.05

# Desempate cuando dos candidatas tienen los mismos muestreos (normalmente 0).
PRIORIDAD = {"amazfit_fit": 3, "nike_tcx": 2, "huawei_json": 1, "my_run_stats": 0}


def _rango(c) -> tuple:
    return (c["muestreos"], PRIORIDAD.get(c["fuente"], 0), c["distancia_metros"])


def marcar_duplicadas(conn: sqlite3.Connection,
                      tolerancia: float = TOLERANCIA) -> list[dict]:
    """Recalcula las marcas desde cero y devuelve las fusiones aplicadas."""
    conn.execute("UPDATE carrera SET sustituida_por = NULL")

    carreras = conn.execute(
        """
        SELECT c.id, c.fecha_inicio_unix, c.distancia_metros, c.fuente,
               (SELECT COUNT(*) FROM muestreo m WHERE m.carrera_id = c.id)
                   AS muestreos
        FROM carrera c
        ORDER BY c.distancia_metros
        """
    ).fetchall()

    por_dia = defaultdict(list)
    for c in carreras:
        dia = datetime.fromtimestamp(c["fecha_inicio_unix"], timezone.utc).date()
        por_dia[dia].append(c)

    fusiones, marcas = [], []
    for dia, delDia in por_dia.items():
        if len(delDia) < 2:
            continue
        # Agrupacion voraz: ya vienen ordenadas por distancia.
        grupos: list[list] = []
        for c in delDia:
            for g in grupos:
                ref = g[0]["distancia_metros"]
                if ref and abs(c["distancia_metros"] - ref) / ref <= tolerancia:
                    g.append(c)
                    break
            else:
                grupos.append([c])

        for g in grupos:
            if len(g) < 2:
                continue
            gana = max(g, key=_rango)
            for pierde in g:
                if pierde["id"] == gana["id"]:
                    continue
                marcas.append((gana["id"], pierde["id"]))
                fusiones.append({
                    "dia": str(dia),
                    "gana": gana["fuente"], "gana_id": gana["id"],
                    "gana_muestreos": gana["muestreos"],
                    "pierde": pierde["fuente"], "pierde_id": pierde["id"],
                    "pierde_muestreos": pierde["muestreos"],
                    "km_gana": round(gana["distancia_metros"] / 1000, 2),
                    "km_pierde": round(pierde["distancia_metros"] / 1000, 2),
                })

    conn.executemany(
        "UPDATE carrera SET sustituida_por = ? WHERE id = ?", marcas)
    conn.commit()
    return fusiones
