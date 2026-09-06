import json
from pathlib import Path

import pytest

DATA = Path(__file__).parent.parent / "data"


@pytest.fixture
def export_real() -> Path:
    """El export real de My Run Stats, si está disponible en data/.

    No se versiona (son datos de salud), así que los tests que dependen de él
    se saltan cuando no está.
    """
    ficheros = sorted(DATA.glob("my-run-stats-*.json"))
    if not ficheros:
        pytest.skip("no hay export de My Run Stats en data/")
    return ficheros[-1]


@pytest.fixture
def export_sintetico(tmp_path) -> Path:
    """Export mínimo que reproduce la forma real del JSON.

    Incluye una carrera con km_splits y otra sin ellos, y un último split
    parcial, para comprobar que el importador los ignora.
    """
    datos = {
        "app": "My Run Stats",
        "exported_at": "2026-09-04T09:34:12.725Z",
        "version": 1,
        "count": 2,
        "runs": [
            {
                "id": "aaaa-1111",
                "date": "2026-05-04",
                "duration": "00:27:55",
                "distance": 5.03,
                "pace": "5:33",
                "km_splits": None,
            },
            {
                "id": "bbbb-2222",
                "date": "2024-08-20",
                "duration": "00:21:06",
                "distance": 3.54,
                "pace": "5:58",
                "km_splits": [
                    {"km": 1, "time": "6:03"},
                    {"km": 2, "time": "5:57"},
                    {"km": 3, "time": "5:54"},
                    {"km": 4, "time": "3:12"},
                ],
            },
        ],
    }
    ruta = tmp_path / "my-run-stats-test.json"
    ruta.write_text(json.dumps(datos))
    return ruta


@pytest.fixture
def fit_real() -> Path:
    """Un .fit real del Amazfit, si esta disponible en data/."""
    ficheros = sorted(DATA.glob("*.fit"))
    if not ficheros:
        pytest.skip("no hay ningun .fit en data/")
    return ficheros[0]


@pytest.fixture
def nike_dir() -> Path:
    """Muestras representativas del export de Nike, si estan en data/nike/."""
    d = DATA / "nike"
    if not d.is_dir() or not list(d.glob("*.tcx")):
        pytest.skip("no hay TCX de Nike en data/nike/")
    return d


@pytest.fixture
def huawei_dir() -> Path:
    """Muestras reales del export de privacidad de Huawei, si están en data/.

    Son datos de salud: no se versionan, y los tests que dependen de ellas se
    saltan cuando no están.
    """
    d = DATA / "huawei"
    if not d.exists() or not list(d.glob("*.json")):
        pytest.skip("no hay muestras de Huawei en data/huawei")
    return d


@pytest.fixture
def huawei_sintetico(tmp_path) -> Path:
    """Un 'Motion path detail data' mínimo con la forma real del export.

    Lleva las dos trampas del formato: las claves sin comillas de
    `partTimeMap` y el detalle metido dentro de `attribute`. Y tres
    actividades: una carrera con GPS, una de cinta sin él y un paseo, que no
    tiene que entrar.
    """
    def pista(inicio_ms, con_gps):
        lineas = []
        for i in range(6):
            t = inicio_ms + i * 5000
            lineas.append(f"tp=h-r;k={t};v={150 + i};")
            lineas.append(f"tp=s-r;k={t};v={160 + i};")
            lineas.append(f"tp=alti;k={t};v={700 + i * 0.5};")
            lineas.append(f"tp=rs;k={i * 5};v=28;")
            if con_gps:
                lineas.append(
                    f"tp=lbs;k={i};lat={40.4 + i * 0.001};lon={-3.7 + i * 0.001};"
                    f"alt=0.0;t={(inicio_ms // 1000 + i) / 1e9:.9E};")
        # El salto va escapado: dentro del JSON es un "\n" literal de dos
        # caracteres, no un salto de linea de verdad.
        return "HW_EXT_TRACK_DETAIL@i" + "\\n".join(lineas)

    def actividad(inicio_ms, tipo, metros, ms, con_gps):
        return (
            '{"recordId":"id%d","sportType":%d,"startTime":%d,"endTime":%d,'
            '"totalDistance":%d,"totalTime":%d,"totalCalories":300000,'
            '"partTimeMap":{1.0:380.0,2.0:770.0},"attribute":"%s"}'
            % (inicio_ms, tipo, inicio_ms, inicio_ms + ms, metros, ms,
               pista(inicio_ms, con_gps)))

    crudo = "[%s]" % ",".join([
        actividad(1774422857000, 4, 5000, 1800000, True),     # carrera con GPS
        actividad(1774509257000, 101, 4000, 1500000, False),  # cinta
        actividad(1774595657000, 5, 1600, 1900000, True),     # paseo: fuera
    ])
    ruta = tmp_path / "motion path detail data123.json"
    ruta.write_text(crudo)
    return ruta
