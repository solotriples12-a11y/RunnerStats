# Architecture — RunnerStats

## Visión
Web personal de estadísticas de carrera, servida en `run.javimendoza.com`
desde el servidor Hetzner propio. Importa carreras desde ficheros exportados
a mano, las persiste en SQLite y ofrece análisis más rico que las apps
oficiales: récords por ventana rodante, eficiencia cardiovascular en el
tiempo, gráficas con zonas de FC y mapa.

Responsive: se consulta igual desde ordenador que desde móvil.

## Stack
Mismo patrón que el resto de subdominios de javimendoza.com.

- Flask + Jinja2 + gunicorn sobre `python:3.12-slim`
- SQLite en volumen persistente
- CSS plano, heredando los tokens de `javimendoza.com` (fondo `#0f0f0f`,
  texto `#f5f5f5`, acento `#f56565`, borde `#2a2a2a`)
- Docker → **Coolify** sobre Hetzner, HTTPS por Let's Encrypt, auto-deploy
  al hacer push a `main`
- Subdominio `run.javimendoza.com`. Pasos en `DEPLOY.md`.

### Autenticación
Basic auth **en la aplicación**, con la contraseña en `RUNNERSTATS_PASSWORD`.
Es la convención que ya usa `javimendoza.com` para `/stats` y `/enlaces`.

Dos diferencias respecto a aquella:
- El guard es global (`before_request`), no ruta por ruta: aquí no hay
  ninguna parte pública.
- Falla cerrado. Sin la variable configurada la web devuelve 401 a todo, para
  que un despiste de configuración no publique el histórico.

### Persistencia en producción
El SQLite vive en un volumen montado en `/app/data`. Sin volumen, cada
redeploy borraría los 15 años de histórico. `.dockerignore` impide además que
los datos entren en la imagen, que se construye desde un repo público.

Historial: el proyecto nació como app Android nativa (Kotlin + Compose +
Room). El único motivo era que Huawei Health Kit es Android-only. Tras el
rechazo de Huawei se pivotó a web. Ver `DECISIONS.md`, 2026-09-04.

## Fuentes de datos
Todas son ficheros exportados a mano. No hay sincronización automática.

| Fuente | Carreras | Periodo | Fidelidad |
|---|---|---|---|
| My Run Stats (JSON) | 207 | 2011-12 → 2026-05 | Solo resumen |
| Amazfit Cheetah 2 Pro (`.fit`) | 9 | 2026 | Completa, 1 Hz |
| Huawei (export de privacidad) | ? | ? | Por confirmar |

El detalle verificado de cada formato está en `DECISIONS.md` (entrada
"Tres fuentes de datos con niveles de fidelidad distintos").

Cada fuente se implementa como un importador independiente que produce
carreras normalizadas. Es el equivalente de la interfaz `CarreraSource` del
diseño Android, ahora con tres implementaciones reales.

Los ficheros se suben desde `/importar` y se leen **en memoria**: nada se
escribe en disco, lo que evita de raíz tener que sanear rutas. El despacho
se hace por extensión y cada fichero informa de su resultado por separado,
para que un fichero corrupto no tumbe la subida entera.

### Niveles de fidelidad
No todas las funciones aplican a todas las carreras:

- **Volumen y tendencia de ritmo a largo plazo** → las 207. Señal de 15 años.
- **Zonas de FC, eficiencia cardiovascular, PRs por ventana rodante** → solo
  carreras con muestreos.

La capa de análisis debe saber sobre qué subconjunto habla, y la UI debe
decirlo. Un "mejor 1K de siempre" calculado sobre 9 carreras y mostrado junto
a 15 años de histórico es engañoso aunque sea correcto.

## Modelo de datos (SQLite)

```
[ carrera ] 1 ──< N [ muestreo ]
```

### carrera
- `id` (PK, TEXT) — clave natural prefijada por fuente
- `fecha_inicio_unix` (UTC)
- `distancia_metros`
- `duracion_segundos`
- `fuente` — `my_run_stats` | `amazfit_fit` | `huawei`
- `fc_media`, `fc_maxima` (nullable)
- `desnivel_positivo_metros`, `desnivel_negativo_metros` (nullable)
- `calorias` (nullable)
- `dispositivo` (nullable)
- `importado_en`

El ritmo medio se deriva de distancia y duración; no se almacena. La condición
de récord se calcula al leer; no se almacena.

### muestreo
Puntos segundo a segundo. Solo se cargan al abrir el detalle.
- `carrera_id` (FK, CASCADE) + `timestamp_unix` (PK compuesta)
- `distancia_acumulada_metros` (nullable)
- `frecuencia_cardiaca`, `cadencia_spm`, `velocidad_ms`, `altitud_metros`,
  `latitud`, `longitud` (todos nullable)

Los nulos son reales, no defensivos: en el FIT examinado faltaban 92 valores
de FC y 49 de cadencia, dispersos como microcortes del sensor.

## Trampas de unidades
Ambas verificadas sobre datos reales. Detalle completo en `DECISIONS.md`.

- **Cadencia FIT**: los `record` vienen por pierna (×2 para pasos por
  minuto); los `lap` vienen ya en pasos por minuto.
- **Splits de My Run Stats**: descartados por no fiables.

## Deduplicación
Las fuentes se solapan: la carrera del 2026-09-02 está en Huawei y en el
Amazfit. Regla: misma fecha y distancia aproximada. Ante un duplicado gana la
fuente de mayor fidelidad.

## Capa de análisis y gráficas
- `analisis.py` — solo cálculos que se sostienen con el resumen (fecha,
  distancia, duración), así que aplican a las 207 carreras. Lo que necesita
  muestreos vive fuera y aún no existe.
- `graficas.py` — devuelve geometría; el SVG lo pinta la plantilla. Sin
  librería de gráficas ni CDN: encaja con el "CSS plano" del resto de
  subdominios y evita una dependencia para dos gráficas.
- Ambas gráficas son de **una sola serie**, así que no llevan leyenda y el
  color va solo en las marcas; las etiquetas usan tokens de texto.
- Al filtrar por año las gráficas mantienen la vista larga y **resaltan** el
  año elegido (patrón de énfasis): 15 años de contexto valen más que un año
  aislado. Las barras no resaltadas usan `--marca-contexto`, un gris legible
  sobre la tarjeta; con `--surface-2` desaparecían.
- La línea de medianas **se parte en los años sin carreras**. Unir 2018 con
  2020 dibujaría continuidad donde no hay ni un dato (2019 está vacío).
- Los tooltips son `<title>` nativos de SVG: cero JavaScript, y la lista de
  carreras hace de vista en tabla.

## Cálculos derivados
- **PRs por ventana rodante**: mejor 1K/5K/10K extraído de CUALQUIER carrera
  con muestreos, recorriendo `distancia_acumulada_metros` con dos punteros.
- **Eficiencia cardiovascular**: serie de `(ritmo medio, FC media)` agrupada
  por mes.
- **Zonas de FC**: 5 zonas desde FCMax. El FIT del Amazfit ya trae
  `time_in_hr_zone` calculado por el reloj, útil como contraste.

## Fuera de alcance
- Multi-usuario.
- Otros deportes. Solo running.
- Sincronización automática desde ningún reloj.
- Predicciones tipo "tiempo estimado de tu próxima carrera".
