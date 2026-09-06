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

---

## 2026-09-04 — Huawei rechaza la solicitud de Health Kit

**Contexto**: La solicitud enviada en mayo de 2026 fue denegada. El riesgo
registrado el 2026-05-25 ("tasa de rechazo alta para uso personal") se
materializó.

**Decisión**: Abandonar Health Kit definitivamente. No se reintenta.

**Consecuencias**:
- Se cae la sincronización automática. Todas las fuentes pasan a ser ficheros
  exportados a mano.
- Se cae el motivo principal para que el proyecto fuese Android nativo
  (ver entrada del pivote a web, más abajo).
- Los HTML de `docs/` (política de privacidad y términos) existían solo para
  el formulario de solicitud. Quedan sin propósito.

---

## 2026-09-04 — Tres fuentes de datos con niveles de fidelidad distintos

**Contexto**: Tras el rechazo se examinaron ficheros reales de cada fuente
disponible. Todos los datos de abajo están verificados sobre exports propios,
no sobre documentación.

**Hallazgos**:

1. **Huawei, export por actividad (TCX)**: solo `Time`, latitud, longitud y
   `AltitudeMeters`. 3606 trackpoints sin una sola pulsación. Cero FC, cero
   cadencia, cero velocidad, cero distancia por punto. Además el XML es
   inválido contra el esquema TCX (`CumulativeClimb` y `CumulativeDecrease`
   como hijos sin namespace de `<Lap>`, fuera de orden). Inservible para
   zonas de FC, eficiencia cardiovascular y cadencia.

2. **Amazfit Cheetah 2 Pro (.fit)**: la fuente más rica con diferencia.
   Muestreo perfecto a 1 Hz sin huecos. Por punto: GPS, altitud, FC (97,4%),
   cadencia (98,6%), velocidad, **distancia acumulada** (98,7%), potencia,
   longitud de zancada, tiempo de contacto, oscilación y ratio vertical.
   A nivel de sesión: distancia, duración, FC media/máx, ascenso, descenso,
   calorías, training effect y `time_in_hr_zone`. Además 9 vueltas
   automáticas de 1 km. Ocupa 135 KB frente a 1,7 MB del TCX del mismo Zepp,
   que además pierde la distancia acumulada y toda la dinámica de carrera.

3. **My Run Stats (JSON)**: 207 carreras del 2011-12-26 al 2026-05-04,
   1098,8 km, 112,3 h. Es la única fuente con histórico largo. Resúmenes
   fiables: `pace` cuadra con `duration/distance` en las 207.

**Decisión**: Usar las tres, cada una en su nivel. `.fit` del Amazfit para
detalle completo; My Run Stats para el histórico largo en resumen; Huawei
como relleno intermedio si su export de privacidad (pendiente, 7 días)
resulta traer FC.

**Consecuencias**:
- Las funciones planeadas NO aplican a todas las carreras por igual. Zonas de
  FC, eficiencia cardiovascular y PRs por ventana rodante solo son calculables
  sobre carreras con muestreos. La capa de análisis debe saber sobre qué
  subconjunto habla, y la UI debe decirlo.
- Se necesita deduplicación entre fuentes: la carrera del 2026-09-02 está en
  Huawei y en el Amazfit a la vez.
- La interfaz `CarreraSource` queda justificada por fin con tres
  implementaciones reales, no hipotéticas. Se mantiene.

---

## 2026-09-04 — Dos trampas de unidades verificadas en los datos

**Contexto**: Ambas producirían resultados incorrectos sin que nada falle.
Se registran aquí porque son invisibles al leer el código.

**Trampa 1 — Cadencia ×2 en el FIT**: `record.cadence` (78) y
`session.avg_running_cadence` (77) vienen en zancadas por minuto **por
pierna**. `lap.avg_cadence` (156) viene ya en pasos por minuto. La cadencia
real es ~156 spm, confirmado por `total_strides` (9302 / 3602 s × 60 = 155).
Hay que normalizar los records ×2 y NO tocar los laps.

**Trampa 2 — Splits parciales en My Run Stats**: el último `km_split` de cada
carrera es la fracción sobrante, y su `time` es tiempo bruto, no ritmo. Coger
el split más rápido sin filtrar da un "mejor kilómetro" de **3:01** que en
realidad son 580 m. El mejor kilómetro real es **4:05** (2022-12-18).
64 s/km de diferencia en una pantalla de récords.

**Decisión**: Documentar ambas aquí y cubrirlas con tests sobre datos reales.

**Consecuencias**: Los `km_splits` de My Run Stats se **descartan** por
completo, no solo se filtran. Motivos: solo los tienen 101 de 207 carreras
(ninguna anterior a 2018), su suma nunca cuadra con la duración (65 de 101
se quedan cortos, mediana −16 s, peor caso −219 s) y el número de splits no
cuadra con la distancia en 65 de 101. Para las carreras del Amazfit las
vueltas de 1 km reales vienen gratis en el FIT. Añadir una tabla para datos
en los que no confiamos sería complejidad especulativa (CLAUDE.md §2).

