# Backlog

Ordenado. Los ítems salen al completarse o al matarse explícitamente.

## Bloqueante actual

1. **[Externo, bloqueante de todo lo demás]** Solicitud de Health Kit a
   Huawei. Pasos completados hasta hoy:
   - [x] Cuenta en developer.huawei.com creada y verificada.
   - [x] Proyecto `RunnerStats` creado en AppGallery Connect.
   - [x] App Android `RunnerStats` con package `com.runnerstats` creada.
   - [ ] Solicitar Health Kit en
         https://developer.huawei.com/consumer/en/hms/huaweihealth/
         (NO desde AGC — es un apply form aparte con revisión manual).
   - [ ] Esperar aprobación. Riesgo alto de rechazo para uso personal.
   - Scopes a marcar: los relativos a heart rate, location, cadence,
     speed/distance/altitude samples y activity session summaries.
     Nombres exactos `HEALTHKIT_*` los confirma el propio formulario.

## Próximo (al tener Health Kit aprobado)

2. Cliente Huawei Health Kit como `HuaweiHealthKitSource`: AppAuth-Android
   para OAuth + Retrofit para los endpoints REST. Primera ejecución real
   contra tus datos.

3. Reevaluar la interfaz `CarreraSource` (decidida en DECISIONS pero ahora
   con solo una implementación prevista): mantener o eliminar la
   indirección.

4. `RunningRepository.refreshCarreras()` con sincronización incremental
   (last sync timestamp en DataStore, paginación por bloques de 7 días).

5. Pantalla "Mis Carreras": lista con resumen, observando `Flow` del DAO.

6. Pantalla detalle: gráfica de FC + ritmo. Decisión Vico vs MPAndroidChart
   aquí (registrarla en `DECISIONS.md`).

7. Algoritmo de PRs por ventana rodante: mejor 1K/5K/10K extraído de
   cualquier carrera, no solo de carreras de esa distancia exacta.

8. Pantalla de PRs.

## Después

- Eficiencia cardiovascular (ritmo vs FC) agregada por mes con gráfica.
- Zonas de FC pintadas como bandas de fondo en la gráfica de detalle.
- Scrubbing en gráfica sincronizado con mapa flotante.
- Tracker de desgaste de zapatillas (alertas a 600-800 km acumulados).
- Récord de desnivel positivo por km.

## Plan B

Si Huawei rechaza la solicitud de Health Kit:
- Importador de export ZIP de Huawei Salud (Privacidad → Solicitar datos).
- Implica parser del formato HCY/JSON que entrega Huawei en el email.

## Descartado por ahora

- Cloud sync entre dispositivos.
- Multi-usuario.
- Otros deportes (ciclismo, natación).
- Predicciones ML ("tiempo estimado de tu próxima 10K").
