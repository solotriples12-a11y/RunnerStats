// Tooltip de las gráficas.
//
// El <title> nativo de SVG lo pinta el navegador con casi un segundo de
// retardo y en táctil no aparece nunca, porque no hay hover. Esto lo
// sustituye: la marca lleva el texto en data-tip y aquí se pinta al momento,
// con el dedo o con el ratón.
//
// Todo cuelga de `document` y el globo se crea al primer uso, así que da
// igual cuándo se cargue el script.
(function () {
    let globo = null;

    const ocultar = () => { if (globo) globo.hidden = true; };

    function mostrar(marca, x, y, separacion) {
        if (!globo) {
            globo = document.createElement("div");
            globo.className = "tip";
            document.body.appendChild(globo);
        }
        globo.textContent = marca.dataset.tip;
        globo.hidden = false;

        // Encima del puntero y dentro de la ventana: en las marcas de los
        // extremos el globo se saldria por un lado.
        const caja = globo.getBoundingClientRect();
        const izq = Math.min(Math.max(8, x - caja.width / 2),
                             window.innerWidth - caja.width - 8);
        const arriba = y - caja.height - separacion;
        globo.style.left = `${izq}px`;
        globo.style.top = `${arriba < 8 ? y + separacion : arriba}px`;
    }

    const marcaDe = (e) =>
        e.target.closest && e.target.closest("svg.gr [data-tip]");

    // El dedo tapa el sitio que toca, asi que el globo sale mas arriba.
    const separacion = (e) => (e.pointerType === "mouse" ? 12 : 30);

    function alApuntar(e) {
        const marca = marcaDe(e);
        if (marca) mostrar(marca, e.clientX, e.clientY, separacion(e));
        else ocultar();
    }

    // pointerdown ademas de pointermove: en tactil no hay hover, el toque
    // hace de hover, y tocar fuera de una marca cierra el globo.
    document.addEventListener("pointermove", alApuntar);
    document.addEventListener("pointerdown", alApuntar);
    window.addEventListener("scroll", ocultar, { passive: true });
})();
