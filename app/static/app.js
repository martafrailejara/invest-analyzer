/* Interacciones del dashboard: paleta ⌘K, count-up de métricas, estado de envío.
 * Tres primitivas de movimiento, todas respetando prefers-reduced-motion. */
(function () {
  "use strict";
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- Paleta de comandos (N13) ---------- */
  const cmdk = document.getElementById("cmdk");
  const pill = document.getElementById("searchpill");
  if (cmdk && pill) {
    const input = cmdk.querySelector("input");
    const items = Array.from(cmdk.querySelectorAll(".cmdk__item"));
    let visibles = items.slice();
    let activo = 0;
    let previo = null;

    function pinta() {
      items.forEach((el) => el.classList.remove("is-active"));
      if (visibles[activo]) visibles[activo].classList.add("is-active");
    }
    function abre() {
      previo = document.activeElement;
      cmdk.classList.add("is-open");
      cmdk.setAttribute("aria-hidden", "false");
      document.body.style.overflow = "hidden";
      input.value = "";
      filtra("");
      input.focus();
    }
    function cierra() {
      cmdk.classList.remove("is-open");
      cmdk.setAttribute("aria-hidden", "true");
      document.body.style.overflow = "";
      if (previo) previo.focus();
    }
    function filtra(q) {
      const t = q.trim().toLowerCase();
      visibles = items.filter((el) => {
        const coincide = el.textContent.toLowerCase().includes(t);
        el.style.display = coincide ? "" : "none";
        return coincide;
      });
      activo = 0;
      pinta();
    }

    pill.addEventListener("click", abre);
    document.addEventListener("keydown", (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        cmdk.classList.contains("is-open") ? cierra() : abre();
      } else if (cmdk.classList.contains("is-open")) {
        if (e.key === "Escape") cierra();
        else if (e.key === "ArrowDown") { e.preventDefault(); activo = Math.min(activo + 1, visibles.length - 1); pinta(); }
        else if (e.key === "ArrowUp") { e.preventDefault(); activo = Math.max(activo - 1, 0); pinta(); }
        else if (e.key === "Enter" && visibles[activo]) { e.preventDefault(); visibles[activo].click(); }
      }
    });
    input.addEventListener("input", () => filtra(input.value));
    cmdk.querySelector(".cmdk__backdrop").addEventListener("click", cierra);
    items.forEach((el) => el.addEventListener("click", () => { window.location.href = el.dataset.href; }));
  }

  /* ---------- Count-up de la cifra héroe (one-shot) ---------- */
  document.querySelectorAll("[data-countup]").forEach((el) => {
    const objetivo = parseFloat(el.dataset.countup);
    const texto = el.textContent; // formato final renderizado por el servidor
    if (reduceMotion || !isFinite(objetivo)) return;
    const dur = 900;
    const inicio = performance.now();
    function paso(ahora) {
      const p = Math.min((ahora - inicio) / dur, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = (objetivo * eased).toLocaleString("es-ES", {
        minimumFractionDigits: 2, maximumFractionDigits: 2,
      }) + " €";
      if (p < 1) requestAnimationFrame(paso);
      else el.textContent = texto;
    }
    requestAnimationFrame(paso);
  });

  /* ---------- Menú del rail en móvil ---------- */
  const railMenu = document.getElementById("rail-menu");
  const rail = document.getElementById("rail");
  if (railMenu && rail) {
    railMenu.addEventListener("click", () => {
      const abierto = rail.classList.toggle("is-open");
      railMenu.setAttribute("aria-expanded", String(abierto));
    });
  }

  /* ---------- Nombre del activo al pasar el ratón ---------- */
  const catalogoEl = document.getElementById("catalogo-tickers");
  if (catalogoEl) {
    const catalogo = JSON.parse(catalogoEl.textContent);
    document.querySelectorAll('input[list="tickers"]').forEach((el) => {
      const pinta = () => {
        el.title = catalogo[el.value.trim().toUpperCase()] || "";
      };
      el.addEventListener("input", pinta);
      pinta();
    });
  }

  /* ---------- Estado de carga en todos los formularios ---------- */
  document.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", () => {
      const btn = form.querySelector("button[type=submit]");
      if (!btn) return;
      btn.setAttribute("aria-busy", "true");
      if (btn.classList.contains("btn--primary")) btn.textContent = "Ejecutando… ";
    });
  });
})();