---

## 2026-09-04 — Pivote: de app Android nativa a web propia

**Contexto**: La entrada del 2026-05-25 eligió Android nativo con un único
argumento de peso: "acceso natural al SDK de Huawei Health Kit (oficialmente
Android-only)". Health Kit ha sido rechazado, así que ese argumento ya no
existe. Las tres fuentes de datos son ficheros que se exportan a mano.

**Opciones consideradas**:
- Seguir en Android nativo.
- Web propia en el servidor Hetzner ya existente, en un subdominio.

**Decisión**: Web propia en `run.javimendoza.com`, responsive para consultar
desde ordenador y móvil. **Supersede la entrada del 2026-05-25 "Stack:
Android nativo"**.

**Stack**: Python + SQLite. Frontend responsive servido por la misma app.
Autenticación mediante basic auth en el proxy inverso.

**Por qué**:
- No queda ningún requisito que ate el proyecto a un móvil. Subir nueve
  ficheros desde el escritorio es más cómodo que desde Android.
- `fitparse` ya está verificado contra un `.fit` real en esta máquina: el
  trozo de más riesgo técnico está probado antes de decidir.
- Desaparecen dos decisiones abiertas de `ARCHITECTURE.md`: la de librería de
  gráficas (Vico vs MPAndroidChart) y la de mapas (Map Kit vs osmdroid vs
  MapLibre). En web ambas son problemas resueltos.
- Los tests dejan de necesitar dispositivo o emulador. El test instrumentado
  de Room nunca llegó a ejecutarse por eso.
- SQLite sobra: 500 carreras a 1 Hz serían ~1,8 M de muestreos.

**Consecuencias**:
- Se borra el scaffold Android (~250 líneas de Kotlin: build Gradle, dos
  entities, dos DAOs, `MainActivity` placeholder y un test nunca ejecutado).
  El diseño del modelo de datos sobrevive intacto: Room es SQLite y las dos
  tablas pasan a SQL sin cambios.
- **Coste nuevo y real: autenticación.** Los datos pasan de un móvil propio a
  internet. Son 15 años de entrenamientos, frecuencia cardíaca y trazas GPS
  que salen y vuelven al domicilio. No puede quedar abierto. Se resuelve con
  basic auth en el proxy: cero código de aplicación, seguro sobre HTTPS,
  sustituible por un login real más adelante sin rehacer nada.
- Coste menor: se pierde el "compartir a la app" desde Zepp. Habrá que
  exportar y subir, aunque desde el móvil se hace igual en el navegador.
- Se valida a posteriori la decisión de pausar del 2026-05-25: de haber
  construido la UI contra fixtures en mayo, hoy se tiraría mucho más que un
  scaffold.

---

## 2026-09-04 — Ajustes al modelo de datos tras ver datos reales

**Contexto**: El modelo del 2026-05-25 se diseñó sin haber visto un solo
fichero. Con tres fuentes reales delante aparecen cambios justificados.

**Decisión**:
- **Añadir `distancia_acumulada_metros` a los muestreos.** El FIT la trae con
  autoridad del reloj (98,7%, monótona, cuadra con el total de sesión). Con
  ella el algoritmo de PRs por ventana rodante es un barrido de dos punteros
  en vez de integrar haversine sobre GPS ruidoso.
- **Añadir `fuente` a la carrera.** Necesario para el nivel de fidelidad y
  para deduplicar entre fuentes.
- **Eliminar `ritmoMedioSegPerKm`.** Es derivable de distancia y duración, y
  en My Run Stats se verificó redundante en las 207 carreras.
- **Eliminar `esRecordPersonal`.** Estado derivado y cacheado que hay que
  recalcular tras cada import. Se calcula al leer.
- **Eliminar `vo2Max`.** No aparece en ninguna de las fuentes examinadas. Se
  añadirá cuando se vea en un fichero real, no antes.

**Consecuencias**:
- Las carreras de My Run Stats solo llenan fecha, distancia, duración y
  fuente. Todo lo demás queda a NULL. El nivel de fidelidad se expresa solo
  con eso, sin necesidad de una columna de tipo.
- Limitación conocida: My Run Stats solo da `date` (YYYY-MM-DD), sin hora.
  Esas carreras se guardan a medianoche. El FIT sí trae timestamp exacto.
- Los timestamps se guardan en UTC. La visualización usa Europe/Madrid.

---

## 2026-09-04 — Infraestructura: Coolify sobre Hetzner, y auth en la app

**Contexto**: Al revisar el proyecto `web-javimendoza` aparece que ya hay tres
subdominios en producción (`javimendoza.com`, `app.` y `links.`) con un patrón
consolidado, y que `javimendoza.com` ya es Flask + gunicorn en Docker.

