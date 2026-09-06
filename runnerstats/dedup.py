"""Deduplicación entre fuentes.

Las fuentes se solapan: 199 de las fechas de Nike coinciden con My Run Stats,
y la carrera del 2026-09-02 está en Huawei y en el Amazfit. No se borra nada;
la perdedora se marca con `sustituida_por` y las consultas la ocultan.

Dos carreras son la misma si comparten día y su distancia difiere menos que
la tolerancia. Gana la que más **datos** traiga, contando valores y no filas:
un muestreo vacío no permite ni gráficas, ni zonas de FC, ni récords.
"""

import sqlite3
from collections import defaultdict
from datetime import datetime, timezone

TOLERANCIA = 0.05

# Desempate cuando dos candidatas traen los mismos datos (normalmente 0).
PRIORIDAD = {"amazfit_fit": 3, "nike_tcx": 2, "huawei_json": 1, "my_run_stats": 0}

# Columnas que se cuentan para medir cuanta informacion trae una carrera.
# `velocidad_ms` queda fuera a proposito: solo la rellena Huawei, asi que
# contarla le daria ventaja por como esta escrito su importador y no por
# tener mas datos. `longitud` tampoco: viene siempre con `latitud` y contar
# las dos pesaria el GPS el doble.
COLUMNAS = ("distancia_acumulada_metros", "frecuencia_cardiaca", "cadencia_spm",
            "altitud_metros", "latitud")


def _rango(c) -> tuple:
    return (c["datos"], PRIORIDAD.get(c["fuente"], 0), c["distancia_metros"])


def marcar_duplicadas(conn: sqlite3.Connection,
                      tolerancia: float = TOLERANCIA) -> list[dict]:
    """Recalcula las marcas desde cero y devuelve las fusiones aplicadas."""
    conn.execute("UPDATE carrera SET sustituida_por = NULL")

    carreras = conn.execute(
        """
        SELECT c.id, c.fecha_inicio_unix, c.distancia_metros, c.fuente,
               (SELECT COUNT(*) + {valores}
                FROM muestreo m WHERE m.carrera_id = c.id) AS datos
        FROM carrera c
        ORDER BY c.distancia_metros
        """.format(valores=" + ".join(f"COUNT({c})" for c in COLUMNAS))
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
                    "gana_datos": gana["datos"],
                    "pierde": pierde["fuente"], "pierde_id": pierde["id"],
                    "pierde_datos": pierde["datos"],
                    "km_gana": round(gana["distancia_metros"] / 1000, 2),
                    "km_pierde": round(pierde["distancia_metros"] / 1000, 2),
                })

    conn.executemany(
        "UPDATE carrera SET sustituida_por = ? WHERE id = ?", marcas)
    conn.commit()
    return fusiones
