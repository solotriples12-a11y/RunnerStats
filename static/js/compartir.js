/* Recupera el archivo despues del login y usa el mismo POST que la subida
   manual. Solo se borra cuando el servidor devuelve su resultado. */
(() => {
    const parametros = new URLSearchParams(location.search);
    const id = parametros.get("envio");
    const estado = document.getElementById("estado-compartido");
    const reintentar = document.getElementById("reintentar-compartido");
    const errores = {
        vacio: "No se ha recibido ningún archivo. Vuelve a compartirlo desde el móvil.",
        limite: "Los archivos superan el límite de 64 MB. Compártelos en varias veces.",
        recepcion: "No se pudo recibir el archivo. Vuelve a compartirlo o impórtalo manualmente.",
        almacenamiento: "No se pudo conservar el archivo en el móvil. Prueba a importarlo manualmente.",
    };
    let enCurso = false;

    async function importar() {
        if (enCurso) return;
        enCurso = true;
        reintentar.hidden = true;
        estado.textContent = "Importando…";
        try {
            const envio = await archivosCompartidos.leer(id);
            if (!envio || !envio.ficheros.length) {
                estado.textContent = "El archivo compartido ya no está disponible. Vuelve a compartirlo o impórtalo manualmente.";
                return;
            }
            const datos = new FormData();
            for (const fichero of envio.ficheros) datos.append("ficheros", fichero, fichero.name);
            const respuesta = await fetch("/importar", {
                method: "POST", body: datos, credentials: "same-origin",
            });
            if (new URL(respuesta.url).pathname === "/login") {
                location.replace("/login?next=" + encodeURIComponent(location.pathname + location.search));
                return;
            }
            if (!respuesta.ok && respuesta.status !== 413) throw new Error("Importación pendiente");
            const pagina = new DOMParser().parseFromString(await respuesta.text(), "text/html");
            const contenido = pagina.querySelector("main.container");
            if (!contenido) throw new Error("Respuesta incompleta");
            await archivosCompartidos.borrar(id).catch(() => {});
            document.querySelector("main.container").replaceWith(contenido);
            document.title = pagina.title;
            // Recargar muestra /importar sin volver a enviar el archivo.
            history.replaceState(null, "", "/importar");
        } catch (_) {
            estado.textContent = "No se ha podido completar la importación. El archivo sigue en el móvil; comprueba la conexión y reintenta.";
            reintentar.hidden = false;
        } finally {
            enCurso = false;
        }
    }

    reintentar.addEventListener("submit", (evento) => {
        evento.preventDefault();
        importar();
    });
    if (parametros.has("error")) {
        estado.textContent = errores[parametros.get("error")] || errores.almacenamiento;
    } else if (!id) {
        estado.textContent = "Comparte un archivo desde Android y elige RunnerStats para importarlo.";
    } else {
        importar();
    }
})();
