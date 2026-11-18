/* Verifica Bot: gestore offline dell'app installabile.
   Conserva soltanto i file dell'app (pagina, scheda, icone) per aprirla anche senza rete.
   Non vede e non conserva mai risposte, testi o screenshot: restano nella pagina, in memoria.
   Strategia "prima la rete": online si riceve sempre l'ultima versione, offline la copia salvata. */
"use strict";

const CACHE = "verifica-bot-v1";
const ATTESA_RETE_MS = 4000; // rete lenta: oltre questo tempo una pagina già salvata si apre dalla copia
const FILE = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./icone/icona.svg",
  "./icone/icona-32.png",
  "./icone/icona-192.png",
  "./icone/icona-512.png",
  "./icone/icona-maskable-512.png",
  "./icone/apple-touch-icon.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(FILE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys()
    .then((nomi) => Promise.all(nomi.filter((n) => n !== CACHE).map((n) => caches.delete(n))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  // la libreria esterna di lettura e ogni altro sito passano senza essere toccati né salvati
  if (url.origin !== self.location.origin) return;
  const dallaCopia = () => caches.match(req, { ignoreSearch: true })
    .then((salvata) => salvata || (req.mode === "navigate" ? caches.match("./index.html") : undefined));
  const dallaRete = fetch(req).then((res) => {
    if (res.ok && res.type === "basic") {
      const copia = res.clone();
      event.waitUntil(caches.open(CACHE).then((c) => c.put(req, copia)));
    }
    return res;
  });
  // pagine: se la rete tarda, la copia salvata; altrimenti sempre l'ultima versione dalla rete
  const conAttesa = req.mode !== "navigate" ? dallaRete : Promise.race([
    dallaRete,
    new Promise((ok) => setTimeout(ok, ATTESA_RETE_MS)).then(() => dallaCopia().then((c) => c || dallaRete))
  ]);
  event.respondWith(conAttesa.catch(() => dallaCopia().then((c) => c || Response.error())));
});
