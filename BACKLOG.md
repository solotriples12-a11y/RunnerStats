# Backlog

Ordenado. Los ítems salen al completarse o al matarse explícitamente, y
cuando se matan se dice por qué.

## Siguiente

Nada comprometido. Lo que hay sobre la mesa, por orden de lo que aportaría:

1. **Eficiencia cardiovascular por mes.** Serie de `(ritmo medio, FC media)`
   agrupada por mes: dice si estás corriendo más rápido al mismo pulso, que
   es la pregunta que ninguna app contesta bien. Aplica a las 136 carreras
   con FC, que son suficientes para una tendencia.
2. **Mapa de la ruta con scrubbing** sincronizado con las gráficas de
   detalle: mover el cursor por la gráfica de ritmo y ver dónde ibas.
3. **Desgaste de zapatillas**, con aviso a los 600-800 km. Necesita un
   modelo nuevo (par de zapatillas, fecha de estreno, carreras asignadas) y
   una forma de asignar carreras; es el ítem más caro de los tres.
4. **Récord de desnivel positivo por kilómetro.** Barato, pero solo cuatro
   carreras traen desnivel: esperar a tener más `.fit`.

## Lo que el `.fit` trae y no se usa

Están importados los tres `.fit` y la vista de detalle ya enseña zonas de FC,
potencia y contacto con el suelo. Sigue habiendo en el fichero, sin usar:

- efecto de entrenamiento aeróbico y anaeróbico (3,6 / 0,1 en la del 2 sep)
- oscilación y ratio vertical, longitud de zancada
- velocidad ajustada por pendiente (`Equivalent Speed`)

Se dejaron fuera a conciencia: cabían como tarjetas y llenaban el detalle de
números que no se leen (`DECISIONS.md`, 2026-09-07). Recuperarlos es enseñar,
no importar.

## Pendiente de una acción tuya

- **`docs/index.html`, `docs/privacy.html`, `docs/terms.html`**: se crearon
  solo para el formulario de Health Kit, que fue rechazado. No los sirve
  nadie. Confirmar borrado.
- **Carrera del 2026-03-11**: se borró de producción a mano. Si algún día se
  reimporta el export de Nike entero, volverá: no hay marca de "descartada".

## Hecho

- Esquema SQLite y los cinco importadores, con tests: My Run Stats, Nike
  (`.tcx`), Amazfit (`.fit`), Huawei (export de privacidad, JSON) y Huawei
  (TCX de la app).
- Deduplicación entre fuentes, que **cuenta datos y no filas**, y fusión de
  las versiones de una carrera campo a campo.
- Publicado en `https://run.javimendoza.com`: Coolify, volumen persistente,
  auto-deploy al hacer push, login de una sola contraseña.
- Portada: tarjetas, récords por ventana rodante precalculados, filtro por
  año, gráfica de kilómetros con cuatro agrupaciones y nube de ritmos. Las
  barras son enlaces: llevan al periodo o a la carrera.
- Detalle: cifras, recorrido, parciales con FC por kilómetro, esfuerzo
  (zonas de FC), y gráficas de ritmo, pulso, potencia, contacto y altitud.
- Tooltips propios, favicon y las dos vistas responsive.

## Descartado

- **Huawei Health Kit.** Solicitud rechazada el 2026-09-04. El export de
  privacidad cubre lo mismo sin depender de que aprueben nada.
- **App Android nativa.** Superseded por la web (`DECISIONS.md`, 2026-09-04).
- **`km_splits` de My Run Stats.** No fiables.
- **Strava como fuente.** Desde el 30-06-2026 la API estándar exige
  suscripción de pago, la sincronización Zepp→Strava no rellena histórico y
  no está claro que los muestreos de FC sobrevivan a la subida.
- **Parciales para las carreras de cinta** integrando la serie de velocidad
  de Huawei. Se puede, con un +1,6 % de error, pero una serie escalada al
  resumen cuadra con el resumen por construcción y dejaría de ser una
  comprobación independiente (`DECISIONS.md`, 2026-09-06).
- Cloud sync entre dispositivos, multi-usuario, otros deportes, predicciones
  tipo "tiempo estimado de tu próxima carrera".
