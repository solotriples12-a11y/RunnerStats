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
| `RUNNERSTATS_PASSWORD` | la contraseña de acceso (usuario: cualquiera) |
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

**Marcar "auto-deploy" en Coolify no basta**: un repo público necesita el
webhook creado a mano en GitHub Y el *Webhook secret* de Coolify copiado al
campo Secret del webhook. Sin el secreto, Coolify recibe el envío y lo
descarta.

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
