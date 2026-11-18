/* Dal questionario + controlli automatici al verdetto (schema v1), calcolato dal motore.
   Regole: spec 2026-11-14 §7.3. Usa motore.js, nome.js, analizzatore.js, sicurezza.js. */
"use strict";

var _dip = typeof module !== "undefined" ? Object.assign({}, require("./motore.js"), require("./nome.js"),
  require("./analizzatore.js"), require("./sicurezza.js")) : null;
function _usa(nome) { return _dip ? _dip[nome] : globalThis[nome]; }

var FONTE_RISPOSTA = "risposta dell'utente";
var FONTE_ORIGINE = { screenshot: "lettura automatica dello screenshot", incollato: "lettura automatica del testo incollato" };
var FONTE_NOME = "controllo del nome";
var FONTE_LINK = "controllo del link";
var RISPOSTE_AMMESSE = ["si", "no", "nonso"]; // una domanda può limitarle con "risposte"
var MIN_LETTERE_MATERIALE = 40; // sotto questa soglia il testo non basta come materiale
var MAX_NOTE = 2000;
var FONTE_SPUNTA = "dichiarazione dell'utente (spunta non verificata dallo strumento)";

var NON_FARE_SEMPRE = [
  "Non condividere mai seed phrase, chiavi private, password o codici di accesso",
  "Non inviare denaro per \"sbloccare\" un prelievo, un premio o un livello",
  "Non aprire file ricevuti dal bot e non incollare comandi sul computer"
];
var FARE = {
  rosso: ["Interrompi l'uso del bot e non seguire ulteriori istruzioni",
    "Segnala il bot a Telegram (⋮ → Segnala) e chiudi la chat",
    "Se hai già condiviso codici o inviato fondi: cambia le password, trasferisci i fondi residui su un nuovo wallet e valuta una denuncia alla Polizia Postale"],
  giallo: ["Procedi con la massima cautela e senza inviare denaro",
    "Raccogli informazioni da fonti indipendenti prima di fidarti",
    "Ripeti la valutazione includendo gli screenshot delle sezioni prelievo, pagamenti e inviti"],
  verde: ["Utilizzalo con le normali cautele: nessun controllo può garantire la sicurezza di un servizio",
    "Se in seguito ti chiede denaro, codici o il collegamento del wallet, ripeti la valutazione"]
};

function codiciAutomatici() {
  return ["nome_imita_marchio", "nome_parole_esca", "dominio_con_marchio", "dominio_tld_rischioso", "segnalazione_truffa",
    "recensioni_positive_indipendenti"];
}

/* Domanda condizionale ("mostra_se"): compare solo se la domanda da cui dipende ha una delle risposte indicate.
   Stessa regola per la pagina (cosa mostrare e chiedere) e per il calcolo (cosa conta). */
function domandaVisibile(d, risposte) {
  if (!d.mostra_se) return true;
  return d.mostra_se.risposte.indexOf((risposte || {})[d.mostra_se.codice]) >= 0;
}

function domandeVisibili(questionario, risposte) {
  var out = [];
  questionario.pagine.forEach(function (p) {
    p.domande.forEach(function (d) { if (domandaVisibile(d, risposte)) out.push(d); });
  });
  return out;
}

function risorseDaPayload(p) {
  return { catalogo: _usa("catalogoDaLista")(p.catalogo), questionario: p.questionario, regole: p.regole,
    marchi: _usa("caricaMarchi")(p.marchi) };
}

function _linkValidi(lista) {
  var visti = {}, out = [];
  (lista || []).forEach(function (u) {
    var testo = String(u || "").trim();
    try {
      var url = new URL(testo);
      if ((url.protocol !== "https:" && url.protocol !== "http:") || url.hostname.indexOf(".") < 0) return;
      var base = _usa("dominioBase")(url.hostname);
      if (!visti[base]) { visti[base] = true; out.push({ url: testo, base: base }); }
    } catch (e) { /* ignorato */ }
  });
  return out;
}

