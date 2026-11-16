"use strict";
const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const path = require("path");
const KIT = path.join(__dirname, "..", "..");
const leggi = (p) => fs.readFileSync(path.join(KIT, p), "utf8");
const { costruisciVerdetto, risorseDaPayload, codiciAutomatici } = require(path.join(KIT, "app", "assembla.js"));

const CATALOGO = JSON.parse(leggi("segnali.json"));
const QUESTIONARIO = JSON.parse(leggi("app/questionario.json"));
const RISORSE = risorseDaPayload({ catalogo: CATALOGO, questionario: QUESTIONARIO,
  regole: JSON.parse(leggi("app/analizzatore.json")), marchi: leggi("marchi.txt") });

const tuttiCodiciDomande = () => QUESTIONARIO.aree.flatMap((a) => a.domande.map((d) => d.codice));
function tutteNo() {
  const r = {};
  for (const c of tuttiCodiciDomande()) r[c] = "no";
  return r;
}
function input(extra) {
  return Object.assign({ username: "ProvaBot", nomeVisualizzato: "", risposte: tutteNo(), sezioniViste: true,
    testi: [], linkMiniApp: "", linkSegnalazioni: [], linkPositivi: [] }, extra);
}

test("solo risposte No, nessun materiale → giallo, certezza bassa", () => {
  const { verdetto } = costruisciVerdetto(input({}), RISORSE);
  assert.strictEqual(verdetto.verdetto, "giallo");
  assert.strictEqual(verdetto.fiducia, "bassa");
});

test("risposte No + testo innocuo analizzato → verde, certezza media", () => {
  const { verdetto, basataSu } = costruisciVerdetto(input({ username: "wallet",
    testi: [{ origine: "incollato", testo: TESTO_LUNGO }] }), RISORSE);
  assert.strictEqual(verdetto.verdetto, "verde");
  assert.strictEqual(verdetto.fiducia, "media");
  assert.ok(basataSu.length >= 2);
});

test("Sì a una linea rossa → rosso, certezza alta", () => {
  const r = tutteNo(); r.richiesta_seed_o_codici = "si";
  const { verdetto } = costruisciVerdetto(input({ risposte: r }), RISORSE);
  assert.strictEqual(verdetto.verdetto, "rosso");
  assert.strictEqual(verdetto.fiducia, "alta");
});

test("risposta No smentita dal testo → rosso con contrasto", () => {
  const { verdetto, contrasti } = costruisciVerdetto(input({
    testi: [{ origine: "screenshot", testo: "deposit to withdraw your earnings" }] }), RISORSE);
  assert.strictEqual(verdetto.verdetto, "rosso");
  assert.ok(contrasti.some((c) => c.codice === "prelievo_condizionato"));
  const seg = verdetto.aree.richieste.segnali.filter((s) => s.codice === "prelievo_condizionato");
  assert.strictEqual(seg.length, 1);
  assert.strictEqual(seg[0].fonte, "lettura automatica dello screenshot");
});

test("Sì + stesso codice trovato dal controllo → un solo segnale, nessun contrasto", () => {
  const r = tutteNo(); r.prelievo_condizionato = "si";
  const { verdetto, contrasti } = costruisciVerdetto(input({ risposte: r,
    testi: [{ origine: "incollato", testo: "deposit to withdraw" }] }), RISORSE);
  assert.strictEqual(verdetto.aree.richieste.segnali.filter((s) => s.codice === "prelievo_condizionato").length, 1);
  assert.deepStrictEqual(contrasti, []);
});

test("due segnalazioni da domini diversi → rosso da segnalazioni", () => {
  const { verdetto } = costruisciVerdetto(input({
    linkSegnalazioni: ["https://x.com/a", "https://y.org/b", "https://www.x.com/c"] }), RISORSE);
  assert.strictEqual(verdetto.rosso_da_segnalazioni, true);
  assert.strictEqual(verdetto.aree.reputazione.segnali.filter((s) => s.codice === "segnalazione_truffa").length, 2);
});

test("link positivi: al massimo un segnale di recensioni positive", () => {
  const { verdetto } = costruisciVerdetto(input({ linkPositivi: ["https://a.com/1", "https://b.com/2"] }), RISORSE);
  assert.strictEqual(verdetto.aree.reputazione.segnali.filter((s) => s.codice === "recensioni_positive_indipendenti").length, 1);
  assert.strictEqual(verdetto.contesto.fonti_indipendenti, 2);
});

test("link non validi ignorati", () => {
  const { verdetto } = costruisciVerdetto(input({ linkSegnalazioni: ["javascript:alert(1)", "ciao"] }), RISORSE);
  assert.strictEqual(verdetto.aree.reputazione.segnali.length, 0);
  assert.strictEqual(verdetto.contesto.fonti_indipendenti, 0);
});

test("username normalizzato; vuoto → errore", () => {
  assert.strictEqual(costruisciVerdetto(input({ username: "https://t.me/X?start=1" }), RISORSE).verdetto.bot.username, "X");
  assert.throws(() => costruisciVerdetto(input({ username: "  " }), RISORSE), /username mancante/);
});

