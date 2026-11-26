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


/* --- Tester UX 26/11/2026: il perché del colore in una frase semplice --- */
const CAT_P = {
  richiesta_seed_o_codici: { descrizione: "Chiede seed phrase, chiavi o codici", punti: 100 },
  referral_piramidale: { descrizione: "Guadagni legati al portare altre persone", punti: 40 },
  promessa_guadagno: { descrizione: "Promette guadagni", punti: 40 },
  nessun_termini_privacy: { descrizione: "Nessun termine di servizio né privacy", punti: 20 },
  richiesta_dati_personali: { descrizione: "Chiede dati personali o documenti", punti: 25 },
};
const aree = (segnali) => ({ identita: { rischio: 0, segnali: [] }, promesse: { rischio: 0, segnali: segnali || [] } });

test("perche: linea rossa → la nomina", () => {
  const v = verdetto(100, 60, { verdetto: "rosso", linee_rosse: [{ codice: "richiesta_seed_o_codici", prova: "x" }], aree: aree() });
  assert.match(A.perche(v, CAT_P, []), /^Rosso perché: chiede seed phrase, chiavi o codici\.$/);
});

test("perche: rosso da segnali → i due più pesanti, in parole semplici", () => {
  const v = verdetto(67, 67, { verdetto: "rosso", aree: aree([{ codice: "nessun_termini_privacy" }, { codice: "referral_piramidale" }, { codice: "promessa_guadagno" }]) });
  const f = A.perche(v, CAT_P, []);
  assert.match(f, /^Rosso perché: /);
  assert.ok(f.includes("guadagni legati al portare altre persone") && f.includes("promette guadagni"));
  assert.ok(!f.includes("termine"), "solo i due segnali più pesanti");
});

test("perche: giallo di sola prudenza → nessun segnale di truffa, mancano verifiche", () => {
  const v = verdetto(31, 17, { verdetto: "giallo", aree: aree() });
  const f = A.perche(v, CAT_P, ["sezioni_non_confermate"]);
  assert.match(f, /^Nessun segnale di truffa trovato\. È giallo solo perché mancano alcune verifiche: /);
  assert.ok(f.includes("pulsanti per prelevare"));
});

test("perche: giallo di prudenza con un segnale minore → prima le verifiche mancanti, poi il segnale", () => {
  // rigioco di Renato 26/11: punteggio 17 (da verde), giallo solo perché non ha guardato i pulsanti
  const v = verdetto(31, 17, { verdetto: "giallo", aree: aree([{ codice: "richiesta_dati_personali" }]) });
  assert.strictEqual(A.perche(v, CAT_P, ["sezioni_non_confermate"]),
    "Nessun segnale grave. È giallo perché mancano alcune verifiche: non hai guardato i pulsanti per prelevare, " +
    "pagare o invitare amici. Da tenere d'occhio: chiede dati personali o documenti.");
});

test("perche: giallo con segnali → li nomina", () => {
  const v = verdetto(40, 40, { verdetto: "giallo", aree: aree([{ codice: "richiesta_dati_personali" }]) });
  assert.strictEqual(A.perche(v, CAT_P, []), "Giallo per: chiede dati personali o documenti.");
});

test("perche: verde e verde con riserva", () => {
  assert.match(A.perche(verdetto(17, 17, { verdetto: "verde", aree: aree() }), CAT_P, []), /^Nessun segnale di rischio rilevante/);
  assert.match(A.perche(verdetto(20, 0, { verdetto: "verde", verde_con_riserva: true, aree: aree() }), CAT_P, []), /manca però materiale/);
});

test("perche: segnali fuori catalogo o senza punti non rompono la frase", () => {
  const v = verdetto(40, 40, { verdetto: "giallo", aree: aree([{ codice: "sconosciuto" }]) });
  assert.strictEqual(A.perche(v, CAT_P, []), "Giallo per: alcuni segnali di rischio (dettaglio nel riquadro «Rischio per area»).");
});

test("pocheInformazioni: da 5 Non so in su", () => {
  assert.strictEqual(A.pocheInformazioni(4), false);
  assert.strictEqual(A.pocheInformazioni(5), true);
});