function costruisciVerdetto(input, risorse) {
  var cat = risorse.catalogo;
  var username = _usa("normalizzaUsername")(input.username || "");
  if (!username) throw new Error("username mancante");

  var segnali = {};      // codice → segnale (uno per codice)
  var ordine = [];
  var extra = [];        // segnali multipli ammessi (segnalazioni per dominio)
  var contrasti = [];
  var nonVerificato = [];
  var risposte = input.risposte || {};
  // solo le domande visibili contano: quelle condizionali nascoste non si chiedono e non pesano
  var domande = domandeVisibili(risorse.questionario, risposte);
  var visibile = {};
  domande.forEach(function (d) { visibile[d.codice] = true; });
  // domanda che copre ogni codice: la sua o quella che lo assorbe (revisione 18/11, punto 6)
  var domandaDi = {};
  domande.forEach(function (d) { domandaDi[d.codice] = d; });
  domande.forEach(function (d) { (d.assorbe || []).forEach(function (c) { if (!domandaDi[c]) domandaDi[c] = d; }); });
  // ogni domanda accetta solo le sue risposte (la seed phrase: solo Sì o No)
  var mancanti = domande.filter(function (d) { return (d.risposte || RISPOSTE_AMMESSE).indexOf(risposte[d.codice]) < 0; });
  if (mancanti.length) throw new Error("risposte mancanti: " + mancanti.length);

  function metti(codice, testo, fonte, automatico) {
    if (segnali[codice]) {
      if (automatico && segnali[codice].fonte === FONTE_RISPOSTA) { segnali[codice].testo = testo; segnali[codice].fonte = fonte; }
      return;
    }
    var d = domandaDi[codice];
    if (automatico && d) {
      // discrepanza = la risposta nega il segnale (non "Non so"); nelle domande in positivo il segnale scatta col "no"
      var r = risposte[d.codice], rispostaSegnale = d.segnale_se === "no" ? "no" : "si";
      if (r && r !== "nonso" && r !== rispostaSegnale) contrasti.push({ codice: codice, frase: testo });
    }
    segnali[codice] = { codice: codice, tipo_prova: "diretta", testo: testo, fonte: fonte };
    ordine.push(codice);
  }

  // 1. risposte
  domande.forEach(function (d) {
    var codice = d.codice, r = risposte[codice];
    var rispostaSegnale = d.segnale_se === "no" ? "no" : "si"; // domande in positivo: il segnale scatta con "no"
    if (r === "si" && codice === "bot_ufficiale_verificato") {
      // la spunta dichiarata pesa (-50) ma non è una prova diretta: non annulla le segnalazioni né alza la certezza
      segnali[codice] = { codice: codice, tipo_prova: "segnalazione", testo: d.testo, fonte: FONTE_SPUNTA };
      ordine.push(codice);
    } else if (r === rispostaSegnale) {
      // la domanda in positivo non descrive il rischio: nel report si mostra la descrizione del segnale
      metti(codice, rispostaSegnale === "no" ? cat[codice].descrizione : d.testo, FONTE_RISPOSTA, false);
    } else if (r === "nonso") nonVerificato.push("Senza risposta: " + d.testo);
  });

  // 2. controllo del nome (username + nome visualizzato)
  var n = _usa("analizzaNome")(username, risorse.marchi);
  var nv = input.nomeVisualizzato ? _usa("analizzaNomeVisualizzato")(input.nomeVisualizzato, risorse.marchi) : null;
  var marchiImitati = n.ufficiale ? [] : n.imitazioni.map(function (i) { return i.marchio; });
  if (nv && !n.ufficiale) nv.imitazioni.forEach(function (i) { if (marchiImitati.indexOf(i.marchio) < 0) marchiImitati.push(i.marchio); });
  if (marchiImitati.length) {
    metti("nome_imita_marchio", "Il nome richiama il marchio " + marchiImitati.join(", ") +
      (nv && nv.decorato ? " (nome scritto con lettere decorative: \"" + nv.normalizzato + "\")" : ""), FONTE_NOME, true);
  }
  var esca = n.parole_esca.slice();
  if (nv) nv.parole_esca.forEach(function (p) { if (esca.indexOf(p) < 0) esca.push(p); });
  if (esca.length) metti("nome_parole_esca", "Il nome contiene parole esca: " + esca.join(", "), FONTE_NOME, true);

  // 3. testi (screenshot letti / testo incollato)
  var testi = (input.testi || []).filter(function (t) { return t && String(t.testo || "").trim(); });
  testi.forEach(function (t) {
    _usa("analizzaTesto")(t.testo, risorse.regole).forEach(function (r) {
      metti(r.codice, "\"" + r.frase + "\"", FONTE_ORIGINE[t.origine] || FONTE_ORIGINE.incollato, true);
    });
  });

  // 4. link della Mini App
  var avvisi = [];
  var link = input.linkMiniApp ? _usa("analizzaLink")(input.linkMiniApp, risorse.marchi) : null;
  if (link) {
    avvisi = link.avvisi.slice();
    link.segnali.forEach(function (s) { metti(s.codice, s.frase, FONTE_LINK, true); });
  }

  // 5. link facoltativi
  var segnalazioni = _linkValidi(input.linkSegnalazioni);
  segnalazioni.forEach(function (l) {
    extra.push({ codice: "segnalazione_truffa", tipo_prova: "segnalazione", fonte: l.url,
      testo: "Segnalazione trovata dall'utente su " + l.base });
  });
  var positivi = _linkValidi(input.linkPositivi);
  if (positivi.length) {
    metti("recensioni_positive_indipendenti", "Fonti positive indicate dall'utente: " +
      positivi.map(function (l) { return l.base; }).join(", "), positivi[0].url, false);
  }

  // copertura
  if (input.sezioniViste === false) nonVerificato.push("Sezioni prelievo / pagamenti / inviti non aperte");
  var nonCoperti = (risorse.questionario.non_coperti || []).filter(function (c) { return cat[c]; })
    .map(function (c) { return cat[c].descrizione.charAt(0).toLowerCase() + cat[c].descrizione.slice(1); });
  if (nonCoperti.length) nonVerificato.push("Non verificabile da questo strumento (serve l'analisi completa): " + nonCoperti.join("; "));
  nonVerificato.push("Codice lato server e funzionamento interno della Mini App");

  var aree = {};
  _usa("ORDINE_AREE").forEach(function (a) { aree[a] = { rischio: 0, segnali: [] }; });
  ordine.forEach(function (c) { aree[cat[c].area].segnali.push(segnali[c]); });
  extra.forEach(function (s) { aree[cat[s.codice].area].segnali.push(s); });

  var domini = {};
  segnalazioni.concat(positivi).forEach(function (l) { domini[l.base] = true; });
  var nFontiLink = Object.keys(domini).length;
  function lettere(s) { return (String(s).match(/\p{L}/gu) || []).length; }
  var testiSostanziosi = testi.filter(function (t) { return lettere(t.testo) >= MIN_LETTERE_MATERIALE; });
  // conta l'area del segnale nel catalogo, non la pagina del questionario
  var nonsoRichieste = domande.some(function (d) { return cat[d.codice].area === "richieste" && risposte[d.codice] === "nonso"; });
  // materiale sufficiente = testo vero letto dallo strumento + sezioni prelievo/pagamenti viste + nessun "Non so" sulle richieste
  var materiale = testiSostanziosi.length > 0 && input.sezioniViste === true && !nonsoRichieste;
  var limiti = [];
  if (testi.length && !testiSostanziosi.length) limiti.push("testo rilevato troppo breve per essere considerato materiale");
  if (testiSostanziosi.length && input.sezioniViste !== true) limiti.push("sezioni prelievo/pagamenti non confermate");
  if (testiSostanziosi.length && nonsoRichieste) limiti.push("\"Non so\" su domande delle richieste");

  var grezzo = {
    versione_schema: 1,
    data: new Date().toISOString().slice(0, 19),
    bot: { username: username, tipo: "", link: input.linkMiniApp ? [String(input.linkMiniApp).trim()] : [] },
    aree: aree,
    // 18/11/2026: lo screenshot non è bloccante. Risposte complete (nessun "Non so", sezioni prelievo aperte)
    // → il motore ammette il verde con riserva anche senza materiale: +20 punti, certezza bassa
    contesto: { materiale_utente: materiale, tecnica_completa: false,
      fonti_indipendenti: (materiale ? 1 : 0) + nFontiLink,
      risposte_complete: input.sezioniViste === true && !domande.some(function (d) { return risposte[d.codice] === "nonso"; }) },
    cosa_fare: [], cosa_non_fare: NON_FARE_SEMPRE.slice(), non_verificato: nonVerificato,
    fonti: segnalazioni.concat(positivi).map(function (l) { return { titolo: l.base, url: l.url }; }),
    origine: "autovalutazione guidata"
  };
  var v = _usa("calcola")(grezzo, cat);
  var note = String(input.note || "").trim().slice(0, MAX_NOTE);
  if (note) v.note_utente = note; // solo nel report: le parole libere non pesano sul punteggio
  v.cosa_fare = FARE[v.verdetto].slice();

  var nScreen = testi.filter(function (t) { return t.origine === "screenshot"; }).length;
  var nIncollati = testi.length - nScreen;
  var basataSu = [];
  if (nScreen) basataSu.push(nScreen + (nScreen === 1 ? " screenshot letto" : " screenshot letti"));
  if (nIncollati) basataSu.push(nIncollati === 1 ? "testo incollato analizzato" : nIncollati + " testi incollati analizzati");
  if (!testi.length) basataSu.push("nessun materiale analizzato: solo le risposte fornite");
  limiti.forEach(function (l) { basataSu.push(l); });
  basataSu.push("controllo del nome");
  if (link && link.valido) basataSu.push("controllo del link della Mini App");
  basataSu.push(nFontiLink === 1 ? "1 fonte esterna" : nFontiLink + " fonti esterne");
  if (input.sezioniViste === false) basataSu.push("sezioni prelievo/pagamenti non viste");

  // perché la certezza è bassa: un codice per ogni requisito del materiale che manca
  var motiviCertezzaBassa = [];
  if (v.fiducia === "bassa") {
    if (!testi.length) motiviCertezzaBassa.push("nessun_materiale");
    else if (!testiSostanziosi.length) motiviCertezzaBassa.push("testo_breve");
    if (input.sezioniViste !== true) motiviCertezzaBassa.push("sezioni_non_confermate");
    if (nonsoRichieste) motiviCertezzaBassa.push("nonso_richieste");
  }

  return { verdetto: v, contrasti: contrasti, basataSu: basataSu, avvisi: avvisi,
    motiviCertezzaBassa: motiviCertezzaBassa };
}

/* Riepilogo per la schermata di conferma: quante domande visibili hanno una risposta, e quanti "Non so". */
function contaRisposte(questionario, risposte) {
  var c = { risposte: 0, nonso: 0 };
  domandeVisibili(questionario, risposte || {}).forEach(function (d) {
    var v = (risposte || {})[d.codice];
    if (v) c.risposte++;
    if (v === "nonso") c.nonso++;
  });
  return c;
}

if (typeof module !== "undefined") {
  module.exports = { costruisciVerdetto: costruisciVerdetto, risorseDaPayload: risorseDaPayload,
    codiciAutomatici: codiciAutomatici, domandaVisibile: domandaVisibile, domandeVisibili: domandeVisibili,
    contaRisposte: contaRisposte };
}
