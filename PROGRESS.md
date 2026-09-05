# Progress

Append-only. Qué cambió, por qué, qué se verificó.

---

## 2026-05-25 — Bootstrap conceptual

**Qué**: Decisiones iniciales tomadas (stack, fuente de datos, alcance,
modelo de datos). Creación de `ARCHITECTURE.md`, `DECISIONS.md`,
`BACKLOG.md`, `PROGRESS.md`.

**Por qué**: Sentar las bases antes de escribir código, para no construir
contra una arquitectura imaginada (CLAUDE.md §1).

**Verificado**: Ninguna ejecución. No hay código aún.

**Siguiente**: Validar con el usuario que el contenido de `ARCHITECTURE.md`
y `BACKLOG.md` refleja lo que quiere. Después arrancar el bootstrap del
proyecto Android (punto 2 del backlog).

---

## 2026-05-25 — Bootstrap proyecto Android + fuente agnóstica

**Qué**:
- Scaffold Gradle (Kotlin DSL + version catalog), módulo `:app`, Compose vacío
  arrancando con tema Material 3 que respeta dark mode.
- Decisión registrada: `RunningRepository` depende de una interfaz
  `CarreraSource`, no de un cliente concreto. Razón: poder pivotar a import
  ZIP sin reescribir capas si Huawei rechaza Health Kit.
- Backlog reordenado: nuevo punto 7 (interfaz + `FixtureSource`).

**Por qué**: Avanzar contra fixtures permite desarrollar la UI y los
algoritmos sin esperar a la aprobación de Health Kit por parte de Huawei.

**Verificado**: Pendiente — el usuario tiene que generar el wrapper de Gradle
(`gradle wrapper` o "Sync Project" en Android Studio) y abrir el proyecto.
Yo no puedo generar el `gradle-wrapper.jar` (binario).

**Siguiente**: Punto 3 del backlog — esquema Room mínimo (entities + DAOs).

---

## 2026-05-25 — Esquema Room (entities + DAOs + test instrumentado)

**Qué**:
- Plugin KSP añadido (versión emparejada con Kotlin 2.0.21).
- Dependencias Room 2.6.1 (runtime, ktx, compiler vía KSP, testing).
- Entities `CarreraSummaryEntity` (PK `String`) y `CarreraMuestreoEntity`
  (FK a summary con `onDelete = CASCADE`, índice en `carrera_id`).
- DAOs con métodos mínimos: `upsertAll`, observación con `Flow`, lookup por
  id, `getUltimaFechaUnix` (para sync incremental) y borrado.
- `RunnerStatsDatabase` versión 1, `exportSchema = true` (escribe en
  `app/schemas/` para futuras migration tests).
- Test instrumentado `RunnerStatsDatabaseTest`: comprueba orden descendente
  por fecha y cascade delete de muestreos.
- `local.properties` creado apuntando a `~/Library/Android/sdk` (no va a git).

**Por qué**: Sentar la persistencia local antes de cualquier UI o fuente de
datos, porque tanto los fixtures como Health Kit acabarán escribiendo aquí.

**Verificado**: `./gradlew :app:assembleDebug` → BUILD SUCCESSFUL (1m 48s).
KSP procesó las anotaciones de Room, schema exportado a `app/schemas/`,
APK debug generado. Tests instrumentados no ejecutados (requieren
dispositivo o emulador).

**Siguiente**: Punto 2 del backlog (fixtures JSON) para poder empezar la UI
sin depender de Health Kit.

---

## 2026-05-25 — Decisión de pausar hasta tener Health Kit

**Qué**: No se escribe más código de capa de datos ni de UI hasta tener
Health Kit aprobado. Ni fixtures, ni parser ZIP. Backlog reorganizado para
poner el registro como dev en Huawei como bloqueante explícito y el cliente
Health Kit como primera tarea de código tras la aprobación.

**Por qué**: Evitar construir contra una API imaginada y evitar código que
se va a tirar (CLAUDE.md §1, §2). Decisión completa en `DECISIONS.md`.

**Verificado**: N/A — no hay cambio de código en este step.

**Siguiente**: Acción del usuario fuera del repo (registro en Huawei
Developers + solicitud Health Kit). Cuando esté aprobado, retomamos por el
punto 2 del backlog.

---

## 2026-05-25 — Solicitud Health Kit + corrección de scopes en docs

**Qué**:
- Confirmado que Health Kit NO se habilita desde AGC como otros servicios.
  Hay un apply form aparte en developer.huawei.com/consumer/en/hms/huaweihealth/
  con revisión manual de Huawei.
- Corregidos `ARCHITECTURE.md` y `DECISIONS.md`: los scopes inventados
  (`health.activity.read`) no existen; los reales son de la familia
  `HEALTHKIT_*_BOTH` / `HEALTHKIT_*_READ` y se confirmarán al ver la lista
  del formulario.
- BACKLOG actualizado con checklist de progreso del registro Huawei
  (cuenta, proyecto y app creadas; falta el apply).

**Por qué**: Honestidad sobre lo que pasa con Health Kit (CLAUDE.md §6) y
sobre que mi info inicial sobre scopes estaba mal.

**Verificado**: N/A (sin cambios de código).

