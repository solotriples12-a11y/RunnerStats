# Backlog

Ordenado. Los ítems salen al completarse o al matarse explícitamente.

## Hecho

- Esquema SQLite + importador de My Run Stats (207 carreras), con tests.
- Vista de lista responsive con basic auth global.
- Empaquetado Docker y `DEPLOY.md` para `run.javimendoza.com`.
- Formulario de subida en `/importar`. El sitio ya es autónomo: no hace
  falta tocar el servidor para meter datos.
- Publicado en `https://run.javimendoza.com` (Coolify, volumen persistente).
- Panel: tiles de cabecera, récords por banda de distancia, filtro por año y
  dos gráficas (km por año, evolución del ritmo).
- Parser de `.fit` del Amazfit, con la cadencia normalizada a pasos por
  minuto y los muestreos a 1 Hz en la tabla `muestreo`.
- Selector de agrupación en la gráfica de volumen: año, mes, semana y
  carrera. Récords con el tiempo real además del ritmo.
- Importador de Nike Run Club (269 carreras) con fusión de trackpoints por
  segundo y distancia derivada del GPS cuando falta.
- Deduplicación entre fuentes al 5 %, marcando en vez de borrar.

## En curso

1. Publicar el subdominio: DNS, app en Coolify, volumen persistente y
   variables de entorno. Pasos en `DEPLOY.md`. Requiere acceso al panel.

## Próximo

2. Vista de detalle: gráfica de FC + ritmo sobre los muestreos.
3. Algoritmo de PRs por ventana rodante sobre `distancia_acumulada_metros`.
   Solo aplica a carreras con muestreos: la UI debe decirlo.
4. Vista de PRs.

## Esperando

- **Importar el export de Nike en producción**: 269 ficheros, 152 MB. El
  límite por tanda son 64 MB, así que van tres o cuatro tandas desde
  `/importar`.
- **Export de privacidad de Huawei**: solicitado el 2026-09-04, avisan de 7
  días. Al llegar, mirar si `Motion path detail data` trae FC. Si la trae,
  escribir el importador; si no, descartar Huawei como fuente y quedarse con
  las rutas para el mapa. Existe [Hitrava](https://github.com/CTHRU/Hitrava),
  que ya parsea ese formato, como referencia.

## Después

- Deduplicación entre fuentes (la carrera del 2026-09-02 está duplicada).
- Eficiencia cardiovascular por mes con gráfica.
- Zonas de FC como bandas de fondo en la gráfica de detalle.
- Mapa de la ruta con scrubbing sincronizado con la gráfica.
- Tracker de desgaste de zapatillas (alertas a 600-800 km acumulados).
- Récord de desnivel positivo por km.

## Pendiente de una acción tuya

- **Secreto del webhook de auto-deploy.** El webhook ya existe en el repo
  (id 674567388, evento `push`, JSON) y apunta a Coolify, pero le falta el
  secreto compartido. Copia el "Webhook secret" de Coolify (Webhooks →
  GitHub) al campo Secret del webhook en GitHub. Sin eso Coolify rechaza los
  envíos y hay que desplegar a mano.

## Limpieza pendiente

- `docs/index.html`, `docs/privacy.html`, `docs/terms.html`: se crearon solo
  para el formulario de solicitud de Health Kit, que fue rechazado. Sin
  propósito actual. Confirmar borrado.

## Descartado

- Huawei Health Kit. Solicitud rechazada el 2026-09-04.
- App Android nativa. Superseded por la web (`DECISIONS.md` 2026-09-04).
- `km_splits` de My Run Stats. No fiables.
- Strava como fuente: desde el 30-06-2026 la API de tier estándar exige
  suscripción de pago, la sincronización Zepp→Strava no rellena histórico, y
  no está claro que los muestreos de FC sobrevivan a la subida.
- Cloud sync entre dispositivos, multi-usuario, otros deportes, predicciones.
