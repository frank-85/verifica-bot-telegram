/* Motore di punteggio: porting 1:1 di punteggio.py (stesse regole, stessi risultati).
   Funziona nel browser (funzioni globali) e in Node (module.exports). */
"use strict";

var DIVISORE = 3;
var PESI = { identita: 2, promesse: 2, richieste: 2, tecnica: 2, reputazione: 1, trasparenza: 1 };
var ORDINE_AREE = ["identita", "promesse", "richieste", "tecnica", "reputazione", "trasparenza"];
var SOGLIE = { verde: 30, giallo: 60, areaPiena: 80, minFontiUfficiale: 2, fuoriCatalogo: [-50, 100], malusSenzaProve: 20 };
var IMITAZIONE = { marchio: "nome_imita_marchio", rinforzi: ["nome_parole_esca", "dominio_con_marchio"] };

class ErroreVerdetto extends Error {
  constructor(msg) { super(msg); this.name = "ErroreVerdetto"; }
}

/* round() di Python: metà al pari (banker's rounding). */
function arrotondaPython(x) {
  var base = Math.floor(x);
  var diff = x - base;
  if (diff === 0.5) return base % 2 === 0 ? base : base + 1;
  return Math.round(x);
}

function catalogoDaLista(lista) {
  var c = {};
  lista.forEach(function (v) { c[v.codice] = v; });
  return c;
}

function _isObj(x) { return x !== null && typeof x === "object" && !Array.isArray(x); }
function _isInt(x) { return typeof x === "number" && Number.isInteger(x); }
function _isNum(x) { return typeof x === "number" && isFinite(x); }

