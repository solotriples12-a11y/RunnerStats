# Decisions

Append-only. No reescribir entradas anteriores; supersedirlas con una nueva.

---

## 2026-05-25 — Stack: Android nativo (Kotlin + Compose + Room)

**Contexto**: Proyecto nuevo, decidir plataforma de base.

**Opciones consideradas**:
- Android nativo (Kotlin + Compose + Room)
- Kotlin Multiplatform (compartir lógica con iOS futuro)
- Flutter

**Decisión**: Android nativo.

**Consecuencias**:
- Solo Android. Sin camino inmediato a iOS.
- Acceso natural al SDK de Huawei Health Kit (oficialmente Android-only).
- Compose + Room es el camino oficial recomendado; ecosistema maduro y bien
  documentado.

---

## 2026-05-25 — Fuente de datos: Huawei Health Kit oficial (OAuth)

**Contexto**: Cuatro alternativas reales — Health Kit oficial, export ZIP
manual desde la app de Huawei Salud, puente vía Strava/Google Fit, o ficheros
`.fit/.tcx` sueltos.

**Decisión**: Health Kit oficial.

**Consecuencias**:
- Requiere registro como desarrollador en Huawei Developers (gratuito) y
  solicitud de Health Kit por scope. La aprobación puede tardar semanas y
  PUEDE SER RECHAZADA.
- A cambio: sincronización automática y datos estructurados.
- Granularidad de muestreo depende de los scopes aprobados; pedir
  `health.activityrecord.read` desde el principio.
- Riesgo abierto: si Huawei rechaza la solicitud para uso personal, pivotar
  al import de ZIP manual. Plan B registrado en `BACKLOG.md`.

---

## 2026-05-25 — Alcance: proyecto personal

**Contexto**: Definir si la app va a distribuirse o es para uso propio.

**Decisión**: Personal.

**Consecuencias**:
- Sin i18n, sin store listing, sin política de privacidad pública, sin
  onboarding extenso, sin gestión de múltiples cuentas.
- La app se firma con keystore propio y se instala vía sideload.
- Las decisiones de diseño priorizan velocidad de iteración sobre pulido.

---

## 2026-05-25 — Modelo de datos: dos tablas (Summary + Muestreo)

**Contexto**: Decidir cómo persistir las carreras y sus puntos segundo a
segundo.

**Decisión**: `CarreraSummary` 1-N `CarreraMuestreo`. Estructura completa en
`ARCHITECTURE.md`.

**Consecuencias**:
- Listas y agregados rápidos (solo tocan `CarreraSummary`).
- Pantalla de detalle hace una query extra, pero solo al abrir la carrera.
- El cálculo de PRs por ventana rodante requiere recorrer muestreos: se hace
  una vez tras cada sync en background, no en cada interacción.

---

## 2026-05-25 — `RunningRepository` agnóstico a la fuente

**Contexto**: Riesgo abierto de que Huawei rechace la solicitud de Health Kit.
Si eso pasa, queremos pivotar al import ZIP sin reescribir la capa de datos
ni la UI.

**Decisión**: Introducir la interfaz `CarreraSource` en `domain/` desde el
día 1. El `RunningRepository` depende solo de esta interfaz. Las
implementaciones (`HuaweiHealthKitSource`, `HuaweiZipImportSource`,
`FixtureSource`) viven en `data/`.

**Consecuencias**:
- Un nivel más de indirección desde el principio, justificado por un riesgo
  concreto (no especulativo).
- `FixtureSource` deja de ser solo una utilidad de tests: es una
  implementación legítima usada durante desarrollo, antes de tener Health Kit
  aprobado.

---

## 2026-05-25 — Pausar implementación de datos hasta tener Health Kit aprobado

**Contexto**: Tras crear el esquema Room, tocaba decidir cómo arrancar la UI
sin tener todavía Health Kit aprobado. Opciones: fixtures sintéticos,
implementar el parser del export ZIP ya, o esperar.

**Decisión**: Esperar a tener Health Kit aprobado por Huawei antes de
escribir más código de la capa de datos o de la UI que consume datos.

**Por qué**:
- Los fixtures sintéticos no informan decisiones de diseño reales — la UI
  diseñada contra datos inventados no sobrevive al primer choque con datos
  reales (CLAUDE.md §1).
- Implementar `HuaweiZipImportSource` solo para desarrollo es código que
  probablemente se tirará si Health Kit es aprobado (CLAUDE.md §2).

**Consecuencias**:
- La abstracción `CarreraSource` queda parcialmente desjustificada: si solo
  va a existir `HuaweiHealthKitSource`, es una indirección especulativa.
  **Reevaluar al llegar al punto 5 del backlog**, no ahora.
- Trabajo pendiente que NO depende de datos (estructura DI, navegación,
  diseño visual con `@Preview` ad-hoc) se puede hacer en paralelo al proceso
  de aprobación, pero solo si aporta valor real.
- Si Huawei rechaza la solicitud, se activa el Plan B (parser ZIP) que ya
  está documentado en `BACKLOG.md`.

---

## 2026-05-25 — Corrección: scopes reales de Health Kit + restricción de acceso

**Contexto**: Al buscar el botón de Health Kit en AppGallery Connect, no
aparecía. Investigación posterior confirmó dos cosas:

1. Los nombres de scopes que había anotado yo (`health.activity.read`,
   `health.activityrecord.read`) eran inventados y NO existen como tal en
   Health Kit. Los reales son de la familia `HEALTHKIT_*_BOTH` /
   `HEALTHKIT_*_READ`.
2. Health Kit no se habilita desde el "Customize menu bar" de AGC. Es un
   servicio restringido que requiere una solicitud aparte en
   https://developer.huawei.com/consumer/en/hms/huaweihealth/. Para apps de
   uso personal sin justificación comercial, la tasa de rechazo es alta y la
   revisión puede tardar semanas.

**Decisión**: Mantener la decisión de "esperar a Health Kit". Se envía la
solicitud oficial con la mejor justificación posible (texto preparado en el
chat). Si Huawei rechaza, se activa el Plan B (parser ZIP), y entonces SÍ
recupera todo su sentido la abstracción `CarreraSource`.

**Consecuencias**:
- Espera de semanas con resultado incierto.
- Riesgo concreto de rechazo: el caso de uso "single user, personal,
  sideloaded, sin política de privacidad pública" no es el perfil que
  Huawei suele aprobar.
- Scopes exactos a marcar en el formulario: a confirmar en la propia
  pantalla del apply (lista cerrada que ofrece Huawei). Se anotarán en una
  nueva entrada de este fichero cuando esté hecho.