**Decisión**: Seguir ese patrón en lugar de inventar uno.

- Flask + gunicorn sobre `python:3.12-slim`, puerto 8000, un repo por
  subdominio, build por Dockerfile, Coolify gestiona HTTPS y auto-deploy.
- **Corrige la decisión de auth tomada horas antes en este mismo día**: se
  había elegido basic auth en el proxy inverso. Se cambia a basic auth **en
  la aplicación** (`RUNNERSTATS_PASSWORD`), que es lo que ya hace
  `javimendoza.com` en `/stats` y `/enlaces`. Motivo: es la convención de la
  casa, está probada en este stack y no obliga a tocar la configuración de
  Traefik en Coolify (CLAUDE.md §3).

**Consecuencias**:
- Dos diferencias deliberadas con el patrón de `javimendoza.com`: el guard es
  global en vez de por ruta (aquí nada es público) y falla cerrado si falta
  la variable de entorno.
- El SQLite exige un volumen persistente en `/app/data`. Sin él cada redeploy
  borra el histórico — el mismo problema que ya apareció con `tracker.db`.
- El repo `RunnerStats` es **público**, como los otros tres. Obliga a que
  `.gitignore` y `.dockerignore` excluyan `data/` y `*.db` sin excepción.
- Queda un hueco conocido: no hay formulario de subida, así que la primera
  carga en producción es copiar el SQLite al volumen a mano.

---

## 2026-09-05 — Nike Run Club como fuente principal del histórico

**Contexto**: Llegó el export completo de Nike: 269 TCX, 152 MB, del
2011-12-26 al 2026-07-28. Analizado el corpus entero, no un fichero suelto.

**Corrección de una entrada anterior**: el 2026-09-04 anoté, a partir de un
único TCX de 2013, que Nike no traía frecuencia cardíaca. **Falso para el
conjunto**: 98 de las 269 carreras tienen FC real (media 153 ppm), sobre todo
de 2021 en adelante. Aquel fichero era de una época sin sensor.

**Hallazgos**:
- Cobertura: 202/269 con distancia por punto, 158 con GPS, 99 con cadencia,
  98 con FC, 49 con pausas marcadas.
- Muestreo mediano: un punto cada 2,2 s. 368.828 puntos en total.
- Nike es casi un superconjunto de My Run Stats: 199 fechas comunes, 65
  carreras solo en Nike, **5 solo en My Run Stats**. Rellena 2019 entero (9
  carreras; My Run Stats tenía cero) y llega tres meses más lejos.
- Las distancias concuerdan: mediana de 26 m de diferencia en las 199 fechas
  comunes.

**Decisión**: Nike pasa a ser la fuente principal del histórico. My Run Stats
se conserva por las carreras que solo están ahí.

**Consecuencias**: el histórico pasa de 207 carreras solo-resumen a 296
visibles con 267 con muestreos y 98 con frecuencia cardíaca.

---

## 2026-09-05 — Fusionar los trackpoints de Nike por segundo

**Contexto**: Nike escribe **un trackpoint por sensor**, no un punto completo
por instante: uno lleva solo el pulso, el siguiente solo la posición. Y con
marca de milisegundos.

**Problema**: la clave primaria de `muestreo` es `(carrera_id, timestamp_unix)`
en segundos. Medido sobre 40 ficheros, **el 41 % de los puntos caían en un
segundo ya ocupado** y se habrían perdido en silencio con `INSERT OR REPLACE`.

**Decisión**: agrupar por segundo y combinar campos, quedándose con el primer
valor no nulo de cada uno.

**Consecuencias**: cero colisiones, ningún valor perdido, y la densidad sube
de 1,13 a 2,37 campos con dato por fila. Un fichero de 3768 trackpoints queda
en 1807 muestreos más completos.

---

## 2026-09-05 — Deduplicación: marcar, no borrar; tolerancia del 5 %

**Contexto**: Con Nike dentro, 199 fechas están duplicadas contra My Run
Stats. Hacía falta una regla y decidir si se borra o se oculta.

**Opciones consideradas**:
- Borrar la peor al importar. Rápido, pero irreversible y destruye datos del
  usuario ante una regla que es un juicio, no un hecho.
- Deduplicar en cada consulta. No pierde nada pero complica todas las queries.
- Marcar la perdedora con una columna y filtrarla. Una cláusula por consulta.

**Decisión**: marcar con `sustituida_por`. Tolerancia del **5 %** sobre la
distancia, mismo día natural en UTC. Gana la carrera con más muestreos;
desempate por prioridad de fuente.

**Consecuencias**:
- 180 fusiones sobre el corpus real, todas ganadas por Nike (178 sobre My Run
  Stats, 2 duplicados internos del propio export de Nike).
- Quedan 29 carreras de My Run Stats visibles. De ellas, 5 no tienen ninguna
  carrera de otra fuente ese día; las otras 24 comparten día pero difieren más
  del 5 %.