**Siguiente**: El usuario envía la solicitud de Health Kit con la
justificación preparada. Si aprueban, retomamos con el cliente
`HuaweiHealthKitSource`. Si rechazan, activamos el parser ZIP (Plan B).

---

## 2026-09-04 — Rechazo de Huawei, tres fuentes reales y pivote a web

**Qué**:
- Huawei denegó la solicitud de Health Kit. Abandonado definitivamente.
- Se examinaron ficheros reales de las tres fuentes disponibles. El TCX de
  Huawei resultó ser solo GPS + altitud (cero FC). El `.fit` del Amazfit trae
  todo a 1 Hz. Apareció una tercera fuente, el JSON de My Run Stats, con 207
  carreras desde 2011.
- Se detectaron dos trampas de unidades que habrían producido datos falsos sin
  fallar: cadencia ×2 en el FIT y splits parciales en My Run Stats.
- **Pivote de app Android nativa a web** en `run.javimendoza.com`. Stack:
  Python + SQLite, basic auth en el proxy. Motivo: el único argumento para
  Android era Health Kit, que ya no existe.
- Reescritos `ARCHITECTURE.md` y `BACKLOG.md`. Cinco entradas nuevas en
  `DECISIONS.md`.
- Esquema SQLite (`carrera` 1-N `muestreo`) e importador de My Run Stats.

**Por qué**: Con Health Kit muerto, todas las fuentes son ficheros y nada ata
el proyecto a un móvil. Se empieza por My Run Stats porque es la fuente más
simple y la que más histórico aporta, así que da una app útil antes de
meterse con el parser de FIT, que es el trozo grande.

**Verificado**: 13 tests en verde (`pytest`), 6 de ellos contra el export real:
- Las 207 carreras se importan; totales 1098,8 km y 112,3 h.
- El `pace` del JSON coincide con duración/distancia en las 207 → confirma
  que almacenarlo sería redundante.
- La trampa de los splits queda cubierta por un test: el "mejor kilómetro"
  ingenuo da 3:01 (que en realidad son 580 m) frente a 4:05 real. 64 s/km.
- Reimportar no duplica.
- Import real ejecutado contra `data/runnerstats.db`: 207 filas.

**Pendiente de acción del usuario**:
- Borrar el scaffold Android (el clasificador bloqueó el borrado masivo).
- Datos del servidor Hetzner para poder planear el despliegue.
- Export de privacidad de Huawei: pedido, avisan de 7 días.

**Siguiente**: Punto 2 del backlog — parser de `.fit`, que es donde están los
muestreos y por tanto las gráficas, las zonas de FC y los PRs por ventana
rodante.

---

## 2026-09-04 — Web funcionando y lista para desplegar en run.javimendoza.com

**Qué**:
- Revisado el proyecto `web-javimendoza`: hay tres subdominios en producción
  con un patrón consolidado (Hetzner + Coolify + Dockerfile) y
  `javimendoza.com` ya es Flask + gunicorn. Se adopta ese patrón entero en
  lugar de inventar uno.
- **Corregida la decisión de auth** tomada esa misma mañana: de basic auth en
  el proxy a basic auth en la app (`RUNNERSTATS_PASSWORD`), que es la
  convención de la casa. Guard global y fallo cerrado.
- App Flask con vista de lista responsive, heredando los tokens visuales de
  `javimendoza.com`.
- `Dockerfile`, `.dockerignore`, `.env.example` y `DEPLOY.md`.

**Por qué**: El usuario indicó que la infraestructura ya estaba resuelta en
el proyecto vecino y que aquí solo hacía falta el subdominio nuevo. Copiar el
patrón existente es más barato y más consistente que decidir de cero
(CLAUDE.md §3).

**Verificado**: 18 tests en verde, 5 nuevos de la capa web:
- Sin credenciales → 401. Password incorrecta → 401.
- **Sin `RUNNERSTATS_PASSWORD` configurada nadie entra**, ni con credenciales
  correctas. Cubre el fallo cerrado.
- Con password → 200 y las carreras en el HTML.
- Las carreras sin muestreos no se marcan como "detalle".

Ejecutado en local contra el SQLite real: la portada rinde las 207 carreras
con totales correctos (1098,80 km, 112,3 h desde el 26 dic 2011). Comprobado
visualmente en escritorio y en móvil (375 px): la tarjeta reflota la fecha a
su propia línea y las métricas quedan legibles.

**Pendiente**:
- Publicar el subdominio (requiere panel de Hetzner y Coolify).
- **Hueco conocido**: no hay formulario de subida. La primera carga en
  producción es copiar el SQLite al volumen a mano. Es ahora el punto 2 del
  backlog.
- Borrar el scaffold Android: sigue bloqueado, comando en el chat.
- Export de Huawei: pedido, 7 días.

**Siguiente**: Formulario de subida, y después el parser de `.fit`.

---

## 2026-09-04 — Formulario de subida: el sitio ya es autónomo

**Qué**:
- Ruta `/importar` con subida múltiple de ficheros. Despacho por extensión:
  el JSON de My Run Stats se importa; los `.fit` avisan de que aún no hay
  parser; el resto informa de formato no soportado.
