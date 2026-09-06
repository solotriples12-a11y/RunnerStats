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
Sesión por cookie con **una sola contraseña, sin usuario**, igual que Notyo.
La contraseña vive en `RUNNERSTATS_PASSWORD`; al acertarla se entrega una
cookie con un token HMAC derivado de esa misma contraseña, así que no hay
estado de sesión que guardar y cambiarla invalida todas las sesiones.

- El guard es global (`before_request`): aquí no hay ninguna parte pública.
- Falla cerrado. Sin la variable configurada la web devuelve 503 a todo, para
  que un despiste de configuración no publique el histórico.
- La cookie va `HttpOnly`, `SameSite=Lax` y `Secure` cuando el cliente llegó
  por HTTPS (se lee de `X-Forwarded-Proto`, porque Traefik proxea en claro).
- El `next` del login solo admite rutas internas: uno absoluto convertiría el
  login en un redirector abierto.

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
| **Nike Run Club (`.tcx`)** | 269 | 2011-12 → 2026-07 | Variable: 202 con distancia por punto, 158 con GPS, 99 con cadencia, 98 con FC |
| My Run Stats (JSON) | 207 | 2011-12 → 2026-05 | Solo resumen |
| Amazfit Cheetah 2 Pro (`.fit`) | 3 | 2026-09 | La más rica: 1 Hz con potencia, tiempo de contacto y zonas de FC ya calculadas |
| **Huawei Health (JSON)** | 37 | 2025-05 → 2026-09 | Completa: 37 con FC y cadencia a 0,2 Hz, 26 con GPS a 1 Hz |

Nike es casi un superconjunto de My Run Stats: comparten 199 fechas, 65
carreras solo están en Nike y 5 solo en My Run Stats. Rellena 2019 entero,
que en My Run Stats no existía.

Huawei cubre el otro extremo, lo reciente: de sus 37 carreras, 27 no estaban
en ninguna otra fuente y las 10 que sí estaban solo constaban como resumen,
así que la deduplicación las sustituye por la versión con muestreos.

El detalle verificado de cada formato está en `DECISIONS.md` (entrada
"Tres fuentes de datos con niveles de fidelidad distintos").

Cada fuente se implementa como un importador independiente que produce
carreras normalizadas. Es el equivalente de la interfaz `CarreraSource` del
diseño Android, ahora con tres implementaciones reales.

Los ficheros se suben desde `/importar` y se leen **en memoria**: nada se
escribe en disco, lo que evita de raíz tener que sanear rutas. El despacho
se hace por extensión y cada fichero informa de su resultado por separado,
para que un fichero corrupto no tumbe la subida entera. Huawei y My Run Stats
comparten la extensión `.json`, así que entre esos dos se decide por la forma:
el de Huawei es una lista de actividades y el otro un objeto.

### Niveles de fidelidad
No todas las funciones aplican a todas las carreras:

- **Volumen y tendencia de ritmo a largo plazo** → las 313. Señal de 15 años.
- **Ritmo, parciales, récords por ventana rodante** → carreras con muestreos.
- **Esfuerzo (zonas de FC), potencia y contacto con el suelo** → solo el
  `.fit`, hoy 3 carreras. Sus bloques no se pintan en las demás.

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
- **Cadencia Nike**: ya viene en pasos por minuto (media 153,9 en el corpus).
  Misma etiqueta que el FIT, convención distinta. Doblarla daría ~300 spm.
- **Splits de My Run Stats**: descartados por no fiables.

## Deduplicación
Las fuentes se solapan mucho: 199 fechas de Nike coinciden con My Run Stats.

Regla: **mismo día y distancia dentro del 5 %** → gana la carrera con más
**datos**, contando valores y no filas: un muestreo vacío no permite ni
gráficas, ni zonas de FC, ni récords. La perdedora **no se borra**, se marca
con `sustituida_por` y las consultas la ocultan (`WHERE sustituida_por IS
NULL`). Así la decisión es reversible y no se pierde nada.

Contar filas bastaba mientras la competencia era "tiene muestreos" contra "no
tiene". Con dos fuentes completas enfrentadas decide a cara o cruz: la
carrera del 2026-09-02 la ganaba Huawei por cuatro muestreos, dejando fuera
la del Amazfit, que traía el pulso segundo a segundo en vez de cada cinco.

Sobre el corpus real: 296 carreras visibles de 476 antes de Huawei, y 312 de
513 con Huawei dentro.

