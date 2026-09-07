# RunnerStats

Web personal de estadísticas de carrera. Corre en
**<https://run.javimendoza.com>**, sobre el Hetzner propio. Importa los
ficheros que exportan Nike, Huawei, Amazfit y My Run Stats, los normaliza en
un SQLite y saca de ahí más de lo que dan esas apps: récords por ventana
rodante, parciales que descuentan el tiempo parado, y las cinco fuentes
fusionadas en una sola carrera.

No tiene parte pública: una contraseña y dentro.

## Estado, a 7 de septiembre de 2026

**313 carreras visibles** de 519 filas importadas, **1.637 km**, de diciembre
de 2011 a septiembre de 2026. 305.448 muestreos segundo a segundo.

| Fuente | Visibles / importadas | Periodo | Qué aporta |
|---|---|---|---|
| `nike_tcx` | 257 / 267 | 2011-12 → 2026-07 | El grueso del histórico. FC por segundo en las recientes; muchas antiguas solo resumen |
| `my_run_stats` | 29 / 207 | 2011-12 → 2026-05 | Solo resumen. Casi todas las tapa Nike |
| `huawei_json` | 23 / 37 | 2025-05 → 2026-09 | GPS a 1 Hz, FC y cadencia cada 5 s |
| `huawei_tcx` | 1 / 5 | 2026-02 → 2026-04 | Solo el recorrido de las "carreras de prueba", que el export de privacidad no trae |
| `amazfit_fit` | 3 / 3 | 2026-09 | La más rica: 1 Hz con potencia, contacto con el suelo y zonas de FC |

Que una carrera no sea "visible" no significa que se pierda: la
deduplicación esconde la peor versión, pero **sus campos se fusionan con la
que gana**. Ver `DECISIONS.md`, 2026-09-06.

## Empezar

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m pytest tests/ -q          # 157 tests, ~10 s
RUNNERSTATS_PASSWORD=loquesea ./.venv/bin/python app.py   # http://localhost:5001
```

Los tests que van contra ficheros reales se **saltan solos** si no están en
`data/`; los demás usan ficheros sintéticos que reproducen la forma exacta de
cada formato, trampas incluidas.

## El mapa

```
app.py                  rutas, filtros de plantilla y despacho de subidas
runnerstats/
  modelo.py             Carrera y Muestreo: lo que toda fuente produce
  db.py                 conexión, esquema y migraciones
  schema.sql            carrera, muestreo, zona_fc, record_ventana
  importers/            uno por formato; todos exponen leer() e importar()
  dedup.py              qué versión de una carrera gana
  detalle.py            parciales, récords, series y la fusión de versiones
  analisis.py           agregados para la portada
  graficas.py           geometría; el SVG lo pinta la plantilla
  geo.py                haversine y distancia acumulada
  consultas.py          listados
templates/  static/     Jinja2 y CSS plano, sin framework
tests/                  157 tests
data/                   exports personales, ignorado por git
```

## Los cuatro documentos

Cada uno responde a una cosa distinta. Léelos en este orden:

| Archivo | Para qué |
|---|---|
| **`ARCHITECTURE.md`** | La forma del sistema: stack, modelo de datos, fuentes, trampas de unidades, cómo funcionan análisis y gráficas. **Empieza aquí.** |
| **`DECISIONS.md`** | Por qué las cosas son como son. Append-only, 42 entradas. Cuando algo parezca raro, la respuesta suele estar aquí. |
| **`BACKLOG.md`** | Qué falta y qué se descartó, con el motivo. |
| **`PROGRESS.md`** | Diario de iteraciones. Append-only. Útil para reconstruir cuándo entró algo. |
| **`DEPLOY.md`** | Cómo se despliega y **cómo se opera la base de producción por SSH**. |

Si vas a tocar el proyecto, lee también `CLAUDE.md`: son las convenciones que
no se deducen del código.

## Datos

Viven en `data/`, que **está en `.gitignore` y en `.dockerignore`**: son datos
de salud y trazas GPS del domicilio, y el repo es público. La base de
producción está en un volumen de Coolify montado en `/app/data`, no en la
imagen.

Los originales de los exports están fuera del repo, en el escritorio:
`~/Desktop/nikeuserdata/tcx`, `~/Desktop/datos huawei/`.

## Lo que hay que saber antes de tocar nada

- **Las cifras se comprueban contra la realidad.** Un récord de 5K salió una
  vez en 20:21 cuando el real era 34:53, por una serie de distancia con un
  hueco de 890 s. Se arregló y desde entonces toda serie derivada se valida
  contra el resumen de su carrera (`detalle._serie_fiable`).
- **No se borra nada.** La deduplicación marca, no elimina.
- **La interfaz dice de qué subconjunto habla.** Un "mejor 1K de siempre"
  calculado sobre 3 carreras y puesto junto a 15 años de histórico engaña
  aunque sea correcto.
