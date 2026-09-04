# Deploy

Pasos para publicar `run.javimendoza.com` la primera vez. Mismo patrón que
`links.javimendoza.com` y `app.javimendoza.com`: Hetzner + Coolify, build
desde `Dockerfile`, HTTPS automático y auto-deploy al hacer push a `main`.

## 0. Antes de nada: el repo es público

`solotriples12-a11y/RunnerStats` es público, como los otros tres. El código
puede serlo; **los datos no**. `.gitignore` excluye `data/` y `*.db`, y
`.dockerignore` impide además que entren en la imagen. No aflojar eso.

## 1. DNS en Hetzner

En la zona DNS de `javimendoza.com`:

1. Añade un registro:
   - **Tipo:** `A`
   - **Nombre:** `run`
   - **Valor:** la IP pública del servidor de Coolify, la misma que los otros
     subdominios (`dig +short app.javimendoza.com`).
   - **TTL:** el por defecto.
2. Si ese servidor tiene IPv6, añade también el `AAAA`.
3. Verifica con `dig +short run.javimendoza.com` antes de seguir.

## 2. Nueva aplicación en Coolify

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

Lanza el deploy. La web responderá pidiendo usuario y contraseña, pero la
base estará **vacía**: todavía no hay formulario de subida (está en el
backlog). Para poblarla la primera vez, copia el SQLite local al volumen:

```bash
scp data/runnerstats.db <usuario>@<ip>:/tmp/runnerstats.db
```

y muévelo al volumen desde el servidor, o usa el file manager de Coolify.

## Cambios futuros

Push a `main` → Coolify reconstruye y redespliega. El volumen no se toca, así
que los datos sobreviven.

## Desarrollo local

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
cp .env.example .env    # y pon una RUNNERSTATS_PASSWORD
./.venv/bin/python -m flask --app app run --port 5001
```

Tests: `./.venv/bin/python -m pytest tests/ -q`