- **Sensibilidad de la tolerancia**: con 10 % se fusionarían 14 más, con 15 %
  otras 19. Se deja en 5 % porque diferencias del 20-40 % en el mismo día
  suelen ser carreras distintas, no la misma medida por dos sistemas.
- `marcar_duplicadas` recalcula desde cero, así que es idempotente y cambiar
  la tolerancia no deja marcas viejas.

---

## 2026-09-05 — Distancia derivada del GPS como respaldo

**Contexto**: Una de las 269 carreras de Nike (2016-08-29) trae 465 puntos,
321 con GPS y frecuencia cardíaca, pero `DistanceMeters` a 0. El importador
la rechazaba.

**Decisión**: `geo.py` deriva la distancia acumulada por haversine cuando la
fuente no la trae, descartando saltos por encima de 12 m/s (43 km/h) como
error de GPS.

**Por qué se puede**: validado contra dos ficheros con distancia declarada —
0,32 % de error en un TCX de Nike y 0,49 % en uno de Huawei. Los dos relojes
discrepan entre sí un 1,2 % sobre la misma carrera, así que el valor derivado
cae dentro del ruido que ya hay entre dispositivos.

**Consecuencias**: se recupera esa carrera (4102 m a 5:40/km, que además
cuadra con los 4,11 km que My Run Stats tenía ese día). Y queda el módulo
listo para el importador de Huawei, cuyo TCX no trae distancia por punto.

---

## 2026-09-05 — El `DistanceMeters` de un trackpoint de Nike es un incremento

**Contexto**: Al construir la vista de detalle, los parciales por kilómetro
solo salían en 13 de 296 carreras. Los valores de
`distancia_acumulada_metros` eran de 13-68 m y no eran monótonos.

**Hallazgo**: el `DistanceMeters` de un `Trackpoint` de Nike es la distancia
**desde el punto anterior**, no la acumulada que manda el estándar TCX.
Verificado: la suma de los 910 incrementos de una carrera da 6018,0 m, que es
exactamente el `DistanceMeters` de su `Lap`.

**Decisión**: acumular los incrementos al importar. Y al fusionar trackpoints
del mismo segundo, los incrementos se **suman** en vez de quedarse con el
primero, que perdería el resto del metraje de ese segundo.

**Consecuencias**:
- Los parciales por kilómetro pasan de 13 a 206 carreras.
- Los datos ya subidos a producción tenían esa columna mal y hubo que
  reimportar los 269 ficheros.
- **Una librería de TCX no habría evitado esto, lo habría escondido**:
  `python-tcxparser` sobre el mismo fichero devuelve `distance = 12.22` en
  vez de 6018 m, porque coge el último valor asumiendo que es acumulado. El
  resto de campos sí los da bien, así que el error habría pasado
  desapercibido. El fichero de Nike no cumple el estándar TCX.

---

## 2026-09-05 — Vista de detalle: dos gráficas apiladas, no un eje doble

**Contexto**: La vista de una carrera tiene que enseñar ritmo y pulso sobre
el mismo tiempo.

**Decisión**: gráficas **apiladas** compartiendo el eje X, nunca superpuestas
con dos ejes Y. Dos escalas distintas en un mismo plot inventan una
correlación que no está en los datos.

**Otras decisiones de la vista**:
- El ritmo se calcula sobre una ventana móvil de 20 s: el ritmo instantáneo
  entre dos muestras es puro ruido.
- **Las paradas no son un ritmo.** Si en toda la ventana no se cubren 10 m,
  estabas parado; incluirlo daba ejes de hasta 522 min/km que aplastaban la
  serie real contra el borde.
- La escala se recorta a los percentiles 2-98 por el mismo motivo.
- Los kilómetros se **interpolan** entre muestras. A 2,2 s de muestreo,
  redondear a la muestra más cercana mete varios segundos de error por
  kilómetro.
- El último tramo se marca como parcial y no se compara con los demás: es la
  misma trampa que ya nos mordió con los splits de My Run Stats. Por debajo de
  50 m ni se muestra.
- **El recorrido se dibuja en local**, con proyección equirectangular. Pedir
  teselas a un servidor de mapas enviaría a un tercero las coordenadas de por
  dónde corre el usuario. El lienzo toma la proporción del recorrido.
- La página se adapta a lo que hay: de las 296 visibles, 206 tienen ritmo y
  parciales, 158 recorrido y 98 pulso. Una carrera de cinta con pulsómetro
  tiene 855 puntos de FC y ni GPS ni distancia.

---

## 2026-09-05 — Récords por ventana rodante

**Contexto**: Los récords eran "mejor ritmo de una carrera dentro de una banda
de distancia", un apaño mientras no había distancia acumulada fiable. Con 206
carreras que ya la tienen, se puede calcular lo que un corredor entiende de
verdad por "mi mejor 5K": el tramo más rápido de esa distancia extraído de
dentro de cualquier carrera.

