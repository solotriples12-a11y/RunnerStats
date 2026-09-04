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
