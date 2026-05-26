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
