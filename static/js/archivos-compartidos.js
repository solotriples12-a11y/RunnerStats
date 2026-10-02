/* Los archivos esperan en el movil, incluso mientras se inicia sesion.
   Los pendientes caducan en una hora y se limpian al volver a usar la cola. */
globalThis.archivosCompartidos = (() => {
    const CADUCIDAD = 60 * 60 * 1000;

    function abrir() {
        return new Promise((resolver, rechazar) => {
            const peticion = indexedDB.open("runnerstats-compartidos", 1);
            peticion.onupgradeneeded = () => {
                const almacen = peticion.result.createObjectStore("envios", {keyPath: "id"});
                almacen.createIndex("creado", "creado");
            };
            peticion.onsuccess = () => resolver(peticion.result);
            peticion.onerror = () => rechazar(peticion.error);
        });
    }

    async function operar(modo, accion) {
        const base = await abrir();
        try {
            return await new Promise((resolver, rechazar) => {
                const transaccion = base.transaction("envios", modo);
                const peticion = accion(transaccion.objectStore("envios"));
                transaccion.oncomplete = () => resolver(peticion.result);
                transaccion.onabort = () => rechazar(transaccion.error);
                transaccion.onerror = () => rechazar(transaccion.error);
            });
        } finally {
            base.close();
        }
    }

    async function limpiar() {
        await operar("readwrite", (almacen) => {
            const rango = IDBKeyRange.upperBound(Date.now() - CADUCIDAD);
            const peticion = almacen.index("creado").openCursor(rango);
            peticion.onsuccess = () => {
                const cursor = peticion.result;
                if (cursor) {
                    cursor.delete();
                    cursor.continue();
                }
            };
            return peticion;
        });
    }

    return {
        async guardar(ficheros) {
            await limpiar();
            const id = crypto.randomUUID();
            await operar("readwrite", (almacen) => almacen.put({id, creado: Date.now(), ficheros}));
            return id;
        },
        async leer(id) {
            await limpiar();
            return operar("readonly", (almacen) => almacen.get(id));
        },
        async borrar(id) {
            await operar("readwrite", (almacen) => almacen.delete(id));
        },
    };
})();