**Decisión**: barrido de dos punteros sobre la distancia acumulada,
**interpolando** el instante de arranque. A 2,2 s de muestreo, empezar a
contar en la muestra más cercana mete varios segundos en un récord de 1 km.

Se calcula al vuelo: el barrido completo tarda 0,27 s sobre las 296 carreras,
así que no compensa mantener una tabla derivada.

**Trampa encontrada**: el primer resultado dio un mejor kilómetro de **1:25**,
más rápido que el récord del mundo. La causa son picos aislados en los
incrementos de Nike: una carrera de 2018 tiene 37 tramos por encima de 12 m/s,
con máximos de 79 km/h. Es raro (179 de 206 carreras no tienen ninguno) pero
basta un pico para inventar un récord.

Se descuenta la distancia de los tramos imposibles usando el mismo umbral que
ya se aplicaba al GPS derivado. Con eso los récords quedan en 1K 3:15, 5K
20:21 (4:04/km) y 10K 47:34 (4:45/km), todos de 2012-2013 y todos plausibles.

**Consecuencias**: se elimina `analisis.records()` y las bandas de distancia,
que quedan superseded. Los récords solo cubren las carreras con muestreos, y
la UI lo dice.

---

## 2026-09-05 — Distancias de récord y series de distancia incompletas

**Contexto**: Al añadir el 3K a los récords salió un 3K en 9:59 (3:19/km) en
una carrera cuya media era 4:47/km, lo que obliga a que el resto fuera a
8:10/km. Investigado sobre el fichero original.

**Hallazgo**: Nike escribió incrementos de distancia cada 10 s hasta el
segundo 850 de una carrera de 1228 s, y luego dejó de escribirlos — pero la
suma de esos 86 incrementos da los 4282 m completos de la carrera. El resumen
(distancia y duración) es fiable; su **línea temporal no**, porque atribuye
toda la distancia a dos tercios del tiempo.

Se comprobó que el importador no perdía nada: 243 trackpoints → 230 muestreos
(13 fusionados por segundo) cubriendo los 1218 s, y la acumulada cierra exacta.
El problema está en el fichero.

**Decisión**: descartar la serie de distancia cuando los puntos que la llevan
cubren menos del 85 % de la carrera. Sin serie no hay ritmo, ni parciales, ni
récords por ventana rodante para esa carrera; el resumen se sigue mostrando.

**Consecuencias**: afecta a 2 de 206 carreras. El 3K falso desaparece.

**El caso del 2012-03-13 quedó resuelto y NO era ambiguo**: el usuario mostró
la carrera en la propia app de Nike, con parciales 5'27" 5'51" 5'18" 10'11"
8'06" y media de 7'08"/km. El 5K real es 34:53, no los 20:21 que mostrábamos.
Investigado el fichero: tenía **890 s seguidos sin ningún punto de distancia**
en medio, y los incrementos, que suman bien el total, se concentraban en el
tramo con datos. La validación por span no lo detectaba porque los puntos
llegaban de principio a fin. Ver la entrada del 2026-09-05 sobre validación
contra el resumen.

---

## 2026-09-05 — Distancias de récord: 1K, 3K, 5K, 10K, media y maratón

**Decisión**: declarar también media maratón (21 097 m) y maratón (42 195 m).
No aparecen hasta que alguna carrera las cubra, porque `mejor_ventana`
devuelve None si la carrera no llega a la distancia. Así el panel las añade
solo el día que se corran, sin tocar código.

---

## 2026-09-05 — La serie de distancia se valida contra el resumen de la carrera

**Contexto**: Un récord de 5K salió en 20:21 (4:04/km) dentro de una carrera
cuya media es 7:08/km. El usuario lo contrastó con la propia app de Nike: los
parciales reales son 5'27", 5'51", 5'18", 10'11" y 8'06", o sea un 5K de
34:53. Nuestro dato era falso.

**Principio que faltaba**: el **resumen** de una carrera (distancia y
duración) es fiable — coincide con lo que muestra Nike. La **serie punto a
punto no siempre lo es**, y hasta ahora se usaba sin contrastarla contra nada.

**Tres modos de fallo encontrados en el export**:
1. **Huecos interiores**: 890 s seguidos sin ningún punto de distancia en una
   carrera de 2400. Los incrementos suman el total correcto pero se concentran
   en el tramo con datos, así que el acumulado llegaba a 5 km en 1230 s.
2. **Distancia incompleta**: una serie que solo sumaba el 36 % de los metros
   declarados, lo que daba parciales demasiado lentos.
3. **Línea temporal más larga que la carrera**: 2822 s de muestras para una
   carrera que declara 1932.

**Decisión**: `_serie_fiable()` valida la serie contra el resumen antes de
usarla. Debe cubrir ≥85 % de la duración sin huecos de más de 30 s, sumar la
distancia declarada con ±10 % y ocupar la duración declarada con ±15 %. Si no
la pasa, se intenta derivar del GPS; si tampoco, esa carrera se queda sin
ritmo, parciales ni récords, pero conserva su resumen.

