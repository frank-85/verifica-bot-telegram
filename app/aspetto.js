/* Logica di presentazione (nessun calcolo del verdetto): rischio mostrato, barra, note, tema.
   Spec: docs/superpowers/specs/2026-11-14-verifica-bot-restyling-b2-design.md. Usa SOGLIE di motore.js. */
"use strict";

var _dipAspetto = typeof module !== "undefined" ? require("./motore.js") : null;
function _soglieAspetto() { return _dipAspetto ? _dipAspetto.SOGLIE : globalThis.SOGLIE; }

var MARGINE_PROSSIMITA = 5; // la nota "vicino alla soglia" compare negli ultimi 5 punti di una zona

/* Rischio finale (sempre nella zona del colore); i verdetti vecchi ricadono sulla media. */
function rischioFinale(v) {
  return typeof v.rischio_finale === "number" && isFinite(v.rischio_finale) ? v.rischio_finale : v.punteggio_totale;
}

function zonaRischio(n) {
  var s = _soglieAspetto();
  return n <= s.verde ? "verde" : n <= s.giallo ? "giallo" : "rosso";
}

/* Percentuale per l'indicatore sulla barra: mai fuori dalla barra. */
function posizioneIndicatore(n) {
  var x = Number(n);
  if (!isFinite(x)) return 0;
  return Math.max(0, Math.min(100, x));
}

/* Perché il rischio finale differisce dalla media (null se coincidono o se manca il campo). */
function motivoRegola(v) {
  if (typeof v.rischio_finale !== "number" || v.rischio_finale === v.punteggio_totale) return null;
  if (v.linee_rosse && v.linee_rosse.length) return "linea_rossa";
  if (v.rosso_da_segnalazioni) return "segnalazioni";
  return "prudenza";
}

/* "Vicino alla soglia": solo testo, solo quando il numero è la media (nessuna regola prevale). */
function notaProssimita(v) {
  var n = rischioFinale(v);
  if (n !== v.punteggio_totale) return null;
  var s = _soglieAspetto();
  if (n <= s.verde && n > s.verde - MARGINE_PROSSIMITA) return "vicino alla soglia di attenzione";
  if (n > s.verde && n <= s.giallo && n > s.giallo - MARGINE_PROSSIMITA) return "vicino alla soglia del rosso";
  return null;
}

/* Tema mostrato: scelta manuale (chiaro/scuro) oppure automatico, che segue il sistema. */
function temaEffettivo(scelta, scuroDiSistema) {
  if (scelta === "chiaro" || scelta === "scuro") return scelta;
  return scuroDiSistema ? "scuro" : "chiaro";
}

if (typeof module !== "undefined") {
  module.exports = { MARGINE_PROSSIMITA: MARGINE_PROSSIMITA, rischioFinale: rischioFinale, zonaRischio: zonaRischio,
    posizioneIndicatore: posizioneIndicatore, motivoRegola: motivoRegola, notaProssimita: notaProssimita,
    temaEffettivo: temaEffettivo };
}
