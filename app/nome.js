/* Analisi dello username: porting 1:1 di nome.py (imitazione di marchi, parole esca),
   più analizzaNomeVisualizzato (solo JS) per i nomi scritti con lettere decorative. */
"use strict";

var PAROLE_ESCA = ["official", "support", "app", "web", "airdrop", "claim", "bonus", "gift", "free",
  "verify", "safeguard", "help", "admin", "reward", "profit", "invest"];
var OMOGLIFI = [["rn", "m"], ["vv", "w"], ["0", "o"], ["3", "e"], ["4", "a"], ["5", "s"], ["7", "t"]];
var MIN_LUNGO = 5;
var MIN_SOTTOSTRINGA = 4;

function _sostituisciTutto(t, a, b) { return t.split(a).join(b); }

var TME = /^(?:https?:\/\/)?(?:www\.)?(?:t\.me|telegram\.me|telegram\.dog)\//i;

/* Link d'invito a un gruppo o canale (t.me/+…, t.me/joinchat/…, tg://join): non indica un bot. */
function eLinkInvito(testo) {
  var t = String(testo).trim();
  return /^(?:https?:\/\/)?(?:www\.)?(?:t\.me|telegram\.me|telegram\.dog)\/(?:\+|joinchat\/)/i.test(t) ||
    /^tg:\/\/join\b/i.test(t);
}