- El importador de My Run Stats acepta ahora una ruta **o un stream**, así
  que lo que sube el navegador se lee en memoria sin tocar disco. Eso elimina
  de raíz el saneado de rutas.
- Cada fichero informa de su propio resultado: un JSON corrupto o ajeno da un
  mensaje, no un 500 ni tumba la subida entera. Límite de 32 MB con su
  manejador de 413.
- Plantilla base compartida y estado vacío en la portada.

**Por qué**: Sin esto, poblar producción exigía `scp` del SQLite al volumen.
Con el formulario se sube el export desde el propio móvil.

**Verificado**: 27 tests en verde (9 nuevos). Además de los casos de error,
uno cubre que **la portada rinde con la base vacía**, que es justo el estado
con el que nace producción: sin carreras los agregados de SQL son NULL y los
filtros recibirían None.

Prueba de extremo a extremo con datos reales, arrancando con base vacía:
portada vacía → subida del JSON por el formulario → "207 carreras
importadas" → portada con las 207 y 1098,80 km. Subida de un `.fit` → aviso,
y no entra nada.

Revisado visualmente en escritorio y móvil. Se corrigió un defecto: faltaba
la regla base de `a` en el CSS, así que los enlaces salían en el azul por
defecto del navegador en vez del acento de la casa.

**Siguiente**: Publicar el subdominio, y después el parser de `.fit`.

---

## 2026-09-04 — En producción: https://run.javimendoza.com

**Qué**: Desplegado en el Coolify del Hetzner, pilotando el panel desde el
navegador. Aplicación `runner-stats` en el proyecto Personal / production:
repo público, rama `main`, build pack Dockerfile, dominio
`https://run.javimendoza.com` con puerto interno 8000, volumen
`runnerstats-data` montado en `/app/data` y `RUNNERSTATS_DB` apuntando ahí.

**Hallazgos durante el despliegue**:
- El paso de DNS del plan **no existía**: la zona la sirve Cloudflare (no
  Hetzner, como decía este documento) y tiene un comodín `*.javimendoza.com`
  → 178.105.168.93. `run` ya resolvía.
- **Coolify ignora el `EXPOSE 8000` del Dockerfile** y pone 3000 en dos
  campos independientes. Documentado en `DEPLOY.md`.
- El panel avisa de "Cannot connect to real-time service" y hay una alerta de
  puertos de firewall. No impidió nada (Livewire responde 200), pero deja sin
  logs de despliegue en vivo. Pendiente de mirar, es del servidor.

**Verificado** contra el dominio real, no contra el panel:
- `server: gunicorn` y `www-authenticate: Basic realm="RunnerStats"`, o sea
  que responde la aplicación y no una página del proxy.
- Certificado Let's Encrypt válido para `run.javimendoza.com`.
- HTTP redirige a HTTPS.
- **Fallo cerrado confirmado en producción**: 401 sin credenciales, con
  usuario sin contraseña y con contraseña inventada. `/importar` también.

**Pendiente del usuario**: poner `RUNNERSTATS_PASSWORD` en las variables de
entorno de Coolify. Hasta entonces la web queda cerrada a todo el mundo, que
es el estado correcto. La contraseña la teclea él: no introduzco credenciales
en formularios.

**Siguiente**: con la contraseña puesta, entrar en `/importar`, subir el JSON
y ver las 207 carreras. Después, el parser de `.fit`.

---

## 2026-09-04 — Panel: estadísticas, récords, filtros y gráficas

**Qué**: La portada era una lista plana de 207 filas. Ahora tiene cabecera con
kilómetros totales, tiles (mejor ritmo, carrera más larga, media por carrera),
récords por banda de distancia, filtro por año y dos gráficas en SVG generado
en servidor: kilómetros por año y evolución del ritmo.

**Por qué**: Con los datos reales cargados, la lista sola se quedaba corta.
Todo lo añadido se sostiene solo con el resumen, así que aplica a las 207
carreras sin esperar al parser de `.fit`.

**Decisiones**:
- Sin librería de gráficas ni CDN. `graficas.py` calcula geometría y la
  plantilla pinta el SVG. Encaja con el "CSS plano" del resto de subdominios.
- Los récords son **por carrera completa**, no por ventana rodante, y la UI lo
  dice. El mejor 5K dentro de una carrera más larga necesita muestreos.
- Un récord de banda es el mejor **ritmo**, no el mejor tiempo: en la banda de
  5 km caben carreras de 5,0 y de 5,9, así que comparar tiempos sería comparar
  distancias distintas.
- Al filtrar, las gráficas mantienen los 15 años y resaltan el año elegido.

**Verificado**: 35 tests (8 nuevos). Los de análisis no clavan números a mano:
recalculan el resultado desde el JSON y lo comparan con el que da SQL —
totales, filtro de 2012 (33 carreras, 227,4 km), mejor ritmo y récords de las
bandas 5K y 10K. Cubierto también que 2019 no aparece como año disponible y
que una base vacía no revienta.

Revisado en el navegador, donde salieron dos fallos que los tests no ven:
- Las barras no resaltadas usaban `--surface-2` y **desaparecían** contra el
  fondo de la tarjeta. Se añadió `--marca-contexto`.
