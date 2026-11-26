/* Logica di presentazione (nessun calcolo del verdetto): rischio mostrato, barra, note, tema.
   Spec: docs/superpowers/specs/2026-11-14-verifica-bot-restyling-b2-design.md. Usa SOGLIE di motore.js. */
"use strict";

var _dipAspetto = typeof module !== "undefined" ? require("./motore.js") : null;
function _soglieAspetto() { return _dipAspetto ? _dipAspetto.SOGLIE : globalThis.SOGLIE; }

var MARGINE_PROSSIMITA = 5; // la nota "vicino alla soglia" compare negli ultimi 5 punti di una zona

/* Rischio finale (sempre nella zona del colore); i verdetti vecchi ricadono sul punteggio delle aree. */
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

/* Perché il rischio finale differisce dal punteggio delle aree (null se coincidono o se manca il campo). */
function motivoRegola(v) {
  if (typeof v.rischio_finale !== "number" || v.rischio_finale === v.punteggio_totale) return null;
  if (v.linee_rosse && v.linee_rosse.length) return "linea_rossa";
  if (v.rosso_da_segnalazioni) return "segnalazioni";
  if (v.rosso_da_imitazione) return "imitazione";
  if (v.verde_con_riserva) return "riserva";
  return "prudenza";
}

/* "Vicino alla soglia": solo testo, solo quando il numero è il punteggio delle aree (nessuna regola prevale). */
function notaProssimita(v) {
  var n = rischioFinale(v);
  if (n !== v.punteggio_totale) return null;
  var s = _soglieAspetto();
  if (n <= s.verde && n > s.verde - MARGINE_PROSSIMITA) return "vicino alla soglia di attenzione";
  if (n > s.verde && n <= s.giallo && n > s.giallo - MARGINE_PROSSIMITA) return "vicino alla soglia del rosso";
  return null;
}

/* Tester UX 26/11/2026: il perché del colore in una frase semplice, sotto il titolo.
   cat = { codice: { descrizione, punti } }; motivi = motivi della certezza bassa (assembla.js). */
var MOTIVI_SEMPLICI = {
  sezioni_non_confermate: "non hai guardato i pulsanti per prelevare, pagare o invitare amici",
  nonso_richieste: "hai risposto «Non so» su cosa ti chiede il bot",
  nessun_materiale: "manca il testo o uno screenshot del bot",
  testo_breve: "il testo incollato è troppo breve",
  risposte_contraddittorie: "alcune risposte si contraddicono"
};
var SOGLIA_POCHE_INFO = 5;

function _minuscola(t) { return t.charAt(0).toLowerCase() + t.slice(1); }

function _segnaliPrincipali(v, cat, quanti) {
  var tutti = [];
  Object.keys(v.aree || {}).forEach(function (a) {
    ((v.aree[a] || {}).segnali || []).forEach(function (s) {
      var voce = cat[s.codice];
      var punti = s.fuori_catalogo ? s.punti : voce ? voce.punti : 0;
      if (voce && punti > 0 && tutti.every(function (x) { return x.codice !== s.codice; }))
        tutti.push({ codice: s.codice, punti: punti, testo: _minuscola(voce.descrizione) });
    });
  });
  tutti.sort(function (a, b) { return b.punti - a.punti; });
  return tutti.slice(0, quanti).map(function (x) { return x.testo; });
}

function perche(v, cat, motivi) {
  var segnali = _segnaliPrincipali(v, cat, 2);
  var elenco = segnali.length ? segnali.join("; ") : "alcuni segnali di rischio (dettaglio nel riquadro «Rischio per area»)";
  if (v.verdetto === "rosso") {
    if (v.linee_rosse && v.linee_rosse.length) {
      var rosse = v.linee_rosse.slice(0, 2).map(function (l) { return cat[l.codice] ? _minuscola(cat[l.codice].descrizione) : l.codice; });
      return "Rosso perché: " + rosse.join("; ") + ".";
    }
    if (v.rosso_da_segnalazioni) return "Rosso perché almeno due siti diversi riportano segnalazioni su questo bot.";
    if (v.rosso_da_imitazione) return "Rosso perché il nome imita un marchio noto" + (segnali.length ? ": " + elenco : "") + ".";
    return "Rosso perché: " + elenco + ".";
  }
  if (v.verdetto === "giallo") {
    // segnali di rischio presenti, anche se fuori catalogo (i soli segnali a punti ≤ 0 non contano)
    var presenti = Object.keys(v.aree || {}).some(function (a) {
      return ((v.aree[a] || {}).segnali || []).some(function (s) { return !cat[s.codice] || cat[s.codice].punti > 0; });
    });
    var m = (motivi || []).filter(function (x) { return MOTIVI_SEMPLICI[x]; }).map(function (x) { return MOTIVI_SEMPLICI[x]; });
    var mancano = (m.length ? m.join("; ") : "un'area ha raggiunto il rischio massimo o la certezza è bassa") + ".";
    if (!presenti) return "Nessun segnale di truffa trovato. È giallo solo perché mancano alcune verifiche: " + mancano;
    // punteggio da verde: il giallo nasce dalla prudenza, i segnali presenti sono minori
    if (typeof v.punteggio_totale === "number" && v.punteggio_totale <= _soglieAspetto().verde)
      return "Nessun segnale grave. È giallo perché mancano alcune verifiche: " + mancano + " Da tenere d'occhio: " + elenco + ".";
    return "Giallo per: " + elenco + ".";
  }
  return v.verde_con_riserva
    ? "Nessun segnale di rischio nelle tue risposte; manca però materiale da verificare (testo o screenshot del bot)."
    : "Nessun segnale di rischio rilevante nelle tue risposte e nel materiale.";
}

/* Con molti "Non so" il giallo non dice "nessun segnale grave": dice che gli elementi sono pochi. */
function pocheInformazioni(nonso) { return nonso >= SOGLIA_POCHE_INFO; }

/* Tema mostrato: scelta manuale (chiaro/scuro) oppure automatico, che segue il sistema. */
function temaEffettivo(scelta, scuroDiSistema) {
  if (scelta === "chiaro" || scelta === "scuro") return scelta;
  return scuroDiSistema ? "scuro" : "chiaro";
}

if (typeof module !== "undefined") {
  module.exports = { MARGINE_PROSSIMITA: MARGINE_PROSSIMITA, rischioFinale: rischioFinale, zonaRischio: zonaRischio,
    posizioneIndicatore: posizioneIndicatore, motivoRegola: motivoRegola, notaProssimita: notaProssimita,
    temaEffettivo: temaEffettivo, perche: perche, pocheInformazioni: pocheInformazioni };
}