function _hostname(fonte) {
  var s = String(fonte);
  var m = /^[a-z][a-z0-9+.-]*:\/\/([^\/?#]*)/i.exec(s);
  var host;
  if (m) {
    host = m[1].replace(/^[^@]*@/, "").replace(/:\d*$/, "");
  } else {
    // senza schema ("reddit.com/r/x"): solo il nome, come in punteggio._dominio
    host = s.split(/[\/?#]/)[0].replace(/:\d*$/, "");
  }
  host = host.toLowerCase();
  return host.indexOf("www.") === 0 ? host.slice(4) : host;
}

/* Regola unica in sicurezza.js (caricato prima di motore.js nell'app, vedi costruisci_app.ORDINE_JS). */
var _sicurezzaMotore = typeof module !== "undefined" ? require("./sicurezza.js") : null;
function _dominioBase(fonte) {
  return (_sicurezzaMotore ? _sicurezzaMotore.dominioBase : dominioBase)(_hostname(fonte));
}

function _punti(seg, catalogo, area) {
  var codice = seg.codice || "";
  if (seg.fuori_catalogo) {
    if (Object.prototype.hasOwnProperty.call(catalogo, codice))
      throw new ErroreVerdetto("'" + codice + "' è nel catalogo: non marcarlo fuori_catalogo");
    var p = seg.punti;
    if (typeof p === "boolean" || !_isNum(p))
      throw new ErroreVerdetto("il segnale fuori catalogo '" + codice + "' non ha 'punti' numerici");
    return Math.max(SOGLIE.fuoriCatalogo[0], Math.min(SOGLIE.fuoriCatalogo[1], p));
  }
  if (!Object.prototype.hasOwnProperty.call(catalogo, codice))
    throw new ErroreVerdetto("codice '" + codice + "' non presente nel catalogo");
  if (catalogo[codice].area !== area)
    throw new ErroreVerdetto("'" + codice + "' va nell'area '" + catalogo[codice].area + "', non in '" + area + "'");
  return catalogo[codice].punti;
}

function valida(verdetto) {
  if (!_isObj(verdetto)) throw new ErroreVerdetto("il verdetto deve essere un oggetto");
  if (verdetto.bot !== undefined && !_isObj(verdetto.bot))
    throw new ErroreVerdetto("'bot' deve essere un oggetto con 'username'");
  var aree = verdetto.aree;
  if (!_isObj(aree)) throw new ErroreVerdetto("manca il campo 'aree' (oggetto con le sei aree)");
  var sconosciute = Object.keys(aree).filter(function (a) { return !(a in PESI); });
  if (sconosciute.length) throw new ErroreVerdetto("area sconosciuta " + sconosciute.join(", "));
  Object.keys(aree).forEach(function (nome) {
    var area = aree[nome];
    var segnali = _isObj(area) ? (area.segnali === undefined ? [] : area.segnali) : null;
    if (!Array.isArray(segnali)) throw new ErroreVerdetto("l'area '" + nome + "' deve avere 'segnali' come elenco");
    segnali.forEach(function (seg) {
      if (!_isObj(seg) || typeof seg.codice !== "string")
        throw new ErroreVerdetto("in '" + nome + "' c'è un segnale non valido");
      if (seg.tipo_prova !== "diretta" && seg.tipo_prova !== "segnalazione")
        throw new ErroreVerdetto("'" + seg.codice + "': tipo_prova deve essere 'diretta' o 'segnalazione'");
    });
  });
  var ctx = verdetto.contesto === undefined ? {} : verdetto.contesto;
  if (!_isObj(ctx)) throw new ErroreVerdetto("'contesto' deve essere un oggetto");
  ["materiale_utente", "tecnica_completa", "risposte_complete"].forEach(function (k) {
    var val = ctx[k] === undefined ? false : ctx[k];
    if (typeof val !== "boolean") throw new ErroreVerdetto("contesto." + k + " deve essere true o false");
  });
  var fonti = ctx.fonti_indipendenti === undefined ? 0 : ctx.fonti_indipendenti;
  if (typeof fonti === "boolean" || !_isInt(fonti) || fonti < 0)
    throw new ErroreVerdetto("contesto.fonti_indipendenti deve essere un numero intero");
  ["cosa_fare", "cosa_non_fare", "non_verificato", "fonti"].forEach(function (k) {
    if (verdetto[k] !== undefined && !Array.isArray(verdetto[k]))
      throw new ErroreVerdetto("'" + k + "' deve essere un elenco");
  });
}

function calcola(verdetto, catalogo) {
  valida(verdetto);
  var r = JSON.parse(JSON.stringify(verdetto));
  var aree = r.aree;
  var lineeRosse = [];
  var diretti = {}; // codici di catalogo provati direttamente
  var fontiSegnalazioni = {};
  var ufficiale = false;
  var somma = 0;
  ORDINE_AREE.forEach(function (area) {
    var peso = PESI[area];
    if (!aree[area]) aree[area] = { rischio: 0, segnali: [] };
    var dati = aree[area];
    var totaleArea = 0;
    (dati.segnali || []).forEach(function (seg) {
      totaleArea += _punti(seg, catalogo, area);
      var voce = catalogo[seg.codice];
      var diretta = seg.tipo_prova === "diretta";
      if (voce && diretta && !seg.fuori_catalogo) diretti[seg.codice] = true;
      if (voce && voce.linea_rossa && !seg.fuori_catalogo && diretta)
        lineeRosse.push({ codice: seg.codice, tipo_prova: "diretta", prova: seg.testo || "" });
      if (seg.codice === "bot_ufficiale_verificato" && diretta) ufficiale = true;
      if (seg.codice === "segnalazione_truffa" && !diretta && String(seg.fonte || "").trim())
        fontiSegnalazioni[_dominioBase(String(seg.fonte))] = true;
    });
    var rischio = arrotondaPython(Math.max(0, Math.min(100, totaleArea)));
    dati.rischio = rischio;
    somma += rischio * peso;
  });
  // taratura 18/11/2026: somma pesata ÷ 3 con tetto 100 (non più media: le aree vuote diluivano il rischio)
  var totale = arrotondaPython(Math.min(100, somma / DIVISORE));

  var ctx = r.contesto || {};
  var materiale = ctx.materiale_utente || false;
  var tecnica = ctx.tecnica_completa || false;
  var fonti = ctx.fonti_indipendenti || 0;
  var fiducia;
  if (lineeRosse.length || (fonti >= 2 && tecnica && materiale)) fiducia = "alta";
  else if (ufficiale && fonti >= SOGLIE.minFontiUfficiale) fiducia = "media";
  else if (fonti === 0 || (!materiale && !tecnica)) fiducia = "bassa";
  else fiducia = "media";

  var daSegnalazioni = Object.keys(fontiSegnalazioni).length >= 2 && !ufficiale;
  // taratura 17/11/2026 (punto A): marchio imitato + parola esca o dominio col marchio → rosso (non linea rossa)
  var daImitazione = !!diretti[IMITAZIONE.marchio] &&
    IMITAZIONE.rinforzi.some(function (c) { return diretti[c]; }) && !ufficiale;
  var esito;
  if (lineeRosse.length || daSegnalazioni || daImitazione) esito = "rosso";
  else if (totale <= SOGLIE.verde) esito = "verde";
  else if (totale <= SOGLIE.giallo) esito = "giallo";
  else esito = "rosso";
  // taratura 18/11/2026 (porting di punteggio.py): verde con riserva se le risposte sono complete
  var areaPiena = ORDINE_AREE.some(function (a) { return aree[a].rischio >= SOGLIE.areaPiena; });
  var riserva = false;
  if (esito === "verde" && fiducia === "bassa") {
    riserva = ctx.risposte_complete === true && !areaPiena &&
      Math.min(100, totale + SOGLIE.malusSenzaProve) <= SOGLIE.verde;
    if (!riserva) esito = "giallo";
  }
  if (esito === "verde" && areaPiena) esito = "giallo";

  // rischio finale (porting di punteggio.py): sempre nella zona del colore; linea rossa = 100.
  var finale;
  if (lineeRosse.length) finale = 100;
  else if (daSegnalazioni || daImitazione) finale = Math.max(totale, SOGLIE.giallo + 1);
  else if (esito === "giallo") finale = Math.max(totale, SOGLIE.verde + 1);
  else if (riserva) finale = Math.min(100, totale + SOGLIE.malusSenzaProve);
  else finale = totale;

  r.pesi = Object.assign({}, PESI);
  r.punteggio_totale = totale;
  r.rischio_finale = finale;
  r.linee_rosse = lineeRosse;
  r.fiducia = fiducia;
  r.verdetto = esito;
  r.rosso_da_segnalazioni = daSegnalazioni;
  r.rosso_da_imitazione = daImitazione;
  r.verde_con_riserva = riserva;
  return r;
}

if (typeof module !== "undefined") {
  module.exports = { PESI: PESI, DIVISORE: DIVISORE, ORDINE_AREE: ORDINE_AREE, SOGLIE: SOGLIE, ErroreVerdetto: ErroreVerdetto,
    arrotondaPython: arrotondaPython, catalogoDaLista: catalogoDaLista, valida: valida, calcola: calcola,
    dominioBaseFonte: _dominioBase };
}