test("nome che imita un marchio → segnale dal controllo del nome", () => {
  const { verdetto } = costruisciVerdetto(input({ username: "MetamasksAppWebBot" }), RISORSE);
  const codici = verdetto.aree.identita.segnali.map((s) => s.codice);
  assert.ok(codici.includes("nome_imita_marchio"));
  assert.ok(codici.includes("nome_parole_esca"));
});

test("Non so e sezioni non viste → in non verificato", () => {
  const r = tutteNo(); r.richiesta_deposito = "nonso";
  const { verdetto } = costruisciVerdetto(input({ risposte: r, sezioniViste: false }), RISORSE);
  assert.ok(verdetto.non_verificato.some((t) => /prelievo/.test(t)));
  const fuori = verdetto.non_verificato.filter((t) => t.startsWith("Non verificabile da questo strumento"));
  assert.strictEqual(fuori.length, 1, "i controlli non coperti vanno in una sola riga");
  assert.ok(/offuscato/.test(fuori[0]) && /Defender/.test(fuori[0]));
});

test("copertura del catalogo: ogni codice ha una provenienza, nessun codice inventato", () => {
  const cat = new Set(CATALOGO.map((c) => c.codice));
  const domande = tuttiCodiciDomande();
  for (const c of domande) assert.ok(cat.has(c), c);
  assert.strictEqual(new Set(domande).size, domande.length, "domande duplicate");
  const coperti = new Set([...domande, ...QUESTIONARIO.non_coperti, ...codiciAutomatici()]);
  for (const c of cat) assert.ok(coperti.has(c), "senza provenienza: " + c);
});

test("il verdetto ha lo schema v1 e materiale analizzato imposta il contesto", () => {
  const { verdetto } = costruisciVerdetto(input({ testi: [{ origine: "incollato", testo: TESTO_LUNGO }] }), RISORSE);
  assert.strictEqual(verdetto.versione_schema, 1);
  assert.deepStrictEqual(verdetto.contesto, { materiale_utente: true, tecnica_completa: false, fonti_indipendenti: 1 });
  for (const k of ["cosa_fare", "cosa_non_fare", "non_verificato", "fonti"]) assert.ok(Array.isArray(verdetto[k]), k);
});

// --- revisione finale: falso verde ---
test("revisione: risposte mancanti → errore che chiede di rispondere", () => {
  assert.throws(() => costruisciVerdetto(input({ risposte: {}, testi: [{ origine: "incollato", testo: "a" }] }), RISORSE), /risposte mancanti/);
});

const TESTO_LUNGO = "Benvenuto nel bot del meteo: scegli la tua città e ricevi le previsioni ogni mattina.";

test("revisione: testo troppo corto non conta come materiale → niente verde", () => {
  const { verdetto } = costruisciVerdetto(input({ testi: [{ origine: "incollato", testo: "hello" }] }), RISORSE);
  assert.notStrictEqual(verdetto.verdetto, "verde");
  assert.strictEqual(verdetto.contesto.materiale_utente, false);
});

test("revisione: tutte Non so + testo lungo → niente verde", () => {
  const r = {}; for (const c of tuttiCodiciDomande()) r[c] = "nonso";
  const { verdetto } = costruisciVerdetto(input({ risposte: r, testi: [{ origine: "incollato", testo: TESTO_LUNGO }] }), RISORSE);
  assert.notStrictEqual(verdetto.verdetto, "verde");
});

test("revisione: sezioni prelievo non viste → niente verde", () => {
  const { verdetto } = costruisciVerdetto(input({ sezioniViste: false, testi: [{ origine: "incollato", testo: TESTO_LUNGO }] }), RISORSE);
  assert.notStrictEqual(verdetto.verdetto, "verde");
});

test("revisione: tutte No + testo lungo + sezioni viste → verde certezza media", () => {
  const { verdetto } = costruisciVerdetto(input({ testi: [{ origine: "incollato", testo: TESTO_LUNGO }] }), RISORSE);
  assert.strictEqual(verdetto.verdetto, "verde");
  assert.strictEqual(verdetto.fiducia, "media");
});

test("revisione: spunta dichiarata non annulla due segnalazioni", () => {
  const r = tutteNo(); r.bot_ufficiale_verificato = "si";
  const { verdetto } = costruisciVerdetto(input({ risposte: r, linkSegnalazioni: ["https://x.com/a", "https://y.org/b"] }), RISORSE);
  assert.strictEqual(verdetto.verdetto, "rosso");
});

test("revisione: spunta dichiarata + link positivi, senza materiale → niente verde", () => {
  const r = tutteNo(); r.bot_ufficiale_verificato = "si";
  const { verdetto } = costruisciVerdetto(input({ risposte: r, linkPositivi: ["https://a.com/1", "https://b.com/2"] }), RISORSE);
  assert.notStrictEqual(verdetto.verdetto, "verde");
});
