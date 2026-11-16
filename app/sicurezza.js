/* Disinnesco dei link: cliccabili solo le fonti affidabili in https, tutto il resto diventa testo. */
"use strict";

var FONTI_AFFIDABILI = ["telegram.org", "consob.it", "bancaditalia.it", "bitget.com", "crypto.news",
  "dev.to", "linkedin.com", "github.com", "blockworks.co", "cointelegraph.com", "binance.com",
  "kaspersky.com"];

function dominioBase(host) {
  var parti = String(host).toLowerCase().replace(/\.+$/, "").split(".").filter(Boolean);
  if (parti[0] === "www") parti = parti.slice(1);
  return parti.slice(-2).join(".");
}

/* opzioni.sempre: nessun link cliccabile (testi e link forniti dall'utente o letti dagli screenshot). */
function disinnesca(url, opzioni) {
  var testo = String(url == null ? "" : url).trim();
  var href = null;
  try {
    var u = new URL(testo);
    if (!(opzioni && opzioni.sempre) && u.protocol === "https:" && !u.username && !u.password &&
        FONTI_AFFIDABILI.indexOf(dominioBase(u.hostname)) >= 0) href = u.href;
  } catch (e) { /* non è un URL: resta testo */ }
  if (href === null) testo = testo.replace(/^http(s?):/i, "hxxp$1:");
  return { testo: testo, href: href };
}

if (typeof module !== "undefined") {
  module.exports = { FONTI_AFFIDABILI: FONTI_AFFIDABILI, dominioBase: dominioBase, disinnesca: disinnesca };
}
