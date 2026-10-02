importScripts("/static/js/archivos-compartidos.js");

self.addEventListener("install", (evento) => evento.waitUntil(self.skipWaiting()));
self.addEventListener("activate", (evento) => evento.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (evento) => {
    const peticion = evento.request;
    const url = new URL(peticion.url);
    if (url.origin === self.location.origin && url.pathname === "/compartir"
        && peticion.method === "POST" && peticion.mode === "navigate") {
        evento.respondWith(recibir(peticion));
    }
});

async function recibir(peticion) {
    const destino = new URL("/compartir", self.location.origin);
    let datos;
    try {
        datos = await peticion.formData();
    } catch (_) {
        destino.searchParams.set("error", "recepcion");
        return Response.redirect(destino.href, 303);
    }
    try {
        const ficheros = datos.getAll("ficheros").filter((f) => f instanceof File && f.name);
        if (!ficheros.length) {
            destino.searchParams.set("error", "vacio");
        } else if (ficheros.reduce((total, f) => total + f.size, 0) > 64 * 1024 * 1024) {
            destino.searchParams.set("error", "limite");
        } else {
            destino.searchParams.set("envio", await archivosCompartidos.guardar(ficheros));
        }
    } catch (_) {
        destino.searchParams.set("error", "almacenamiento");
    }
    // Una navegacion GET recupera la cookie SameSite=Lax y puede pedir el
    // login sin perder el cuerpo del POST que vino del menu de Android.
    return Response.redirect(destino.href, 303);
}