**Consecuencias**: de 267 carreras con muestreos, 180 tienen serie fiable
(antes se usaban 202, 22 de ellas mal). Auditadas las 180: desviación mediana
−0,1 % frente a su propio resumen, **ninguna fuera del ±13 %** y 168 dentro del
±5 %. Los récords quedan en 1K 4:00, 3K 12:38, 5K 22:17 y 10K 47:34, todos
algo más rápidos que la media de su carrera, que es lo esperable.

**Lección de método**: la validación anterior miraba solo el *span* de la
serie (primer y último punto). Pasaba con un agujero de 890 s en medio. Una
comprobación de extremos no dice nada sobre lo que hay dentro.

---

## 2026-09-05 — El tiempo parado no se cronometra

**Contexto**: Los parciales salían más lentos que en la app de Nike. Medido:
7 carreras se pasaban entre un 7 % y un 13 % de su `TotalTimeSeconds`. Nike
excluye el tiempo parado de esa cifra; nuestros muestreos lo incluían.

**Descartado — `nax:Halt`**: Nike marca las pausas con esa etiqueta, pero
aparece en **todos** los trackpoints del fichero (3512 de 3512), así que
indica que la autopausa estaba activada, no dónde hubo pausa. No sirve.

**Descartado — intervalos sin distancia**: durante la pausa la distancia
sigue avanzando un poco (temblor de GPS), así que filtrar por "distancia que
no crece" no cambiaba nada: el error pasaba de +10,5 % a +10,3 %.

**Decisión**: umbral de **velocidad**. Por debajo de 0,3 m/s (1,1 km/h) no se
está corriendo ni andando, se está parado. `en_movimiento()` reescribe el eje
de tiempo descontando esos tramos, y parciales y récords se miden sobre él.

**Calibración sobre el corpus**, probando de 0 a 1,8 m/s:

| v mín | 7 con pausa | 168 que ya cuadraban |
|---|---|---|
| 0,0 | +10,5 %, 0/7 dentro del ±5 % | −0,26 % |
| **0,3** | **−2,0 %, 7/7** | **−1,75 %** |
| 0,6 | −3,4 %, 6/7 | −2,36 % |
| 0,9 | −5,1 %, 4/7 | −3,17 % |

0,3 arregla las 7 con un coste de ~1,5 % en las demás. Umbrales mayores
empiezan a comerse tramos lentos legítimos.

**Consecuencia colateral**: la validación de la serie pasa a comparar el
tiempo **en movimiento** contra la duración declarada, no el span crudo.
Contra el span, una carrera con una parada larga se rechazaría entera. Con el
cambio entran 183 carreras en vez de 180.

**Sesgo conocido**: queda un −1,2 % sistemático, porque el umbral también
descarta momentos lentos legítimos. Es conservador y está medido.

---

## 2026-09-05 — Los récords se guardan en una tabla derivada

**Contexto**: la portada tardaba 1,6 s en producción. El perfil era
inequívoco: `records_rodantes()` se comía 304 ms de los 306 que costaba
renderizar, porque recorría los 222.000 muestreos en cada visita para
recalcular la mejor ventana de cada distancia.

**Opciones consideradas**:
- Cachear en memoria del proceso. Se pierde en cada despliegue y no vale
  para varios workers de gunicorn.
- Precalcular al importar y guardar en SQLite.
- Dejarlo y aceptar la latencia.

**Decisión**: tabla `record_ventana` (carrera, distancia, segundos, inicio),
rellenada por `detalle.recalcular_records()` al importar, junto a la
deduplicación. La consulta pasa a 0,41 ms y devuelve exactamente los mismos
récords (1K 4:00, 5K 22:01, 10K 46:54).

**Consecuencias**: es una caché, así que puede quedarse rancia. Quien importe
sin recalcular verá récords viejos; los tests lo replican llamando a
`recalcular_records()` igual que hace la web, y esa es la única disciplina
que hay. Las bases anteriores a la tabla se rellenan solas la primera vez
que se abren (`db._rellenar_records`, 315 ms de una vez).

---

## 2026-09-05 — Al filtrar un año, las gráficas hablan de ese año

**Contexto**: al elegir un año solo cambiaban las tarjetas, los récords y la
lista. La gráfica de volumen seguía enseñando los quince años con la barra
del año elegido resaltada, y la de ritmo seguía pintando las 207 carreras.

**Decisión**: el filtro manda sobre las dos gráficas.

- Con un año elegido, agrupar por año deja de ofrecerse (pintaría los
  quince) y la agrupación por defecto pasa a ser el mes. Con eso el resaltado
  de barra se queda sin uso y desaparece.
