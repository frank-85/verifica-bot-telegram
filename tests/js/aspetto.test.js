"use strict";
const test = require("node:test");
const assert = require("node:assert");
const path = require("path");
const A = require(path.join(__dirname, "..", "..", "app", "aspetto.js"));

const verdetto = (finale, media, extra) => Object.assign({ rischio_finale: finale, punteggio_totale: media,
  linee_rosse: [], rosso_da_segnalazioni: false }, extra || {});

test("rischioFinale: usa il campo, ricade sulla media se manca o non è un numero", () => {
  assert.strictEqual(A.rischioFinale(verdetto(100, 44)), 100);
  assert.strictEqual(A.rischioFinale({ punteggio_totale: 29 }), 29);
  assert.strictEqual(A.rischioFinale({ rischio_finale: null, punteggio_totale: 12 }), 12);
  assert.strictEqual(A.rischioFinale({ rischio_finale: "100", punteggio_totale: 12 }), 12);
});

test("zonaRischio: soglie 30/60 coerenti con il motore", () => {
  const atteso = { 0: "verde", 30: "verde", 31: "giallo", 60: "giallo", 61: "rosso", 100: "rosso" };
  for (const [n, zona] of Object.entries(atteso)) assert.strictEqual(A.zonaRischio(Number(n)), zona, n);
});

test("posizioneIndicatore: dentro la barra anche con valori fuori scala", () => {
  assert.strictEqual(A.posizioneIndicatore(-5), 0);
  assert.strictEqual(A.posizioneIndicatore(140), 100);
  assert.strictEqual(A.posizioneIndicatore(54), 54);
  assert.strictEqual(A.posizioneIndicatore(NaN), 0);
});

test("notaProssimita: ultimi 5 punti prima della soglia successiva", () => {
  assert.strictEqual(A.notaProssimita(verdetto(25, 25)), null);
  assert.strictEqual(A.notaProssimita(verdetto(26, 26)), "vicino alla soglia di attenzione");
  assert.strictEqual(A.notaProssimita(verdetto(30, 30)), "vicino alla soglia di attenzione");
  assert.strictEqual(A.notaProssimita(verdetto(55, 55)), null);
  assert.strictEqual(A.notaProssimita(verdetto(56, 56)), "vicino alla soglia del rosso");
  assert.strictEqual(A.notaProssimita(verdetto(60, 60)), "vicino alla soglia del rosso");
  assert.strictEqual(A.notaProssimita(verdetto(61, 61)), null);
});

test("notaProssimita: mai quando prevale una regola", () => {
  assert.strictEqual(A.notaProssimita(verdetto(100, 44, { linee_rosse: [{ codice: "x" }] })), null);
  assert.strictEqual(A.notaProssimita(verdetto(31, 28)), null); // giallo per regola di prudenza, media 28
});

test("motivoRegola: perché il rischio finale è diverso dalla media", () => {
  assert.strictEqual(A.motivoRegola(verdetto(100, 44, { linee_rosse: [{ codice: "x" }] })), "linea_rossa");
  assert.strictEqual(A.motivoRegola(verdetto(61, 12, { rosso_da_segnalazioni: true })), "segnalazioni");
  assert.strictEqual(A.motivoRegola(verdetto(61, 27, { rosso_da_imitazione: true })), "imitazione");
  assert.strictEqual(A.motivoRegola(verdetto(31, 5)), "prudenza");
  assert.strictEqual(A.motivoRegola(verdetto(20, 0, { verde_con_riserva: true })), "riserva");
  assert.strictEqual(A.motivoRegola(verdetto(44, 44)), null);
  assert.strictEqual(A.motivoRegola({ punteggio_totale: 29, linee_rosse: [{ codice: "x" }] }), null); // verdetto vecchio
});

test("temaEffettivo: automatico segue il sistema, la scelta manuale prevale", () => {
  assert.strictEqual(A.temaEffettivo("auto", false), "chiaro");
  assert.strictEqual(A.temaEffettivo("auto", true), "scuro");
  assert.strictEqual(A.temaEffettivo("chiaro", true), "chiaro");
  assert.strictEqual(A.temaEffettivo("chiaro", false), "chiaro");
  assert.strictEqual(A.temaEffettivo("scuro", false), "scuro");
  assert.strictEqual(A.temaEffettivo("scuro", true), "scuro");
  assert.strictEqual(A.temaEffettivo("boh", true), "scuro");
  assert.strictEqual(A.temaEffettivo(undefined, false), "chiaro");
});