- La línea de medianas **cruzaba 2019**, que no tiene ni una carrera,
  dibujando continuidad inexistente. Ahora se parte en los huecos.

**Siguiente**: el parser de `.fit`, que desbloquea zonas de FC, eficiencia
cardiovascular, detalle por carrera y récords por ventana rodante.

---

## 2026-09-04 — Parser de .fit, webhook de auto-deploy y tiempo en los récords

**Qué**:
- **Parser de `.fit` del Amazfit**. Es la última fuente que faltaba y la de
  fidelidad completa: llena `carrera` desde el mensaje `session` y `muestreo`
  con los puntos a 1 Hz (GPS, altitud, FC, cadencia, velocidad y distancia
  acumulada). Conectado al formulario de subida.
- **Webhook de auto-deploy** creado en el repo (id 674567388, `push`, JSON)
  apuntando a Coolify. Le falta el secreto, que no manejo yo.
- Los récords muestran ahora el **tiempo real de esa carrera** además del
  ritmo. Se siguen eligiendo por ritmo: en la banda de 5 km caben carreras de
  5,0 y de 5,9 km, así que ordenar por tiempo compararía distancias distintas.

**Verificado**: 48 tests (12 nuevos). Los del parser no clavan constantes:
contrastan contra el propio mensaje `session` del fichero, que es el resumen
que calculó el reloj.
- Distancia, duración, FC media/máx, desnivel y calorías cuadran con `session`.
- El instante de inicio se interpreta en UTC (2026-09-02 06:06:24 Z).
- 3603 muestreos a 1 Hz sin un solo hueco de tiempo.
- **La cadencia sale ~156 spm, no ~77**: se contrasta contra `total_strides`
  (9302 pasos / 3602 s x 60 = 155). Es la trampa del factor 2.
- El GPS convertido de semicírculos cae en Madrid y dentro de rango válido.
- La distancia acumulada es monótona, empieza en 0 y cierra en el total.
- Los huecos del sensor siguen siendo NULL (92 de FC, 49 de cadencia): faltar
  es un dato, no se rellena ni se pone a cero.
- Reimportar no duplica ni deja muestreos huérfanos, y borrar la carrera los
  arrastra por CASCADE.
- Un fichero corrupto da un mensaje, no un 500.

**Siguiente**: vista de detalle por carrera, que es lo que da sentido a tener
los muestreos: gráfica de FC y ritmo, zonas y mapa.

---

## 2026-09-04 — Agrupación configurable en la gráfica de volumen

**Qué**: La gráfica de kilómetros pasa de ser fija por año a tener un selector
de año, mes, semana (lunes a domingo) o carrera.

**Decisiones que salieron al construirlo**:
- **Los periodos vacíos se rellenan a cero.** Al agrupar por mes salían 80
  barras en vez de 177 porque los meses sin carreras no existen en la tabla,
  y eso pegaba "mar 12" con "may 12" como si fueran consecutivos. Es el mismo
  fallo que la línea cruzando 2019. Ahora la serie es continua.
- **Agrupar por año ignora el filtro; el resto lo respeta.** El histórico
  completo por semanas serían ~770 barras en 640 px, menos de un píxel cada
  una. Sin año filtrado, mes y semana se recortan a los últimos 36 y 52
  periodos, y el subtítulo lo dice.
- El grosor de barra y el hueco se adaptan a la densidad: por debajo de 6 px
  de banda el separador de 2 px desaparece, porque se comería la marca.

**Verificado**: 54 tests (7 nuevos). Entre ellos, que la semana empieza en
lunes de verdad (`weekday() == 0` en las 48 semanas de 2012 y siete días
exactos entre una y la siguiente), que 2019 aparece a cero y la serie de años
es continua, y que agrupar por carrera da exactamente una barra por carrera
sumando los mismos kilómetros.

Un test cazó un bug real: con una agrupación desconocida la consulta caía en
"año" pero el relleno de huecos seguía ramificando por la clave inválida y
petaba. Ahora se normaliza antes de usarla en ningún sitio.

**Siguiente**: vista de detalle por carrera.

---

## 2026-09-05 — Totales a tarjetas

**Qué**: Los kilómetros totales, el número de carreras y el tiempo salen de la
cabecera y pasan a tarjetas junto al resto de métricas. Seis tiles en dos
filas; la cabecera se queda con el título y el periodo.

**De paso, un 500 latente corregido**: `mejor_ritmo` solo mira carreras de 3 km
o más y devuelve None si no hay ninguna. La plantilla lo pasaba al filtro de
ritmo sin comprobarlo, así que un año filtrado con solo carreras cortas habría
reventado. Ahora muestra un guion, y hay un test que lo cubre.

**Verificado**: 55 tests. Revisado en el navegador: las seis tarjetas caen en
dos columnas en móvil y tres en escritorio.

---

## 2026-09-05 — Auto-deploy funcionando

**Qué**: El webhook de GitHub queda operativo. Push a `main` y producción se
actualiza sola en ~20 s, sin entrar al panel de Coolify.

