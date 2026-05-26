# Architecture — RunnerStats

## Visión
App Android personal que lee carreras desde Huawei Health Kit (OAuth oficial),
las persiste localmente y ofrece análisis estadístico más rico que la app
oficial de Huawei Salud: récords personales por ventana rodante, eficiencia
cardiovascular en el tiempo, gráficas interactivas con zonas de FC y mapa.

## Stack
- Lenguaje: Kotlin
- UI: Jetpack Compose (Material 3)
- Persistencia local: Room
- Asincronía: Coroutines + Flow
- DI: Hilt (introducir en cuanto haya un segundo grafo de dependencias real)
- Red: Retrofit + OkHttp para los endpoints REST de Health Kit
- Auth: AppAuth-Android para OAuth 2.0 contra Huawei Account Kit
- Gráficas: TBD entre Vico (nativo Compose) y MPAndroidChart (más maduro,
  requiere `AndroidView` wrapper). Decisión al implementar pantalla de detalle.
- Mapas: TBD entre Huawei Map Kit, osmdroid (OSM) o MapLibre. Decisión al
  implementar scrubbing en mapa.

## Capas (Clean Architecture ligero)
- `data/` — Room (entities, DAOs), `HuaweiHealthApiService`, `AuthRepository`,
  `RunningRepository`.
- `domain/` — Modelos de dominio, casos de uso (calcular PRs, eficiencia,
  zonas FC). Sin dependencias de Android para poder testearlo en JVM puro.
- `ui/` — Pantallas Compose y ViewModels (StateFlow).
- `app/` — Application, MainActivity, grafo Hilt.

## Modelo de datos local (Room)

```
[ CarreraSummary ] 1 ──< N [ CarreraMuestreo ]
```

### CarreraSummary
Resumen rápido para listas y cálculos agregados.
- `id` (PK; id estable de Huawei si lo expone, si no UUID + hash)
- `fechaInicioUnix`
- `distanciaMetros`
- `duracionSegundos`
- `ritmoMedioSegPerKm`
- `frecuenciaCardiacaMedia`
- `vo2Max` (nullable; no todas las actividades lo traen)
- `desnivelPositivoMetros`
- `desnivelNegativoMetros`
- `esRecordPersonal` (boolean derivado, recalculado tras cada sync)

### CarreraMuestreo
Puntos segundo a segundo. Solo se cargan al abrir el detalle.
- `id` (PK)
- `carreraId` (FK indexado)
- `timestampUnix`
- `frecuenciaCardiaca` (nullable)
- `cadenciaSpm` (nullable)
- `velocidadMs` (nullable)
- `altitudMetros` (nullable)
- `latitud` / `longitud` (nullable; pueden faltar fuera de cobertura GPS)

## Fuente de carreras (agnóstica)
El `RunningRepository` depende de una interfaz `CarreraSource` en `domain/`,
no de un cliente concreto. Esto permite cambiar de fuente sin reescribir la
capa de datos local ni el ViewModel.

```
interface CarreraSource {
    suspend fun fetchCarrerasDesde(timestampUnix: Long): List<CarreraImportada>
}
```

Implementaciones previstas:
- `HuaweiHealthKitSource` — OAuth + REST (camino principal).
- `HuaweiZipImportSource` — parser del export ZIP (Plan B y desarrollo
  offline).
- `FixtureSource` — JSON checked-in para desarrollo sin dispositivo.

## Frontera con Huawei Health Kit
- OAuth 2.0 vía AppAuth-Android.
- Scopes: pertenecen a la familia `HEALTHKIT_*_BOTH` / `HEALTHKIT_*_READ`
  (los nombres exactos dependen de lo que ofrezca el formulario de apply de
  Huawei y se anotarán cuando se confirmen). Lo necesario para running con
  muestreos:
  - Heart rate samples
  - Location/GPS samples
  - Cadence samples
  - Speed / distance / altitude samples
  - Workout / activity session summaries
- Sincronización incremental: query desde `lastSyncTimestamp` (DataStore).
- Paginación: pedir por bloques de tiempo (p. ej. 7 días) y manejar `nextToken`.
- Requisito de runtime: HMS Core en el dispositivo. Desarrollo: teléfono
  Huawei con HMS o emulador con HMS instalado.
- Restricción importante: el acceso a Health Kit requiere una solicitud
  aparte en https://developer.huawei.com/consumer/en/hms/huaweihealth/ con
  revisión manual de Huawei. Tasa de rechazo alta para uso personal.

## Estado y flujo
- Single source of truth: Room.
- ViewModels exponen `StateFlow<UiState>` derivado de `Flow<List<Entity>>` del
  DAO. La UI nunca lee del repository directamente para datos; solo dispara
  acciones (refrescar, recalcular PRs).

## Cálculos derivados (en `domain/`)
- **PRs por ventana rodante**: mejor 1K/5K/10K extraído de CUALQUIER carrera
  recorriendo muestreos consecutivos con distancia acumulada (no requiere que
  la carrera mida exactamente esa distancia).
- **Eficiencia cardiovascular**: serie temporal de `(ritmoMedio, FCMedia)`
  agrupada por mes; comparativa móvil para detectar mejoras.
- **Zonas de FC**: 5 zonas desde FCMax (`220 − edad` o personalizada). Para
  cada carrera se calcula tiempo por zona.

## Fuera de alcance (MVP)
- Cloud sync entre dispositivos.
- Multi-usuario.
- Otros deportes (ciclismo, natación). Solo running.
- Predicciones tipo "tiempo estimado de próxima carrera".
