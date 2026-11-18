/* Disinnesco dei link: cliccabili solo le fonti affidabili in https, tutto il resto diventa testo. */
"use strict";

var FONTI_AFFIDABILI = ["telegram.org", "consob.it", "bancaditalia.it", "bitget.com", "crypto.news",
  "dev.to", "linkedin.com", "github.com", "blockworks.co", "cointelegraph.com", "binance.com",
  "kaspersky.com"];

/* Unica regola del "dominio base" in JS (porting di rete.dominio_registrabile, stesso elenco di suffissi):
   news.bbc.co.uk → bbc.co.uk; un indirizzo IP resta com'è. La usano motore.js, analizzatore.js e assembla.js. */
var SECONDO_LIVELLO = ["co", "com", "org", "net", "gov", "ac", "edu"];

function _eIp(host) {
  var h = host.replace(/^\[|\]$/g, "");
  if (h.indexOf(":") >= 0) return /^[0-9a-f:.]+$/.test(h) && /:.*:/.test(h);
  var m = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(h);
  return !!m && m.slice(1).every(function (o) { return Number(o) <= 255 && (o === "0" || o[0] !== "0"); });
}

function dominioBase(host) {
  var h = String(host).toLowerCase().replace(/^\.+|\.+$/g, "");
  if (_eIp(h)) return h.replace(/^\[|\]$/g, "");
  var parti = h.split(".").filter(Boolean);
  if (parti[0] === "www") parti = parti.slice(1);
  if (parti.length >= 3 && SECONDO_LIVELLO.indexOf(parti[parti.length - 2]) >= 0 && parti[parti.length - 1].length === 2)
    return parti.slice(-3).join(".");
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
  module.exports = { FONTI_AFFIDABILI: FONTI_AFFIDABILI, SECONDO_LIVELLO: SECONDO_LIVELLO,
    dominioBase: dominioBase, disinnesca: disinnesca };
}
