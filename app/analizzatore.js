/* Analizzatore a regole (zero AI): frasi a rischio nel testo e controllo della stringa di un link.
   Dipende da nome.js (analizzaNome) e sicurezza.js (dominioBase), globali nel browser. */
"use strict";

var _nome = typeof module !== "undefined" ? require("./nome.js") : null;
function _analizzaNome(u, m) { return (_nome ? _nome.analizzaNome : analizzaNome)(u, m); }

/* Negazione legata al verbo e nella stessa frase: "never enter…", "non inserire mai…". */
var NEGAZIONE = /\b(never|do not|don't|dont|non|mai)\s+(\w+\s+){0,2}(share|send|give|enter|type|paste|import|condivid\w*|dar\w*|invia\w*|inser\w*|comunic\w*|incoll\w*|digit\w*)\b/u;
var FINESTRA_NEGAZIONE = 60;
var MAX_FRASE = 120;
var TLD_RISCHIOSI = ["zip", "mov", "top", "xyz", "click", "gq", "tk", "ml", "cf", "ga", "icu", "buzz"];
var SECONDO_LIVELLO = ["co", "com", "org", "net", "gov", "ac", "edu"];

function normalizzaTesto(t) {
  return String(t || "").normalize("NFKC").toLowerCase().replace(/\s+/gu, " ").trim();
}

var _cache = new WeakMap();
function _compila(regola) {
  var r = _cache.get(regola);
  if (!r) { r = new RegExp(regola.pattern, (regola.flags || "u").replace("g", "") + "g"); _cache.set(regola, r); }
  r.lastIndex = 0;
  return r;
}

function _frase(testo, inizio, fine) {
  var margine = Math.max(0, Math.floor((MAX_FRASE - (fine - inizio)) / 2));
  var a = Math.max(0, inizio - margine), b = Math.min(testo.length, fine + margine);
  var f = testo.slice(a, b).trim();
  if (f.length > MAX_FRASE) f = testo.slice(inizio, Math.min(fine, inizio + MAX_FRASE)).trim();
  return (a > 0 ? "…" : "") + f + (b < testo.length ? "…" : "");
}

function analizzaTesto(testo, regole) {
  var t = normalizzaTesto(testo);
  var trovati = {};
  var ordine = [];
  if (!t) return [];
  regole.forEach(function (regola) {
    if (trovati[regola.codice]) return;
    var re = _compila(regola);
    var m;
    while ((m = re.exec(t)) !== null) {
      if (m[0] === "") { re.lastIndex++; continue; }
      // la frase della corrispondenza (fino al punto precedente) + il suo inizio, dove sta il verbo
      var prima = t.slice(Math.max(0, m.index - FINESTRA_NEGAZIONE), m.index + Math.min(m[0].length, 20));
      prima = prima.split(/[.!?\n]/).pop();
      if (NEGAZIONE.test(prima)) continue;
      trovati[regola.codice] = { codice: regola.codice, area: regola.area,
        frase: _frase(t, m.index, m.index + m[0].length) };
      ordine.push(regola.codice);
      break;
    }
  });
  return ordine.map(function (c) { return trovati[c]; });
}

function _registrabile(host) {
  var parti = host.split(".").filter(Boolean);
  if (parti[0] === "www") parti = parti.slice(1);
  if (parti.length >= 3 && SECONDO_LIVELLO.indexOf(parti[parti.length - 2]) >= 0 && parti[parti.length - 1].length === 2)
    return parti.slice(-3).join(".");
  return parti.slice(-2).join(".");
}

/* Marchi in TUTTO l'indirizzo, sottodomini compresi (porting di rete.marchi_nel_host).
   Sito ufficiale (nome registrato = marchio) escluso con i suoi sottodomini;
   nei sottodomini i marchi generici ("wallet") non contano. */
function _marchiNelHost(host, reg, marchi) {
  var etichetta = reg.split(".")[0];
  var piatta = etichetta.replace(/-/g, "");
  if (marchi.some(function (m) { return m[0] === piatta; })) return [];
  var generici = marchi.filter(function (m) { return m[2] === true; }).map(function (m) { return m[0]; });
  var sotto = host === reg ? [] : host.slice(0, -reg.length).replace(/\.+$/, "").split(".")
    .filter(function (x) { return x && x !== "www"; });
  var trovati = [];
  [[etichetta, false]].concat(sotto.map(function (s) { return [s, true]; })).forEach(function (coppia) {
    _analizzaNome(coppia[0], marchi).imitazioni.forEach(function (i) {
      if (trovati.indexOf(i.marchio) >= 0 || (coppia[1] && generici.indexOf(i.marchio) >= 0)) return;
      trovati.push(i.marchio);
    });
  });
  return trovati;
}

function analizzaLink(url, marchi) {
  var testo = String(url || "").trim();
  var u;
  try { u = new URL(testo); } catch (e) { return { valido: false, host: null, segnali: [], avvisi: ["Non è un link valido"] }; }
  var ip = /^\[.*\]$/.test(u.hostname) || /^\d{1,3}(\.\d{1,3}){3}$/.test(u.hostname);
  if ((u.protocol !== "https:" && u.protocol !== "http:") || (u.hostname.indexOf(".") < 0 && !ip))
    return { valido: false, host: null, segnali: [], avvisi: ["Non è un link web (http/https)"] };
  var host = u.hostname.toLowerCase();
  var avvisi = [];
  var segnali = [];
  if (ip) {
    avvisi.push("Il link usa un indirizzo IP numerico al posto di un nome di dominio: i servizi affidabili non lo fanno");
    if (u.protocol === "http:") avvisi.push("Il collegamento non è cifrato (http)");
    return { valido: true, host: host, segnali: segnali, avvisi: avvisi };
  }
  if (/(^|\.)xn--/.test(host) || /[^\x00-\x7f]/.test(host))
    avvisi.push("Il dominio usa caratteri ingannevoli (punycode): può imitare un nome noto");
  var reg = _registrabile(host);
  var tld = reg.split(".").pop();
  if (TLD_RISCHIOSI.indexOf(tld) >= 0) avvisi.push("Estensione del dominio spesso usata per siti usa e getta (." + tld + ")");
  if (u.protocol === "http:") avvisi.push("Il collegamento non è cifrato (http)");
  var imitazioni = _marchiNelHost(host, reg, marchi);
  if (imitazioni.length) {
    var mostrato = host.replace(/^www\./, "");
    segnali.push({ codice: "dominio_con_marchio", area: "tecnica",
      frase: "L'indirizzo " + mostrato + " richiama il marchio " + imitazioni.join(", ") +
        " senza esserne il sito ufficiale" });
  }
  return { valido: true, host: host, segnali: segnali, avvisi: avvisi };
}

if (typeof module !== "undefined") {
  module.exports = { normalizzaTesto: normalizzaTesto, analizzaTesto: analizzaTesto, analizzaLink: analizzaLink };
}
