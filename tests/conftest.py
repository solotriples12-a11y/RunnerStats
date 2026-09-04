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
