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