/* Username da @nome o da qualsiasi link Telegram (porting di nome.py). "" se il link non indica un bot. */
function normalizzaUsername(testo) {
  var t = String(testo).trim();
  if (/^tg:\/\//i.test(t)) {
    var m = /^tg:\/\/resolve\?(?:.*&)?domain=([^&#\s]*)/i.exec(t);
    return m ? m[1].replace(/^@+/, "").trim() : "";
  }
  var web = /^(?:https?:\/\/)?(?:www\.)?web\.telegram\.org(?:\/[a-z])?\/?(#.*)?$/i.exec(t);
  if (web) {
    var nome = (web[1] || "#").slice(1).replace(/^@+/, "").split("?")[0].trim();
    return !nome || /^-*\d+$/.test(nome) ? "" : nome;
  }
  if (eLinkInvito(t)) return "";
  var link = TME.test(t);
  t = t.replace(/^https?:\/\//i, "");
  t = t.replace(/^(www\.)?(t\.me|telegram\.me|telegram\.dog)\//i, "");
  if (link && /^s(\/|$)/i.test(t)) t = t.slice(2); // t.me/s/Nome = anteprima web della stessa pagina
  t = t.split("?")[0].split("#")[0].replace(/^\/+|\/+$/g, "");
  t = t.split("/")[0];
  return t.replace(/^@+/, "").trim();
}

/* Tester UX 26/11/2026 (solo JS, per l'app): cosa non va in uno username già normalizzato, "" se va bene.
   Gli username Telegram hanno solo lettere latine, cifre e "_": spazi o simboli = copiato male. */
var MIN_USERNAME = 4;
var MAX_USERNAME = 32;
function problemaUsername(u) {
  var t = String(u || "").trim();
  if (/\s/.test(t)) {
    var senza = t.replace(/\s+/g, "");
    return "Gli username Telegram non hanno spazi" + (/^[A-Za-z0-9_]+$/.test(senza) ? ": intendevi @" + senza + "?" : ".") +
      " Copialo dal profilo del bot.";
  }
  // giro finale 26/11 (Luca): le lettere non latine (es. cirilliche) si nominano, perché sono un trucco d'imitazione
  if (/[^\x00-\x7F]/.test(t) && /\p{L}/u.test(t.replace(/[A-Za-z]/g, "")))
    return "Lo username contiene lettere non latine (per esempio cirilliche o greche, che sembrano uguali alle nostre): gli username Telegram usano solo lettere latine. Copialo dal profilo del bot: se il nome che vedi le contiene, è un segnale d'imitazione.";
  if (!/^[A-Za-z0-9_]+$/.test(t)) return "Lo username può contenere solo lettere, numeri e trattino basso (_). Copialo dal profilo del bot.";
  if (t.length < MIN_USERNAME) return "Lo username sembra troppo corto: controlla di averlo copiato per intero dal profilo del bot.";
  if (t.length > MAX_USERNAME) return "Lo username è troppo lungo (al massimo " + MAX_USERNAME + " caratteri): copia solo il nome dopo la @.";
  return "";
}

function caricaMarchi(testo) {
  var marchi = [];
  String(testo).split(/\r?\n/).forEach(function (riga) {
    riga = riga.split("#")[0].trim();
    if (!riga) return;
    var campi = riga.split("|");
    var ufficiali = new Set();
    (campi.length > 1 ? campi[1] : "").split(",").forEach(function (u) { if (u.trim()) ufficiali.add(u.trim().toLowerCase()); });
    var generico = campi.length > 2 && campi[2].trim().toLowerCase() === "generico";
    // quarto campo: domini ufficiali che non coincidono col marchio (porting di nome.domini_ufficiali)
    var domini = (campi.length > 3 ? campi[3] : "").split(",")
      .map(function (d) { return d.trim().toLowerCase(); }).filter(Boolean);
    marchi.push([campi[0].trim().toLowerCase(), ufficiali, generico, domini]);
  });
  return marchi;
}

function _parole(username) {
  var pezzi = username.split(/[^\p{L}\p{N}]+/u);
  var parole = [];
  pezzi.forEach(function (p) {
    var m = p.match(/[A-Z]+(?![a-z])|[A-Z]?[a-z0-9]+/g);
    if (m) parole = parole.concat(m);
  });
  return parole.filter(Boolean).map(function (p) { return p.toLowerCase(); });
}

function _compatto(username) {
  var t = _sostituisciTutto(username.toLowerCase(), "_", "");
  return t.length > 3 && t.slice(-3) === "bot" ? t.slice(0, -3) : t;
}

function _candidati(compatto) {
  var t = compatto;
  OMOGLIFI.forEach(function (c) { t = _sostituisciTutto(t, c[0], c[1]); });
  var set = new Set([_sostituisciTutto(t, "1", "l"), _sostituisciTutto(t, "1", "i")]);
  return Array.from(set).sort();
}

function _levenshtein(a, b) {
  var prec = [];
  for (var j = 0; j <= b.length; j++) prec.push(j);
  for (var i = 1; i <= a.length; i++) {
    var cur = [i];
    for (j = 1; j <= b.length; j++)
      cur.push(Math.min(prec[j] + 1, cur[j - 1] + 1, prec[j - 1] + (a[i - 1] !== b[j - 1] ? 1 : 0)));
    prec = cur;
  }
  return prec[prec.length - 1];
}

function _contiene(marchio, candidato) {
  var pos = candidato.indexOf(marchio);
  if (pos < 0) return null;
  var prima = pos > 0 ? candidato[pos - 1] + "+" : "";
  var fine = pos + marchio.length;
  var dopo = fine < candidato.length ? "+" + candidato[fine] : "";
  return prima + marchio + dopo;
}

function _variante(marchio, candidato) {
  var n = marchio.length;
  var prove = [[n - 1, "lettera mancante"], [n + 1, "lettera aggiunta"], [n, "lettera sostituita"]];
  for (var k = 0; k < prove.length; k++) {
    var lung = prove[k][0];
    for (var i = 0; i < candidato.length - lung + 1; i++) {
      var finestra = candidato.slice(i, i + lung);
      if (finestra !== marchio && _levenshtein(finestra, marchio) === 1) return prove[k][1];
    }
  }
  return null;
}

/* Il candidato è fatto SOLO di marchio + parole esca + cifre? (porting di _composto in nome.py) */
function _composto(candidato, marchio, varianti) {
  var n = marchio.length, memo = {};
  function da(i) {
    if (i === candidato.length) return "";
    if (Object.prototype.hasOwnProperty.call(memo, i)) return memo[i];
    var esiti = [], resto;
    if (candidato.startsWith(marchio, i)) { resto = da(i + n); if (resto !== null) esiti.push("contiene"); }
    if (varianti) {
      [n - 1, n, n + 1].forEach(function (lung) {
        var finestra = candidato.slice(i, i + lung);
        if (finestra.length === lung && finestra !== marchio && _levenshtein(finestra, marchio) === 1) {
          var r = da(i + lung); if (r !== null) esiti.push(r || "variante");
        }
      });
    }
    PAROLE_ESCA.forEach(function (p) {
      if (candidato.startsWith(p, i)) { var r = da(i + p.length); if (r !== null) esiti.push(r); }
    });
    var cifre = /^\d+/.exec(candidato.slice(i));
    if (cifre) { resto = da(i + cifre[0].length); if (resto !== null) esiti.push(resto); }
    memo[i] = esiti.indexOf("contiene") >= 0 ? "contiene" : esiti.indexOf("variante") >= 0 ? "variante"
      : esiti.indexOf("") >= 0 ? "" : null;
    return memo[i];
  }
  return da(0) || null;
}

function analizzaNome(username, marchi) {
  username = normalizzaUsername(username);
  var parole = _parole(username);
  var compatto = _compatto(username);
  var candidati = _candidati(compatto);
  var imitazioni = [];
  var ufficiale = false;
  marchi.forEach(function (voce) {
    var marchio = voce[0], ufficiali = voce[1], generico = voce[2] === true;
    if (ufficiali.has(username.toLowerCase())) { ufficiale = true; return; }
    if (marchio.length < MIN_SOTTOSTRINGA && (parole.indexOf(marchio) >= 0 || compatto === marchio)) {
      imitazioni.push({ marchio: marchio, tipo: "contiene", dettaglio: marchio });
      return;
    }
    if (generico || marchio.length < MIN_SOTTOSTRINGA) {
      var varianti = generico && marchio.length >= MIN_LUNGO;
      var esiti = candidati.map(function (c) { return _composto(c, marchio, varianti); });
      var k = esiti.indexOf("contiene");
      if (k >= 0) imitazioni.push({ marchio: marchio, tipo: "contiene", dettaglio: _contiene(marchio, candidati[k]) });
      else if ((k = esiti.indexOf("variante")) >= 0)
        imitazioni.push({ marchio: marchio, tipo: "variante", dettaglio: _variante(marchio, candidati[k]) });
      return;
    }
    var trovato = null;
    for (var i = 0; i < candidati.length && !trovato; i++) {
      var det = _contiene(marchio, candidati[i]);
      if (det) trovato = { marchio: marchio, tipo: "contiene", dettaglio: det };
    }
    if (!trovato && marchio.length >= MIN_LUNGO) {
      for (i = 0; i < candidati.length && !trovato; i++) {
        var tipo = _variante(marchio, candidati[i]);
        if (tipo) trovato = { marchio: marchio, tipo: "variante", dettaglio: tipo };
      }
    }
    if (trovato) imitazioni.push(trovato);
  });
  var esca;
  if (parole.length > 1) esca = PAROLE_ESCA.filter(function (p) { return parole.indexOf(p) >= 0; });
  else esca = PAROLE_ESCA.filter(function (p) { return p.length >= 4 && compatto.indexOf(p) >= 0; });
  return { username: username, imitazioni: imitazioni, ufficiale: ufficiale, parole_esca: esca };
}

/* Nome visualizzato (es. "𝐁𝐈𝐍𝐀𝐍𝐂𝐄 𝐖𝐀𝐋𝐋𝐄𝐓"): NFKC riporta le lettere decorative a lettere normali. */
function analizzaNomeVisualizzato(nome, marchi) {
  var originale = String(nome || "");
  var normalizzato = originale.normalize("NFKC");
  var decorato = normalizzato !== originale && /[\p{L}]/u.test(originale);
  var compatto = normalizzato.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, "_").replace(/^_+|_+$/g, "");
  var analisi = compatto ? analizzaNome(compatto, marchi) : { imitazioni: [], parole_esca: [], ufficiale: false };
  return { decorato: decorato, normalizzato: normalizzato, imitazioni: analisi.imitazioni,
    parole_esca: analisi.parole_esca };
}

if (typeof module !== "undefined") {
  module.exports = { normalizzaUsername: normalizzaUsername, eLinkInvito: eLinkInvito, caricaMarchi: caricaMarchi,
    analizzaNome: analizzaNome, analizzaNomeVisualizzato: analizzaNomeVisualizzato, problemaUsername: problemaUsername };
}