**Lo que costó descubrirlo**, anotado en `DEPLOY.md`:
- Coolify contesta **200 OK a cualquier POST** y descarta por dentro lo que no
  lleve firma válida. El verde de GitHub nunca fue prueba de nada; la única
  comprobación válida es mirar si el sitio cambia.
- El webhook acabó apuntando a la propia página de ajustes de GitHub en vez de
  al endpoint de Coolify, así que GitHub se hacía POST a sí mismo y devolvía
  403 con su propia página de error.
- Reparar la URL por la API **borra el secreto**: un `PATCH` de `config` sin
  reenviar `config.secret` lo deja vacío.

**Verificado**: entrega con firma → 200 → producción sirviendo los totales en
tarjetas ~20 s después, sin intervención manual. Quedaban dos commits sin
desplegar (`39adf0b` y `262398a`) y han subido los dos.

---

## 2026-09-05 — Importador de Nike y deduplicación entre fuentes

**Qué**: Llegó el export completo de Nike (269 TCX, 152 MB, 2011-2026). Se
escribió el importador, un módulo de deduplicación y otro de distancia por
GPS.

**Resultado sobre el corpus real**: de 476 carreras importadas quedan **296
visibles**, 1539 km. Antes eran 207 carreras y 1099 km, todas solo-resumen.
Ahora **267 tienen muestreos y 98 frecuencia cardíaca**.

**Tres cosas que solo se vieron mirando los datos**:
- **Corregida una afirmación mía anterior**: dije que Nike no traía pulso
  basándome en un único fichero de 2013. En el corpus, 98 de 269 sí lo traen.
- **El 41 % de los trackpoints se habrían perdido en silencio.** Nike escribe
  un punto por sensor con marca de milisegundos, y la clave de `muestreo` es
  el segundo. Fusionarlos arregla la colisión y dobla la densidad de campos
  por fila (1,13 → 2,37).
- **La cadencia de Nike ya viene en pasos por minuto**, al revés que en el
  `.fit` del Amazfit. Misma etiqueta, convención opuesta.

**Deduplicación**: 180 fusiones al 5 %, todas ganadas por Nike. Se marca con
`sustituida_por`, no se borra. Quedan 29 carreras de My Run Stats visibles:
5 son únicas de ese día y 24 comparten día pero difieren más del 5 %.

**Verificado**: 68 tests (13 nuevos). Los del importador van contra ficheros
reales del export: que la cadencia cae en rango humano sin doblar, que no
quedan segundos repetidos, que la distancia derivada es monótona y da un
ritmo plausible, y que un TCX de Huawei se rechaza en vez de colarse
etiquetado como Nike. Los de deduplicación comprueban que no se borra nada,
que fuera de tolerancia no se fusiona y que recalcular es idempotente.

**Siguiente**: subir el export a producción (tres o cuatro tandas de 64 MB) y
después la vista de detalle, que ahora sí tiene 267 carreras con muestreos y
98 con pulso a las que sacar partido.

---

## 2026-09-05 — Vista de detalle por carrera

**Qué**: `/carrera/<id>` con resumen, gráficas de ritmo, pulso y altitud,
recorrido GPS y parciales por kilómetro. Las tarjetas de la lista enlazan a
ella. Cada sección aparece solo si la carrera tiene esos datos.

**Un bug gordo encontrado por el camino**: los parciales solo salían en 13 de
296 carreras. El `DistanceMeters` de un trackpoint de Nike es el
**incremento**, no la distancia acumulada, y yo lo estaba guardando tal cual.
Corregido en el importador; los parciales pasan a 206 carreras. Los datos de
producción estaban mal y hubo que reimportar los 269 ficheros.

**Cobertura sobre las 296 visibles**: 206 con ritmo y parciales, 158 con
recorrido, 98 con pulso.

**Verificado**: 81 tests (13 nuevos). Entre ellos, que la distancia acumulada
es monótona y cierra en el total, que las paradas no generan ritmos absurdos
(techo de 33 min/km), que los kilómetros se interpolan con menos de 1,5 s de
error, que el último tramo se marca como parcial y que un resto de 18 m no
genera tramo. Revisado en el navegador, donde se corrigió que el lienzo del
recorrido era cuadrado y dejaba media caja vacía.

**Siguiente**: récords por ventana rodante, que ahora sí son calculables
sobre 206 carreras con distancia acumulada fiable.

---

## 2026-09-05 — Récords por ventana rodante

**Qué**: El mejor 1K/5K/10K extraído de dentro de cualquier carrera, no de
carreras que midieran exactamente eso. Sustituye a los récords por banda, que
eran el apaño provisional. Cada récord enlaza a su carrera.

**Resultado**: 1K en 3:15, 5K en 20:21 (4:04/km) y 10K en 47:34 (4:45/km).
Todos de 2012-2013.

**Un dato falso cazado**: el primer cálculo dio un mejor kilómetro de 1:25,
más rápido que el récord del mundo. Venía de picos aislados en los
incrementos de Nike — 37 tramos por encima de 12 m/s en una carrera de 2018,
con máximos de 79 km/h. Se descuentan esos tramos con el mismo umbral que ya
se usaba para el GPS.

**Verificado**: 84 tests (4 nuevos), incluido uno que mete un salto de 400 m
en una serie sintética y comprueba que no se convierte en récord.

