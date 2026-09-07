# Convenciones de RunnerStats

Lo que no se deduce leyendo el código. Las reglas generales de trabajo están
en el `CLAUDE.md` de la carpeta padre; esto es lo propio de este proyecto.

## Idioma

**Todo en español**: nombres de funciones y variables, comentarios,
docstrings, mensajes de commit, textos de la interfaz. Sin acentos en
identificadores ni en mensajes de commit; sí en los comentarios, docstrings y
en la interfaz.

El vocabulario del dominio es fijo: `carrera`, `muestreo`, `parciales`,
`ritmo` (s/km), `desnivel`, `ventana rodante`, `fuente`.

## Los datos mandan sobre la documentación

Ningún formato de los que se importan está bien documentado, y varios mienten.
La forma de trabajar que ha funcionado:

1. **Mirar el fichero real antes de escribir el parser.** Cada importador
   nació de volcar campos y contar cobertura, no de leer una especificación.
2. **Contrastar contra una segunda fuente.** Los parciales se validaron
   contra los tiempos por kilómetro del propio reloj; los récords, contra la
   app de Nike. Cuando dos fuentes discrepan, hay que entender por qué antes
   de elegir.
3. **Escribir en `DECISIONS.md` lo que se descubrió**, con los números. Lo
   caro no es escribir el parser, es volver a descubrir que el
   `DistanceMeters` de Nike es un incremento y no un acumulado.

Casos vistos, todos en `DECISIONS.md`: `total_elapsed_time` contra
`total_timer_time` en el `.fit`, claves sin comillas en el JSON de Huawei,
actividades repetidas tres veces, series de distancia con huecos interiores.

## Nada de dependencias para pintar

Sin librería de gráficas y sin CDN. `graficas.py` devuelve **geometría** —
coordenadas, rutas SVG, etiquetas— y la plantilla pinta el SVG. El único
JavaScript es `static/js/tip.js`, unas 50 líneas para los tooltips.

Reglas de las gráficas, que vienen del skill `dataviz`:

- Nunca dos ejes Y. Dos medidas de escala distinta son dos gráficas.
- Secuencial (intensidad, magnitud) = **un solo tono**, de oscuro a claro.
  Las zonas de FC son esto, no cinco colores.
- El color va en las marcas; las etiquetas usan tokens de texto.
- Antes de dar una paleta por buena, pasarla por
  `scripts/validate_palette.js` del skill. No se estima a ojo.

## Verificar en el navegador, no solo con tests

Los tests no ven que dos etiquetas se pisan ni que un eje truncado convierte
1 ms de temblor en una montaña. Las dos veces que pasó, se descubrió mirando.
Para eso: renderizar la página, servirla con `python -m http.server` y abrirla
con las herramientas de navegador; medir con `getBoundingClientRect` o
`getBBox` en vez de opinar sobre la captura.

## Producción

- **La contraseña no la maneja Claude.** Ni se teclea en formularios ni se
  pasa por curl. Para operar la base está el SSH, documentado en `DEPLOY.md`.
- **Copia de la base antes de tocarla**, siempre, en el mismo volumen.
- **Los ficheros de datos se borran del servidor al terminar.** Son datos de
  salud; no se quedan en `/tmp`.
- El repo es **público**. `data/`, `*.db` y `.env` están fuera de git y de la
  imagen. No aflojar eso.

## Al terminar una iteración

Los cuatro documentos vivos (`ARCHITECTURE`, `DECISIONS`, `BACKLOG`,
`PROGRESS`) se actualizan según la regla del `CLAUDE.md` padre. En este
proyecto, además:

- Si un cambio invalida una entrada de `DECISIONS.md`, **no se reescribe**:
  se añade una nueva que diga a cuál supersede y por qué.
- Los números que aparecen en `README.md` y `ARCHITECTURE.md` (carreras, km,
  cobertura por fuente) se comprueban contra producción antes de tocarlos.
