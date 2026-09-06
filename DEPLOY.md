# Deploy

**Desplegado el 2026-09-04.** `https://run.javimendoza.com` está en producción
y responde 401 (falta poner `RUNNERSTATS_PASSWORD`).

Mismo patrón que `links.javimendoza.com` y `app.javimendoza.com`: Hetzner +
Coolify, build desde `Dockerfile`, HTTPS automático y auto-deploy al hacer
push a `main`.

## Trampa: Coolify ignora el EXPOSE del Dockerfile

Al crear la aplicación, Coolify puso **3000** por defecto en dos sitios
distintos pese a que el `Dockerfile` declara `EXPOSE 8000`:

1. El puerto interno del dominio.
2. El campo **Ports Exposes** de la configuración general.

Hay que corregir **los dos**. Al cambiar el primero salta un aviso
("Port 8000 is not listed in Ports Exposes") que delata el segundo. Si se
corrige solo uno, el proxy enruta a un puerto donde no escucha nadie.

## 0. Antes de nada: el repo es público

`solotriples12-a11y/RunnerStats` es público, como los otros tres. El código
puede serlo; **los datos no**. `.gitignore` excluye `data/` y `*.db`, y
`.dockerignore` impide además que entren en la imagen. No aflojar eso.

## 1. DNS — ya está hecho

La zona `javimendoza.com` **la sirve Cloudflare** (`otto.ns.cloudflare.com`,
`monroe.ns.cloudflare.com`), no Hetzner, y tiene un **comodín**
`*.javimendoza.com` → `178.105.168.93`.

Comprobado el 2026-09-04: `run.javimendoza.com` ya resuelve a esa IP, igual
que cualquier nombre inventado (`esto-no-existe-xyz123.javimendoza.com`
resuelve al mismo sitio). Y ya responde con un 404 de Traefik, o sea que el
servidor escucha y solo le falta la aplicación.

**No hay que crear ningún registro.** El comodín es DNS-only (apunta a la IP
de origen, no a las IPs de Cloudflare como hace `links`), así que la
validación HTTP-01 de Let's Encrypt funciona sin más.

## 2. Nueva aplicación en Coolify

Panel: <https://coolify.javimendoza.com>

1. **+ New Resource → Application → Public Repository**.
2. **Repository URL:** `https://github.com/solotriples12-a11y/RunnerStats`.
   **Branch:** `main`.
3. **Build Pack:** `Dockerfile`.
4. **Domains:** `https://run.javimendoza.com`.
5. **Port:** `8000`.
6. Activa **HTTPS** (Let's Encrypt) y **Auto-deploy on push**.

## 3. Volumen persistente — IMPRESCINDIBLE

En **Storages**, monta un volumen en `/app/data`.

Sin esto, cada redeploy borra el SQLite y con él los 15 años de histórico.
Es el mismo problema que ya tuviste en `javimendoza.com` con `tracker.db`.

## 4. Variables de entorno

| Variable | Valor |
|---|---|
| `RUNNERSTATS_PASSWORD` | la contraseña de acceso (no hay usuario) |
| `RUNNERSTATS_DB` | `/app/data/runnerstats.db` |

`RUNNERSTATS_PASSWORD` **no puede quedar vacía**: la app falla cerrado y
devuelve 401 a todo. Es deliberado — un despiste de configuración no debe
publicar el histórico.

## 5. Deploy y primera carga de datos

Lanza el deploy. La web pedirá usuario y contraseña y mostrará la portada
vacía, porque la base de producción nace en blanco.

Para poblarla, entra en **`/importar`** y sube el export de My Run Stats
desde el navegador, en el móvil o en el escritorio. No hace falta `scp` ni
tocar el servidor: el fichero se lee en memoria y nunca se escribe en disco.

Los `.fit` del Amazfit se pueden seleccionar, pero de momento el importador
avisa de que aún no hay parser para ellos.

## Cambios futuros: auto-deploy

Push a `main` → Coolify reconstruye y redespliega. El volumen no se toca, así
que los datos sobreviven.

El webhook está dado de alta en el repo (id `674567388`, evento `push`,
content-type JSON) apuntando a
`https://coolify.javimendoza.com/webhooks/source/github/events/manual`.

**Verificado funcionando el 2026-09-05**: push a `main` y producción se
actualiza sola en ~20 s.

**Marcar "auto-deploy" en Coolify no basta**: un repo público necesita el
webhook creado a mano en GitHub Y el *Webhook secret* de Coolify copiado al
campo Secret del webhook. Sin el secreto, Coolify recibe el envío y lo
descarta.

Dos trampas que costaron una tarde:

1. **El Payload URL y el Secret son campos distintos.** Pegar en Payload URL
   el enlace a la propia página de ajustes del webhook hace que GitHub se
   haga POST a sí mismo: 403 y una página de error de GitHub como respuesta.
   El Payload URL correcto es el de `coolify.javimendoza.com`.
2. **`PATCH` sobre el hook borra el secreto.** Cambiar `config.url` por la
   API de GitHub sin reenviar `config.secret` lo deja vacío, y hay que
   volver a pegarlo. Comprobar después con
   `gh api repos/OWNER/REPO/hooks/ID --jq '.config.secret'`.

**Trampa al verificarlo**: GitHub marca la entrega en verde con 200 OK aunque
Coolify la haya descartado. El 200 no prueba nada. La única comprobación
válida es mirar si el sitio cambia:

```bash
curl -s -u usuario:CONTRASEÑA https://run.javimendoza.com/ | grep -o 'algo-nuevo-del-commit'
```

Si hay que desplegar a mano: Coolify → la aplicación → **Actions → Deploy**.
La sesión del panel caduca, así que puede pedir login otra vez.

## Desarrollo local

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
cp .env.example .env    # y pon una RUNNERSTATS_PASSWORD
./.venv/bin/python -m flask --app app run --port 5001
```

Tests: `./.venv/bin/python -m pytest tests/ -q`

## Operar la base de producción por SSH

El acceso está montado como `ssh hetzner` (alias en `~/.ssh/config` a
`javier@178.105.168.93`). La aplicación corre en un contenedor cuyo nombre
lleva el id de Coolify y cambia en cada despliegue, así que se busca por la
imagen en vez de fijarlo:

```
C=$(ssh hetzner 'docker ps --format "{{.Names}}" | grep -v coolify | head -1')
```

El volumen persistente está en `/app/data` y ahí vive `runnerstats.db`. Para
una importación grande —el export de Huawei son 43 MB en 24 ficheros— sale
mejor por aquí que por `/importar`, que tiene el límite de 64 MB por tanda y
va por HTTP:

1. `scp` de los ficheros a `/tmp` del servidor y `docker cp` al contenedor.
2. **Copia de la base antes de tocarla**: `docker exec "$C" cp
   /app/data/runnerstats.db /app/data/runnerstats.db.antes-de-<lo-que-sea>`.
3. Un script que use los importadores de la propia imagen (`sys.path` a
   `/app`), y que llame a `dedup.marcar_duplicadas` y
   `detalle.recalcular_records` al terminar, que es lo que hace `/importar`.
4. **Borrar los ficheros del servidor y del contenedor**: son datos de salud
   y no pintan nada en `/tmp`.

No hace falta parar el contenedor: SQLite aguanta la escritura mientras
gunicorn sirve, y la aplicación abre la base en cada petición.