- Los meses de un año filtrado son **los doce del calendario**, no del primero
  al último con carreras. Un mes sin salir no dibuja barra, pero ocupa su
  hueco. Es lo contrario que en la vista "Todo", donde no hay año al que
  estirarse y el eje va del primer dato al último.
- La mediana de la nube de ritmos pasa a ser **mensual**: una sola mediana
  anual para un año no dibuja ninguna evolución. El eje X etiqueta meses.

**Consecuencia**: la vista de año ya no da contexto histórico. Es
deliberado: para comparar años está la vista "Todo", y mezclar las dos cosas
hacía que el filtro no significara nada.

**No cambia**: la agrupación por semana con un año elegido sigue yendo de la
primera semana con carreras a la última. Solo se pidió el año entero para
los meses, y 52 huecos vacíos de enero no aportan lo que aportan doce.

---

## 2026-09-06 — Tooltip propio: entra JavaScript en el proyecto

**Contexto**: los tooltips eran `<title>` nativos de SVG, elegidos por "cero
JavaScript". Fallan en las dos puntas: el navegador los pinta con casi un
segundo de retardo, y en táctil no aparecen nunca, porque dependen del hover.
En un panel que se mira sobre todo desde el móvil, eso es la mitad de los
datos inaccesibles.

**Opciones consideradas**:
- Dejarlo y aceptar que en el móvil no hay dato por marca.
- Una tabla debajo de cada gráfica con los mismos números. Duplica la lista
  de carreras que ya está más abajo, y no resuelve el retardo en escritorio.
- Tooltip propio en JavaScript.

**Decisión**: `static/js/tip.js`, ~50 líneas sin dependencias ni CDN, el
único JavaScript del proyecto. La marca lleva el texto en `data-tip` y el
script lo pinta al instante con `pointermove` (ratón) y `pointerdown`
(dedo). Todo cuelga de `document` y el globo se crea al primer uso, así que
no depende del orden de carga.

**Zonas sensibles**: acertar con el dedo sobre una barra de 3 px o un punto
de radio 3 no es realista. Cada marca va dentro de un `<g>` con un
`<rect>`/`<circle>` transparente más ancho —la banda entera en las barras, 10
px de radio en los puntos—. Tiene que ser `fill: transparent` y no
`fill: none`: con `none` el elemento no recibe el puntero.

**Consecuencias**: sin JavaScript la gráfica se queda muda. Es un panel
privado de una persona, y la lista de carreras de abajo sigue siendo la vista
en tabla de los mismos datos. A cambio, ahora un mes vacío también dice algo
("jul: sin carreras") en vez de ser un hueco mudo.

---

## 2026-09-06 — Las etiquetas del eje salen del ancho del texto

**Contexto**: el eje X ponía como mucho 8 etiquetas (`paso = n / 8`). Con doce
meses eso dejaba enero, marzo, mayo… sin poner, teniendo sitio de sobra: la
banda mide 50 px y "ene" ocupa 16. Con dieciséis años pasaba lo mismo.

**Decisión**: el paso sale del ancho real del texto. Las etiquetas son
monoespaciadas de 9 px, o sea 5,4 px por carácter; se etiqueta una de cada N,
con N el mínimo que deja `ancho + 10 px` entre vecinas. Salen los doce meses,
los dieciséis años, y las 52 semanas siguen recortándose porque "28 jul" pide
42 px y la banda mide 11.

**En la nube de ritmos** no vale un paso fijo: cada etiqueta va bajo su nodo
de mediana, y los nodos caen en el centro de masa de su periodo, que no está
repartido por igual. Ahí se recorren del más reciente hacia atrás y se salta
el que no quepa. La etiqueta de los extremos se recorta al lienzo, porque va
centrada en su nodo y el último nodo cae casi pegado al borde.

---

## 2026-09-06 — El recorrido baja a la fila de las cifras

**Contexto**: el recorrido vivía en la fila de la cabecera, junto a la fecha,
en una caja de 96x64. Ahí no se ve nada, y debajo quedaba una franja de aire
a los lados de las cifras sin usar.

**Decisión**: el `<svg>` pasa a la fila de las cifras, pegado a la derecha,
con el alto exacto de las tres líneas de números (7rem = 1,25 de interlínea
sobre 1,5 + 2,6 + 1,5 rem). La caja crece a 11x7rem, casi cuatro veces el
área anterior.

**El ancho es un tope, no una medida**: el `viewBox` que devuelve `ruta_svg`
ya lleva la proporción real del recorrido (entre 0,45 y 1,6 de alto/ancho),
así que `preserveAspectRatio` encaja la traza dentro de la caja. Una ruta
apaisada llena los 11 rem; una alargada se queda estrecha y centrada. Ninguna
se recorta, y el hueco sobrante es transparente, o sea invisible.