## Distancia derivada del GPS
`geo.py` calcula distancia acumulada por haversine cuando la fuente no la
trae. Validado contra dos ficheros con distancia declarada: 0,32 % de error
en un TCX de Nike y 0,49 % en uno de Huawei — dentro del ruido que ya hay
entre los dos relojes sobre la misma carrera (1,2 %).

## Capa de análisis y gráficas
- `analisis.py` — solo cálculos que se sostienen con el resumen (fecha,
  distancia, duración), así que aplican a las 207 carreras. Lo que necesita
  muestreos vive fuera y aún no existe.
- `graficas.py` — devuelve geometría; el SVG lo pinta la plantilla. Sin
  librería de gráficas ni CDN: encaja con el "CSS plano" del resto de
  subdominios y evita una dependencia para dos gráficas.
- Ambas gráficas son de **una sola serie**, así que no llevan leyenda y el
  color va solo en las marcas; las etiquetas usan tokens de texto.
- La gráfica de volumen se agrupa por **año, mes, semana (lunes a domingo) o
  carrera**. Con un año elegido no se ofrece agrupar por año —pintaría los
  quince— y el mes pasa a ser la agrupación por defecto. Sin año filtrado las
  agrupaciones finas se recortan a los últimos N periodos y la UI lo dice,
  porque el histórico completo por semanas serían ~770 barras ilegibles.
- **Los periodos sin carreras se rellenan a cero cuando el eje es un tramo de
  tiempo cerrado**: los años del histórico, o los doce meses del calendario
  del año elegido. Omitirlos ahí pegaría marzo con mayo y el eje mentiría
  sobre el tiempo, el mismo fallo que la línea cruzando 2019. Sin año
  elegido, en cambio, mes y semana **sí los omiten**: son 178 meses y ~770
  semanas de histórico, la mayoría vacías, y el recorte a los últimos N se
  gastaba en aire. Ahí el eje deja de ser lineal en el tiempo y la etiqueta
  del mes lleva el año para que el salto se vea.
- La línea de medianas **se parte en los huecos grandes**: un año entero sin
  carreras en la vista larga, dos meses seguidos dentro de un año. Un mes
  suelto no la parte —dejaba puntos aislados que se leían como un fallo de
  pintado—. Unir 2018 con
  2020 dibujaría continuidad donde no hay ni un dato (2019 está vacío).
- **Las etiquetas del eje X salen del ancho del texto**, no de un tope fijo
  de etiquetas: se pone una de cada N, siendo N el mínimo que evita que se
  pisen. Por eso caben los doce meses y los dieciséis años, y las 52 semanas
  no. En la nube de ritmos cada etiqueta va bajo su nodo de mediana, que no
  están repartidos por igual, así que ahí se salta la que no quepa.
- **La gráfica de volumen es un filtro**: cada barra es un enlace. Por año va
  a la portada filtrada (`/?anio=`), que ya existe y trae récords y gráficas;
  por mes y por semana, a `/periodo/<agrupacion>/<clave>`, una página con el
  resumen de ese tramo y su lista; y por carrera, directa a su detalle. Un
  periodo vacío no es un enlace: se pinta como `<g>` en vez de `<a>`.
- **Las zonas de FC son una barra apilada** en rampa secuencial de un solo
  tono, de la zona 1 a la 5: no son categorías sino intensidad creciente, y
  pintarlas de colores distintos diría que son cosas diferentes. Validada en
  modo oscuro con `scripts/validate_palette.js --ordinal`.
- **`linea_serie` acepta un ancho mínimo de eje.** Sin él, reescalar al
  percentil 2-98 hace que una serie casi plana llene el lienzo: el tiempo de
  contacto vive en 34 ms de rango sobre 305, y un temblor de 1 ms parecía una
  montaña. Con 100 ms de eje se ve lo que pasó de verdad —plano toda la
  carrera, con picos en los semáforos—.
- **Tooltips propios**, `static/js/tip.js`: unas 50 líneas sin dependencias,
  el único JavaScript del proyecto. Supersede a los `<title>` nativos de SVG,
  que el navegador pintaba con casi un segundo de retardo y que en táctil no
  aparecían nunca. Cada marca lleva el texto en `data-tip` y una zona
  sensible ancha —la banda entera en las barras, un círculo de 10 px en los
  puntos— para no tener que acertar sobre una marca de 3 px.

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
