/* Hace instalable la web y registra la recepcion de archivos compartidos. */
if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch((error) => {
        console.warn("No se pudo activar la recepción de archivos", error);
    });
}