**Las cifras siguen centradas en la página** gracias a una columna vacía a la
izquierda que equilibra a la del recorrido (`1fr auto 1fr`). Sin `gap`: la
columna del recorrido existe aunque la carrera no tenga GPS, y el hueco
descentraba los números 4 px. La separación la da el `padding` de las cifras,
que además tiene que cubrir las unidades ("/km"), que van absolutas y fuera
del flujo.

**Consecuencia en el móvil**: a 375 px no caben las dos cosas y además una
columna vacía. Ahí la rejilla pasa a `1fr auto`, así que los números quedan
centrados en el espacio que deja el recorrido y no en la página. Es el precio
de que el mapa sea más grande justo donde más se mira.

---

## 2026-09-06 — El par cifras+recorrido se centra, y la caja abraza la traza

Supersede a la entrada de hoy "El recorrido baja a la fila de las cifras", que
dejaba las cifras centradas en la página y el mapa pegado al borde derecho.

**Contexto**: así, el conjunto no estaba centrado —tenía todo el aire a la
izquierda y ninguno a la derecha— y en el móvil ni siquiera cabía la columna
vacía que hacía de contrapeso.

**Decisión**: cifras y recorrido son un solo bloque centrado, con el mismo
aire a los dos lados. Una fila flex con `justify-content: center`.

**Y la caja del mapa deja de tener ancho fijo.** Centrar las cajas no basta:
el `viewBox` lleva la proporción real del recorrido, así que dentro de una
caja de ancho fijo una ruta alargada dejaba 46 px de vacío a cada lado, y el
par se veía 23 px a la izquierda del centro aunque las cajas estuvieran
centradas al píxel. Con `width: auto` el ancho sale de la proporción del
`viewBox` y la caja abraza la traza: centrar las cajas pasa a ser centrar lo
que se ve. Queda un `max-width` que solo entra con las muy apaisadas, y ahí
el recorrido llena la caja a lo ancho, así que tampoco sobra nada.

**Medido** con las tres proporciones reales: alargada (1,27) da caja de 88 px
con 83 de traza y el centro del par en 379 contra 380 de la página;
apaisada (0,45) topa en 224 px, con 218 de traza y el centro en 380 clavado.

---

## 2026-09-06 — Las tarjetas centran su contenido

**Contexto**: tarjetas anchas con dos líneas cortas dentro, alineadas a la
izquierda: "Carreras / 207" dejaba dos tercios de la tarjeta vacíos a la
derecha.

**Decisión**: contenido centrado en las tres —tiles, récords y lista de
carreras—.

**Consecuencia en la lista**: la fecha tenía una columna fija de 6,5 rem, así
que todas las fechas empezaban en la misma x y se leían en vertical. Al
centrar cada fila esa alineación se pierde, y una carrera sin pulsómetro
—una métrica menos— queda un poco desplazada respecto a sus vecinas. Es el
precio de no tener el hueco muerto a la derecha.

---

## 2026-09-06 — Favicon: la transparencia se recorta con geometría, no por color

**Contexto**: el icono llega como PNG de 1254 px, una zapatilla sobre un
cuadrado azul redondeado, con el resto de la lámina en blanco. Hay que dejar
ese blanco transparente.

**Lo que no funciona**: relleno por inundación desde los bordes ("todo el
blanco conectado con el borde"). Con umbral bajo (45) no basta: el icono
tiene un halo azulado clarísimo que llega hasta el borde inferior de la
lámina, así que sobrevive una banda gris. Y subiendo el umbral hasta
tragárselo (180), el relleno **se cuela por dentro**: el borde derecho del
icono tiene un resplandor casi blanco, y desde ahí inunda la zapatilla, que
es de un azul pálido. El resultado se ve bien sobre fondo claro y se
descubre solo sobre fondo oscuro: la zapatilla sale negra.

**Decisión**: máscara geométrica. Se recorta a la caja del cuerpo del icono,
medida sobre la imagen (lo que se aleja del blanco más de 250 en suma de
canales): `(42, 40, 1210, 1204)`. Y se enmascara con una superelipse:

- radio **0,2226** del lado, medido bajando por el borde izquierdo hasta que
  alcanza su x mínima (260 px sobre un lado de 1168);
- exponente **2,2**, ajustado sobre siete puntos del borde —la esquina es más
  plana que un círculo, es un *squircle*, como los iconos de iOS—;
- 2 px hacia dentro, porque el píxel del borde ya está mezclado con blanco y
  dejaría una orla clara;
- máscara generada a 4x y reducida, que suaviza el borde sin desenfocarlo.

**Comprobado**: alfa 255 en todo el interior (nada se ha colado), 42.688
píxeles a 0 (las esquinas) y 11.496 intermedios (el borde suavizado). Y
mirado a 16, 32, 64 y 180 px sobre fondo claro y oscuro.

**Se guarda `favicon.ico` con 16/32/48** y un `icono-180.png` para
`apple-touch-icon`. No se guarda el original de 1254 px: el de 180 basta para
regenerar cualquier tamaño menor, y el maestro son estas medidas.