**Limpieza**: eliminados `analisis.records()` y `BANDAS`, huérfanos tras el
cambio. En el proceso borré de más y me cargué `AGRUPACIONES` y `_etiqueta`;
lo detectaron 16 tests y se restauró desde git.

---

## 2026-09-05 — Fuera los textos explicativos de la interfaz

**Qué**: Eliminados los subtítulos que explicaban cómo funciona cada cosa —
cómo se calculan los récords, qué es la media móvil del ritmo, por qué el
mapa se dibuja en local, qué significa el badge de detalle, qué año está
resaltado. La interfaz leía como documentación.

**Qué se conserva y por qué**: los mensajes que dicen un *estado*, no un
método.
- "Últimos N periodos", solo cuando la ventana está recortada: sin él se
  leería una vista parcial como si fuera todo el histórico.
- "Sin muestreos: esta carrera solo tiene resumen", que explica una página
  vacía.
- Los formatos aceptados y el límite de 64 MB en la subida, que son
  accionables.

El porqué de cada cálculo sigue en `DECISIONS.md`, que es su sitio.

**Huérfanos retirados**: `analisis.carreras_con_muestreos()` y el parámetro
`sub` del macro de gráficas, que solo existían para los textos eliminados.

---

## 2026-09-05 — Reordenada la vista de detalle

**Qué**: A petición del usuario.
- Cabecera a la izquierda en tres líneas: distancia, duración (en blanco, con
  el mismo peso que la distancia) y fecha (apagada).
- El recorrido sube a la cabecera como **miniatura** a la derecha; deja de ser
  una sección propia.
- Tarjetas reducidas a tres: ritmo medio, FC media y FC máxima. El ritmo
  medio sale de la cabecera y pasa a tarjeta.
- Los parciales suben justo detrás de las tarjetas y pasan de tarjetas a
  **filas**, con el mejor en color de acento.

**Nota**: se dejan de mostrar desnivel, calorías, muestreos y dispositivo. Los
datos siguen en la base; solo salen de la pantalla.

**Verificado**: 84 tests. Se corrigió uno que pasaba por casualidad —
comprobaba que existiera la palabra "Recorrido" y la encontraba en el
`aria-label` del SVG, así que habría seguido en verde con la sección
eliminada. Ahora comprueba la miniatura y que la traza no esté duplicada.

---

## 2026-09-05 — Etiquetas de eje solapadas

**Qué**: En la gráfica de volumen las dos últimas etiquetas se pisaban ("28
jul" encima de "2 sep").

**Causa**: se repartían cada N barras desde el principio **y además** se
forzaba la última. Con 50 barras y paso 6, la penúltima caía en el índice 48
y la forzada en el 49: pegadas.

**Arreglo**: generar los índices desde el final hacia atrás. La última siempre
sale y el espaciado queda uniforme. La gráfica de ritmo tenía la misma trampa
en el eje de años (`a % 3 == 0 or a == max`), corregida igual; de paso se
ordena el eje, que salía invertido.

**Verificado**: 86 tests (2 nuevos). El de solape recorre las cuatro
agrupaciones con y sin filtro de año y exige 46 px de separación mínima entre
etiquetas, que es lo que ocupa "28 jul" a 9 px.

---

## 2026-09-05 — FC media por parcial

**Qué**: Cada parcial muestra la frecuencia cardíaca media de su tramo,
ocupando el hueco que quedaba entre el kilómetro y el tiempo. Se promedian
los muestreos entre los dos cortes interpolados, así que el tramo coincide
exactamente con el que se cronometra.

**Verificado**: 88 tests (2 nuevos). Se comprueba que cada media cae dentro
del rango real de pulso de la carrera y que la media de las medias se parece
a la media global, y que una carrera sin pulso no se inventa ninguna.

Un test sintético falló al añadirlo porque su helper construía filas sin la
clave del pulso. Se alineó el helper con la forma real de una fila en vez de
hacer defensivo el código de producción: la columna siempre existe.

---

## 2026-09-05 — Cabecera del detalle: cifras centradas, sin tarjetas

**Qué**: A petición del usuario.
- Fila superior: botón de volver a la izquierda, fecha centrada en la página
  y el recorrido a la derecha. La fecha se centra con un grid de tres
  columnas de laterales iguales, para que no quede descentrada por medir
  distinto el botón y la miniatura.
- Debajo, centradas y en blanco: duración, distancia (algo mayor) y ritmo
  medio. La fecha queda por debajo de las tres en tamaño.
- Desaparecen las tres tarjetas.
- La FC media y máxima acompañan al título de su gráfica en gris atenuado,
  en vez de ocupar tarjetas propias.

**Verificado**: 88 tests. Dos comprobaban las tarjetas eliminadas y se
actualizaron para exigir la cabecera nueva y que no quede ninguna `.tile`.
Retirado el `.tiles-3` del CSS, huérfano tras el cambio.

---

## 2026-09-05 — Altitud plana oculta, y cifras centradas por el número

**Qué**:
- La gráfica de altitud desaparece cuando no hay desnivel real. En una
  carrera de cinta la altitud llega como **-1 constante**: un centinela, no
  una medición. Afecta a 14 de las 296 carreras, exactamente las que no
  tienen GPS.
- En la cabecera, la unidad (`km`, `/km`) sale del flujo con posicionamiento
  absoluto para que el centrado lo marque solo el número. Antes se centraba
  el bloque entero y la cifra quedaba desplazada a la izquierda.

**Por qué así**: el criterio no es "es de cinta" sino "el dato no varía". Una
raya plana no dice nada, venga de una cinta o de un llano perfecto, y evita
tener que deducir el tipo de carrera desde la ausencia de GPS. El umbral es
solo para la altitud: un pulso estable sí es un dato.

**Verificado**: 91 tests (4 nuevos). Se añadió a `data/nike/` una carrera de
cinta real como muestra, porque el test que lo cubre se saltaba sin ella.

---

## 2026-09-05 — Hueco bajo la fecha en el detalle (móvil)

**Qué**: La cabecera es un grid de tres columnas, así que su altura la marcaba
el elemento más alto: la miniatura del recorrido. Con `height: auto` y una
ruta vertical, la proporción llegaba a 1,6 y a 88 px de ancho ocupaba 141 de
alto, dejando a la fecha con un hueco enorme debajo. 59 de las 158 rutas son
más altas que anchas, así que no era un caso raro.

**Arreglo**: caja de tamaño fijo (96×64, y 76×52 en móvil) dentro de la que el
SVG se ajusta por `preserveAspectRatio`, y la fila pasa a centrar
verticalmente. La cabecera baja de 141 px a 52.

**Verificado**: medido en el DOM a 375 px de ancho — contenedor 375,
cabecera 52 de alto y la miniatura 76×52 pegada al borde derecho.

---

## 2026-09-05 — Unidad en la duración del detalle

**Qué**: La duración lleva su unidad al lado, como ya hacían la distancia y el
ritmo: `h` cuando pasa de la hora y `min` cuando no. Sale del flujo igual que
las otras, así que el centrado lo sigue marcando solo el número.

**Verificado**: 92 tests. El nuevo cubre el corte en 3600 s y que una carrera
de 27 minutos rinde `min`.

---

## 2026-09-05 — 3K en los récords, y una serie de distancia mentirosa

**Qué**:
- Récords: se añade el 3K y se declaran media maratón y maratón, que
  aparecerán solas cuando alguna carrera las cubra.
- La fecha y la carrera de origen suben junto a la etiqueta de distancia, en
  vez de ir en una línea aparte debajo.

**Lo que destapó el 3K**: salía un 3K en 9:59 (3:19/km) dentro de una carrera
cuya media era 4:47/km. Investigando el fichero original, Nike escribió
distancia hasta el segundo 850 de 1228 y luego dejó de hacerlo, atribuyendo a
ese tramo los 4282 m completos. Se descartan ahora las series de distancia que
no cubren al menos el 85 % de la carrera: 2 de 206.

Se verificó antes que el importador no perdía datos — 243 trackpoints → 230
muestreos cubriendo los 1218 s, con la acumulada cerrando exacta.

**Verificado**: 96 tests (3 nuevos), incluido uno que construye una serie que
se corta a los 700 s de 1200 y exige que no salga ni ritmo, ni parciales, ni
récords.

---

## 2026-09-05 — Récords falsos: la serie de distancia no se validaba contra el resumen

**Qué pasó**: El usuario contrastó un récord con la app de Nike y no cuadraba.
Mostrábamos un 5K de 20:21 (4:04/km) en una carrera cuya media es 7:08/km. El
5K real, sumando los parciales que da Nike, es 34:53.

**Causa**: se usaba la serie de distancia punto a punto sin contrastarla con
nada. En esa carrera había **890 s seguidos sin un solo punto de distancia**,
y los incrementos —que suman bien el total— se concentraban en el tramo con
datos. La validación que había miraba solo el span de la serie, así que un
agujero en medio pasaba desapercibido.

**Arreglo**: la serie se valida ahora contra el resumen de la carrera, que sí
es fiable. Tres criterios: cubrir ≥85 % de la duración sin huecos de más de
30 s, sumar la distancia declarada ±10 % y ocupar la duración declarada ±15 %.

**Alcance del error**: de 267 carreras con muestreos se usaban 202; **22 de
ellas tenían la serie mal**. Ahora se usan 180.

**Verificado**: 100 tests. Dos son auditorías sobre el corpus real: que
ninguna serie usada se desvíe más del 15 % del resumen de su carrera, y que
ningún récord sea absurdamente más rápido que la media de la carrera de la
que sale. Medido: desviación mediana −0,1 %, ninguna fuera del ±13 %.

**Lección**: comprobar los extremos de una serie no dice nada de lo que hay
en medio.

---

## 2026-09-05 — Login con pantalla propia, solo contraseña

**Qué**: Se sustituye el basic auth del navegador por una pantalla de login
con la identidad del sitio. **No pide usuario**, solo contraseña, siguiendo
el patrón de Notyo: cookie de sesión con un token HMAC derivado de la propia
contraseña, sin estado que guardar.

La variable de entorno no cambia (`RUNNERSTATS_PASSWORD`), así que no hay que
tocar Coolify. Cambiarla invalida todas las sesiones.

**Verificado**: 104 tests. Los de autenticación se reescribieron para el flujo
real —entrar por el formulario— en vez de mandar cabeceras. Cubren que sin
sesión se redirige al login, que el formulario no pide usuario, que una
contraseña mala devuelve 401 y no da acceso, que salir cierra la sesión, que
sin contraseña configurada se responde 503, y que un `next` absoluto no
convierte el login en un redirector abierto.

---

## 2026-09-05 — Los parciales descuentan el tiempo parado

**Qué**: Nike excluye el tiempo parado de su duración y nosotros lo
incluíamos, así que los parciales salían más lentos que en la app. Ahora el
tiempo se cronometra solo mientras hay movimiento (umbral de 0,3 m/s).

**Dos vías descartadas antes de dar con ella**: la etiqueta `nax:Halt` de Nike
está en todos los trackpoints, no marca las pausas; y filtrar por "distancia
que no crece" no servía porque durante la parada el GPS sigue temblando.

**Efecto**: las 7 carreras con pausa real pasan de +10,5 % a −2,0 % frente a
Nike, y las 7 caen dentro del ±5 %. En la carrera del 2025-05-05 el km 3 pasa
de 9:24 a 6:22 — era una parada, no un mal kilómetro.

De paso, la validación de la serie compara ahora el tiempo en movimiento y no
el span, así que dejan de rechazarse carreras con paradas largas: 183 en vez
de 180.

**Verificado**: 107 tests (3 nuevos con una parada sintética). Auditoría:
mediana −1,16 % frente a la duración de Nike, 163 de 183 dentro del ±5 %.

---

## 2026-09-05 — Portada: tres tarjetas y la carrera más larga entre los récords

**Qué**: A petición del usuario.
- Las tarjetas quedan en tres: carreras, kilómetros y media por carrera.
  Fuera tiempo total, mejor ritmo y carrera más larga.
- Se elimina el récord de 3K.
- La **carrera más larga** pasa a ser el primer récord: distancia como cifra
  principal y su tiempo al lado. Es el único récord que no necesita
  muestreos, sale del resumen.

**Contraste con Nike**: la carrera más larga coincide exacta — 15,01 km en
1:13:56 el 22 abr 2013, igual que marca la app.

**Verificado**: 109 tests, dos nuevos: que la portada tenga exactamente tres
tarjetas y que "Más larga" abra los récords sin rastro del 3K.

---

## 2026-09-05 — Cabecera de la portada al mínimo

**Qué**: Fuera la línea "desde 26 dic 2011" y el enlace a importar. La
cabecera se queda solo con el título; `/importar` sigue accesible por URL,
que es como el usuario quiere usarlo.

**Huérfanos retirados**: al quitar tarjetas en los dos últimos cambios,
`resumen()` había quedado devolviendo tres campos que ya no consumía nadie.
Se eliminan `mejor_ritmo` —que además era una consulta entera muerta— y
`mas_larga`, que ahora cubre `carrera_mas_larga()`. Se conserva `segundos`,
que lo usa un test de auditoría contra el JSON y no cuesta nada en el mismo
agregado.

**Verificado**: 103 tests. Bajan seis porque se retiran los que cubrían los
campos eliminados.

---

## 2026-09-05 — Los récords se precalculan al importar

**Qué**: nueva tabla `record_ventana` con la mejor ventana de cada distancia
dentro de cada carrera, rellenada por `detalle.recalcular_records()` desde
`/importar`. `analisis.records_rodantes()` pasa de recorrer los muestreos a
una consulta con función de ventana.

**Por qué**: 304 ms de los 306 que tardaba la portada se iban en ese barrido.

**Verificado**: 304 ms → 0,41 ms, con los mismos récords (1K 4:00, 5K 22:01,
10K 46:54). Las bases ya existentes se rellenan solas al abrirse (315 ms una
vez). Los tests que importan pasan a llamar a `recalcular_records()`, igual
que hace la web: la caché no se actualiza sola y eso tenía que quedar visible.

---

## 2026-09-05 — Las gráficas obedecen al filtro de año

**Qué**:
- Con un año elegido, la gráfica de kilómetros se agrupa por mes (el chip
  "Año" desaparece: pintaría los quince) y el eje son los doce meses del
  calendario. Un mes sin carreras deja su hueco vacío en vez de no existir.
- La nube de ritmos solo pinta las carreras del año, y su mediana pasa a ser
  mensual en vez de anual.

**Huérfano retirado**: el resaltado de barra (`resaltar`, `.barra.apagada` y
el token `--marca-contexto`) solo servía para marcar el año elegido dentro de
la vista de quince años, que ya no existe.

**Verificado**: 115 tests, 12 nuevos. Los que importan: 2015 —cinco meses con
carreras— sale con los doce meses y las barras solo en enero, febrero, junio,
julio y agosto; 2011, con una sola fila, también sale entero (era justo el
caso en el que el relleno se rendía); la mediana de 2015 da ene-feb-jun-jul-ago
con la línea partida en el hueco de marzo a mayo; y forzar `?agr=anio` con un
año elegido cae en mes.
