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

const tuttiCodiciDomande = () => QUESTIONARIO.pagine.flatMap((a) => a.domande.map((d) => d.codice));
const tutteDomande = () => QUESTIONARIO.pagine.flatMap((a) => a.domande);
/* Risposte che non accendono alcun segnale: "No" alle domande sul rischio, "Sì" a quelle in positivo. */
function risposteSicure() {
  const r = {};
  for (const d of tutteDomande()) r[d.codice] = d.segnale_se === "no" ? "si" : "no";
  return r;
}
function input(extra) {
  return Object.assign({ username: "ProvaBot", nomeVisualizzato: "", risposte: risposteSicure(), sezioniViste: true,
    testi: [], linkMiniApp: "", linkSegnalazioni: [], linkPositivi: [] }, extra);
}

// 18/11/2026 (Francesco): lo screenshot non è bloccante. Risposte complete e pulite → verde con riserva:
// la prova mancante aggiunge 20 punti e la certezza resta bassa.
test("solo risposte sicure, nessun materiale → verde con riserva, rischio 20, certezza bassa", () => {
  const { verdetto } = costruisciVerdetto(input({}), RISORSE);
  assert.strictEqual(verdetto.verdetto, "verde");
  assert.strictEqual(verdetto.fiducia, "bassa");
  assert.strictEqual(verdetto.verde_con_riserva, true);
  assert.strictEqual(verdetto.rischio_finale, verdetto.punteggio_totale + 20);
});

test("risposte sicure + testo innocuo analizzato → verde, certezza media", () => {
  const { verdetto, basataSu } = costruisciVerdetto(input({ username: "wallet",
    testi: [{ origine: "incollato", testo: TESTO_LUNGO }] }), RISORSE);
  assert.strictEqual(verdetto.verdetto, "verde");
  assert.strictEqual(verdetto.fiducia, "media");
  assert.ok(basataSu.length >= 2);
});

test("Sì a una linea rossa → rosso, certezza alta", () => {
  const r = risposteSicure(); r.richiesta_seed_o_codici = "si";
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
  const r = risposteSicure(); r.prelievo_condizionato = "si";
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
  const { verdetto } = costruisciVerdetto(input({ username: "MetamasksAppWebEsempioBot" }), RISORSE);
  const codici = verdetto.aree.identita.segnali.map((s) => s.codice);
  assert.ok(codici.includes("nome_imita_marchio"));
  assert.ok(codici.includes("nome_parole_esca"));
});

test("Non so e sezioni non viste → in non verificato", () => {
  const r = risposteSicure(); r.richiesta_deposito = "nonso";
  const { verdetto } = costruisciVerdetto(input({ risposte: r, sezioniViste: false }), RISORSE);
  assert.ok(verdetto.non_verificato.some((t) => /prelevare/.test(t)));
  const fuori = verdetto.non_verificato.filter((t) => t.startsWith("Controlli tecnici che richiedono l'analisi completa"));
  assert.strictEqual(fuori.length, 1, "i controlli non coperti vanno in una sola riga");
  // tester UX 26/11: niente elenco tecnico che sembra un'accusa ("Defender segnala il file come minaccia")
  assert.ok(!/Defender|offuscato/.test(fuori[0]) && /non indicano nulla di negativo/.test(fuori[0]));
});

test("copertura del catalogo: ogni codice ha una provenienza, nessun codice inventato", () => {
  const cat = new Set(CATALOGO.map((c) => c.codice));
  // codici prodotti o coperti dalle domande: codice, codice_se_si, assorbe (accorpati in un'altra domanda)
  const daDomande = tutteDomande().flatMap((d) => [d.codice].concat(d.codice_se_si ? [d.codice_se_si] : [], d.assorbe || []));
  for (const c of daDomande) assert.ok(cat.has(c), c);
  assert.strictEqual(new Set(daDomande).size, daDomande.length, "codici duplicati tra le domande");
  for (const c of QUESTIONARIO.non_coperti) assert.ok(!daDomande.includes(c), "sia domanda sia non coperto: " + c);
  const coperti = new Set([...daDomande, ...QUESTIONARIO.non_coperti, ...codiciAutomatici()]);
  for (const c of cat) assert.ok(coperti.has(c), "senza provenienza: " + c);
});

// --- domande ridotte e accorpate (17/11/2026) ---
const risp = (extra) => Object.assign(risposteSicure(), extra);
const conta = (v, codice) => Object.values(v.aree).reduce((n, a) => n + a.segnali.filter((s) => s.codice === codice).length, 0);

// 26/11/2026: 19 → 20 domande con q_rimandato (condizionale: compare solo se il bot promette guadagni)
test("questionario ridotto: 20 domande su 4 pagine, ogni id unico", () => {
  assert.strictEqual(QUESTIONARIO.pagine.length, 4);
  assert.strictEqual(tutteDomande().length, 20);
  const ids = tutteDomande().map((d) => d.id);
  assert.strictEqual(new Set(ids).size, ids.length);
});

test("domande condizionali: mostra_se punta a una domanda precedente della stessa pagina", () => {
  for (const p of QUESTIONARIO.pagine) {
    p.domande.forEach((d, i) => {
      if (!d.mostra_se) return;
      const prima = p.domande.slice(0, i).map((x) => x.codice);
      assert.ok(prima.includes(d.mostra_se.codice), d.id);
      assert.ok(d.mostra_se.risposte.length && d.mostra_se.risposte.every((r) => ["si", "no", "nonso"].includes(r)), d.id);
    });
  }
  const condizionali = tutteDomande().filter((d) => d.mostra_se).map((d) => d.id).sort();
  assert.deepStrictEqual(condizionali, ["q_consob", "q_garantito", "q_inviti", "q_rimandato"]);
});

test("senza promesse di guadagno le 3 domande condizionali non servono e non contano", () => {
  const r = risp({ promessa_guadagno: "no" });
  for (const c of ["rendimento_garantito", "referral_piramidale", "consob_oscurato"]) delete r[c];
  const v = costruisciVerdetto(input({ risposte: r }), RISORSE).verdetto; // nessun errore "risposte mancanti"
  // una risposta rimasta da prima (domanda poi nascosta) viene ignorata
  const vecchia = costruisciVerdetto(input({ risposte: risp({ promessa_guadagno: "no", rendimento_garantito: "si" }) }), RISORSE).verdetto;
  assert.strictEqual(conta(vecchia, "rendimento_garantito"), 0);
  assert.ok(!v.non_verificato.some((t) => /garantiti/.test(t)));
});

test("con promesse di guadagno (Sì o Non so) le domande condizionali sono obbligatorie e contano", () => {
  for (const g of ["si", "nonso"]) {
    const r = risp({ promessa_guadagno: g }); delete r.rendimento_garantito;
    assert.throws(() => costruisciVerdetto(input({ risposte: r }), RISORSE), /risposte mancanti/, g);
    const v = costruisciVerdetto(input({ risposte: risp({ promessa_guadagno: g, rendimento_garantito: "si" }) }), RISORSE).verdetto;
    assert.strictEqual(v.verdetto, "rosso", g);
  }
});

test("accorpate: seed in chat o nella Mini App → una sola linea rossa, nessun doppio conteggio", () => {
  const v = costruisciVerdetto(input({ risposte: risp({ richiesta_seed_o_codici: "si" }) }), RISORSE).verdetto;
  assert.strictEqual(conta(v, "richiesta_seed_o_codici"), 1);
  assert.strictEqual(conta(v, "pagina_seed_phrase"), 0);
  assert.strictEqual(v.linee_rosse.length, 1);
});

// --- semplificazione 17/11/2026: all'utente si chiede solo ciò che vede ---
test("gestore: si chiede solo se è dichiarato; Sì → nulla, No → non dichiarato, mai 'verificabile'", () => {
  const per = (x) => costruisciVerdetto(input({ risposte: risp({ gestore_non_dichiarato: x }) }), RISORSE).verdetto;
  for (const x of ["si", "no", "nonso"]) assert.strictEqual(conta(per(x), "gestore_dichiarato_verificabile"), 0, x);
  assert.deepStrictEqual(["si", "no", "nonso"].map((x) => conta(per(x), "gestore_non_dichiarato")), [0, 1, 0]);
  // la verifica della società (registro delle imprese) è un lavoro da analisi completa
  assert.ok(QUESTIONARIO.non_coperti.includes("gestore_dichiarato_verificabile"));
});

test("nessuna domanda chiede all'utente di fare verifiche da analista", () => {
  for (const d of tutteDomande()) {
    assert.ok(!/hai (potuto )?verificat|registro delle imprese|partita iva che hai/i.test(d.testo + " " + d.aiuto), d.id);
    assert.strictEqual(d.codice_se_si, undefined, d.id);
  }
});

test("solo Sì/No dove la cosa salta all'occhio: seed phrase, comando da incollare, file ricevuto", () => {
  const soloSiNo = tutteDomande().filter((d) => d.risposte).map((d) => d.codice).sort();
  assert.deepStrictEqual(soloSiNo, ["file_pericoloso_estensione", "richiesta_comando_pc", "richiesta_seed_o_codici"]);
  for (const codice of soloSiNo) {
    assert.deepStrictEqual(tutteDomande().find((d) => d.codice === codice).risposte, ["si", "no"], codice);
    assert.throws(() => costruisciVerdetto(input({ risposte: risp({ [codice]: "nonso" }) }), RISORSE), /risposte mancanti/, codice);
  }
});

test("seed phrase: solo Sì o No, perché una richiesta così si nota", () => {
  const seed = tutteDomande().find((d) => d.codice === "richiesta_seed_o_codici");
  assert.deepStrictEqual(seed.risposte, ["si", "no"]);
  assert.ok(!/Mini App/.test(seed.testo) && /Mini App/.test(seed.aiuto), "la Mini App sta nell'aiuto, non nella domanda");
  // "Non so" non è una risposta ammessa: vale come risposta mancante
  assert.throws(() => costruisciVerdetto(input({ risposte: risp({ richiesta_seed_o_codici: "nonso" }) }), RISORSE), /risposte mancanti/);
  for (const d of tutteDomande()) {
    if (d.risposte) assert.ok(d.risposte.every((x) => ["si", "no", "nonso"].includes(x)) && d.risposte.includes("si"), d.id);
  }
});

test("Non so sulle richieste: conta l'area del segnale, non la pagina", () => {
  const motiviDi = (r) => costruisciVerdetto(input({ risposte: r, testi: [{ origine: "incollato", testo: TESTO_LUNGO }] }), RISORSE).motiviCertezzaBassa;
  assert.deepStrictEqual(motiviDi(risp({ richiesta_dati_personali: "nonso" })), ["nonso_richieste"]);
  assert.deepStrictEqual(motiviDi(risp({ nessun_sito: "nonso" })), []); // sito: area trasparenza
});

test("le domande tolte finiscono tra i controlli non coperti dall'autovalutazione", () => {
  for (const c of ["nome_incoerente_servizio", "recensioni_sospette"]) assert.ok(QUESTIONARIO.non_coperti.includes(c), c);
});

test("il verdetto ha lo schema v1 e materiale analizzato imposta il contesto", () => {
  const { verdetto } = costruisciVerdetto(input({ testi: [{ origine: "incollato", testo: TESTO_LUNGO }] }), RISORSE);
  assert.strictEqual(verdetto.versione_schema, 1);
  assert.deepStrictEqual(verdetto.contesto, { materiale_utente: true, tecnica_completa: false, fonti_indipendenti: 1,
    risposte_complete: true, risposte_contraddittorie: false });
  for (const k of ["cosa_fare", "cosa_non_fare", "non_verificato", "fonti"]) assert.ok(Array.isArray(verdetto[k]), k);
});

// --- revisione finale: falso verde ---
test("revisione: risposte mancanti → errore che chiede di rispondere", () => {
  assert.throws(() => costruisciVerdetto(input({ risposte: {}, testi: [{ origine: "incollato", testo: "a" }] }), RISORSE), /risposte mancanti/);
});

const TESTO_LUNGO = "Benvenuto nel bot del meteo: scegli la tua città e ricevi le previsioni ogni mattina.";

// 18/11/2026: senza materiale vero il verde pieno resta escluso; è possibile solo il verde con riserva
test("revisione: testo troppo corto non conta come materiale → al massimo verde con riserva", () => {
  const { verdetto } = costruisciVerdetto(input({ testi: [{ origine: "incollato", testo: "hello" }] }), RISORSE);
  assert.strictEqual(verdetto.contesto.materiale_utente, false);
  assert.strictEqual(verdetto.fiducia, "bassa");
  assert.ok(verdetto.verdetto !== "verde" || verdetto.verde_con_riserva);
});

test("revisione: tutte Non so + testo lungo → niente verde", () => {
  const r = tutteNonso();
  const { verdetto } = costruisciVerdetto(input({ risposte: r, testi: [{ origine: "incollato", testo: TESTO_LUNGO }] }), RISORSE);
  assert.notStrictEqual(verdetto.verdetto, "verde");
});

test("revisione: sezioni prelievo non viste → niente verde", () => {
  const { verdetto } = costruisciVerdetto(input({ sezioniViste: false, testi: [{ origine: "incollato", testo: TESTO_LUNGO }] }), RISORSE);
  assert.notStrictEqual(verdetto.verdetto, "verde");
});

test("revisione: risposte sicure + testo lungo + sezioni viste → verde certezza media", () => {
  const { verdetto } = costruisciVerdetto(input({ testi: [{ origine: "incollato", testo: TESTO_LUNGO }] }), RISORSE);
  assert.strictEqual(verdetto.verdetto, "verde");
  assert.strictEqual(verdetto.fiducia, "media");
});

test("revisione: spunta dichiarata non annulla due segnalazioni", () => {
  const r = risposteSicure(); r.bot_ufficiale_verificato = "si";
  const { verdetto } = costruisciVerdetto(input({ risposte: r, linkSegnalazioni: ["https://x.com/a", "https://y.org/b"] }), RISORSE);
  assert.strictEqual(verdetto.verdetto, "rosso");
});

// --- domande in positivo (17/11/2026): niente negazioni, la polarità sta in segnale_se ---
const NEGAZIONI = /\b(non|nessun\w*|manca\w*|mancano|senza|né)\b|sconosciut|incoerent/i;
const IN_POSITIVO = { nessuna_storia_online: "q_storia",
  nessun_sito: "q_sito", nessun_termini_privacy: "q_termini", gestore_non_dichiarato: "q_gestore" };

test("domande in positivo: nessuna negazione nel testo delle domande", () => {
  for (const d of tutteDomande()) assert.ok(!NEGAZIONI.test(d.testo), d.id + ": " + d.testo);
  assert.ok(!NEGAZIONI.test(QUESTIONARIO.copertura.testo));
});

test("domande in positivo: segnale_se vale solo 'no' e solo sulle domande girate", () => {
  for (const d of tutteDomande()) {
    assert.ok(d.segnale_se === undefined || d.segnale_se === "no", d.id);
    assert.strictEqual(d.segnale_se === "no", d.codice in IN_POSITIVO, d.id);
  }
});

for (const [codice, id] of Object.entries(IN_POSITIVO)) {
  test("domanda in positivo " + id + ": No → " + codice + ", Sì → nessun segnale", () => {
    const area = CATALOGO.find((c) => c.codice === codice).area;
    const no = risposteSicure(); no[codice] = "no";
    const conNo = costruisciVerdetto(input({ risposte: no }), RISORSE).verdetto;
    const seg = conNo.aree[area].segnali.find((s) => s.codice === codice);
    assert.ok(seg);
    // nel report la prova descrive il rischio, non ripete la domanda in positivo
    assert.strictEqual(seg.testo, CATALOGO.find((c) => c.codice === codice).descrizione);
    const conSi = costruisciVerdetto(input({ risposte: risposteSicure() }), RISORSE).verdetto;
    assert.ok(!conSi.aree[area].segnali.some((s) => s.codice === codice));
  });
}

test("domande in positivo: Non so resta senza segnale, finisce tra i non verificati", () => {
  const r = risposteSicure(); r.nessun_sito = "nonso";
  const v = costruisciVerdetto(input({ risposte: r }), RISORSE).verdetto;
  assert.ok(!v.aree.trasparenza.segnali.some((s) => s.codice === "nessun_sito"));
  // giro finale 26/11 (Renato): "Senza risposta" → "Hai risposto «Non so»"
  assert.ok(v.non_verificato.some((t) => /^Hai risposto «Non so»: Il bot indica il sito/.test(t)));
});

test("i codici delle domande in positivo non sono rilevati in automatico (i contrasti restano validi)", () => {
  const automatici = new Set([...codiciAutomatici(), ...JSON.parse(leggi("app/analizzatore.json")).map((r) => r.codice)]);
  for (const codice of Object.keys(IN_POSITIVO)) assert.ok(!automatici.has(codice), codice);
});

// --- correzione A: imitazione composta → rosso, rischio almeno 61 ---
/* "Non so" a tutto ciò che lo ammette; "No" alle domande solo Sì/No (es. la seed phrase). */
function tutteNonso() {
  const r = {};
  for (const d of tutteDomande()) r[d.codice] = (d.risposte || ["si", "no", "nonso"]).includes("nonso") ? "nonso" : "no";
  return r;
}
const imit = (extra) => costruisciVerdetto(input(Object.assign({ risposte: tutteNonso(), sezioniViste: false }, extra)), RISORSE).verdetto;

test("A: @B1nance_Support_bot + dominio con marchio → rosso da imitazione, 83 (somma ÷ 3)", () => {
  const v = imit({ username: "B1nance_Support_bot", linkMiniApp: "https://binance-airdrop-claim.xyz/app" });
  assert.strictEqual(v.rosso_da_imitazione, true);
  assert.strictEqual(v.verdetto, "rosso");
  assert.strictEqual(v.rischio_finale, 83);
  assert.strictEqual(v.fiducia, "bassa");
  assert.ok(v.aree.tecnica.segnali.some((s) => s.codice === "dominio_tld_rischioso"));
});

test("A: @B1nance_Support_bot senza link → rosso da imitazione", () => {
  const v = imit({ username: "B1nance_Support_bot" });
  assert.strictEqual(v.rosso_da_imitazione, true);
  assert.strictEqual(v.verdetto, "rosso");
});

for (const username of ["B1nanceBot", "BinanceP2PEsempioBot", "wallet"]) {
  test("A: @" + username + " → regola non attiva, giallo come prima", () => {
    const v = imit({ username });
    assert.strictEqual(v.rosso_da_imitazione, false);
    assert.strictEqual(v.verdetto, "giallo");
    assert.strictEqual(v.rischio_finale, Math.max(31, v.punteggio_totale));
  });
}

test("A: la spunta solo dichiarata non spegne la regola", () => {
  const r = tutteNonso(); r.bot_ufficiale_verificato = "si";
  assert.strictEqual(imit({ username: "B1nance_Support_bot", risposte: r }).rosso_da_imitazione, true);
});

// --- correzione B: motivi della certezza bassa ---
const motivi = (extra) => costruisciVerdetto(input(extra), RISORSE).motiviCertezzaBassa;

test("B: nessun testo né screenshot → solo nessun_materiale", () => {
  assert.deepStrictEqual(motivi({}), ["nessun_materiale"]);
});

test("B: testo troppo breve → solo testo_breve", () => {
  assert.deepStrictEqual(motivi({ testi: [{ origine: "incollato", testo: "hello" }] }), ["testo_breve"]);
});

test("B: testo lungo ma sezioni prelievo non confermate → solo sezioni_non_confermate", () => {
  assert.deepStrictEqual(motivi({ sezioniViste: false, testi: [{ origine: "incollato", testo: TESTO_LUNGO }] }),
    ["sezioni_non_confermate"]);
});

test("B: testo lungo ma Non so su una domanda delle richieste → solo nonso_richieste", () => {
  const r = risposteSicure(); r.richiesta_deposito = "nonso";
  assert.deepStrictEqual(motivi({ risposte: r, testi: [{ origine: "incollato", testo: TESTO_LUNGO }] }),
    ["nonso_richieste"]);
});

test("B: due motivi insieme (testo breve + sezioni non confermate)", () => {
  assert.deepStrictEqual(motivi({ sezioniViste: false, testi: [{ origine: "incollato", testo: "hello" }] }),
    ["testo_breve", "sezioni_non_confermate"]);
});

test("B: certezza non bassa → nessun motivo", () => {
  assert.deepStrictEqual(motivi({ testi: [{ origine: "incollato", testo: TESTO_LUNGO }] }), []);
  const r = risposteSicure(); r.richiesta_seed_o_codici = "si"; // linea rossa → certezza alta
  assert.deepStrictEqual(motivi({ risposte: r }), []);
});

test("B: caso della revisione (@wallet, testo incollato, tutte Non so) → mai nessun_materiale", () => {
  const r = tutteNonso();
  const out = costruisciVerdetto(input({ username: "wallet", risposte: r, sezioniViste: false,
    testi: [{ origine: "incollato", testo: "Welcome to Wallet. Buy, sell and store crypto. Terms of service apply." }] }), RISORSE);
  assert.strictEqual(out.verdetto.fiducia, "bassa");
  assert.ok(!out.motiviCertezzaBassa.includes("nessun_materiale"));
  assert.deepStrictEqual(out.motiviCertezzaBassa, ["sezioni_non_confermate", "nonso_richieste"]);
});

test("B: con testo incollato non compare mai nessun_materiale", () => {
  for (const testo of ["hello", TESTO_LUNGO]) {
    for (const sezioniViste of [true, false]) {
      assert.ok(!motivi({ sezioniViste, testi: [{ origine: "incollato", testo }] }).includes("nessun_materiale"));
    }
  }
});

test("revisione: spunta dichiarata + link positivi, senza materiale → al massimo verde con riserva", () => {
  const r = risposteSicure(); r.bot_ufficiale_verificato = "si";
  const { verdetto } = costruisciVerdetto(input({ risposte: r, linkPositivi: ["https://a.com/1", "https://b.com/2"] }), RISORSE);
  assert.strictEqual(verdetto.fiducia, "bassa");
  assert.ok(verdetto.verdetto !== "verde" || verdetto.verde_con_riserva);
});

/* --- schermata di conferma prima dell'esito (18/11/2026) --- */
const { contaRisposte, domandeVisibili } = require(path.join(KIT, "app", "assembla.js"));

test("contaRisposte: conta solo le domande visibili e i Non so", () => {
  const r = risposteSicure();
  const c = contaRisposte(QUESTIONARIO, r);
  assert.strictEqual(c.risposte, domandeVisibili(QUESTIONARIO, r).length);
  assert.ok(c.risposte < tutteDomande().length); // le condizionali nascoste non contano
  assert.strictEqual(c.nonso, 0);
});

test("contaRisposte: i Non so si contano a parte", () => {
  const r = risposteSicure();
  const prima = tutteDomande().find((d) => !d.mostra_se && !d.risposte);
  r[prima.codice] = "nonso";
  const c = contaRisposte(QUESTIONARIO, r);
  assert.strictEqual(c.nonso, 1);
});

test("contaRisposte: senza risposte → zero", () => {
  assert.deepStrictEqual(contaRisposte(QUESTIONARIO, {}), { risposte: 0, nonso: 0 });
});


/* --- verde con riserva senza materiale (18/11/2026) --- */
test("riserva: un solo \"Non so\" → niente verde", () => {
  const r = risposteSicure();
  const d = tutteDomande().find((x) => !x.mostra_se && !x.risposte);
  r[d.codice] = "nonso";
  const { verdetto } = costruisciVerdetto(input({ risposte: r }), RISORSE);
  assert.strictEqual(verdetto.verdetto, "giallo");
  assert.strictEqual(verdetto.verde_con_riserva, false);
});

test("riserva: sezioni prelievo non aperte → niente verde", () => {
  const { verdetto } = costruisciVerdetto(input({ sezioniViste: false }), RISORSE);
  assert.strictEqual(verdetto.verdetto, "giallo");
  assert.strictEqual(verdetto.verde_con_riserva, false);
});

test("riserva: piccoli segnali + 20 punti oltre 30 → giallo", () => {
  const r = risposteSicure();
  for (const d of tutteDomande()) if (["nessun_sito", "nessun_termini_privacy"].includes(d.codice)) r[d.codice] = d.segnale_se === "no" ? "no" : "si";
  const { verdetto } = costruisciVerdetto(input({ risposte: r }), RISORSE);
  assert.strictEqual(verdetto.punteggio_totale, 13); // 40 ÷ 3
  assert.strictEqual(verdetto.verdetto, "giallo");
  assert.strictEqual(verdetto.verde_con_riserva, false);
});

test("riserva: con materiale vero nessun malus", () => {
  const { verdetto } = costruisciVerdetto(input({ username: "wallet", testi: [{ origine: "incollato", testo: TESTO_LUNGO }] }), RISORSE);
  assert.strictEqual(verdetto.verdetto, "verde");
  assert.strictEqual(verdetto.verde_con_riserva, false);
  assert.strictEqual(verdetto.rischio_finale, verdetto.punteggio_totale);
});

test("note dell'utente: nel verdetto, ripulite, senza effetto sul punteggio", () => {
  const senza = costruisciVerdetto(input({}), RISORSE).verdetto;
  const con = costruisciVerdetto(input({ note: "  mi ha chiesto la seed phrase, non so se fidarmi  " }), RISORSE).verdetto;
  assert.strictEqual(con.note_utente, "mi ha chiesto la seed phrase, non so se fidarmi");
  assert.strictEqual(con.rischio_finale, senza.rischio_finale);
  assert.strictEqual(con.verdetto, senza.verdetto);
  assert.strictEqual(senza.note_utente, undefined);
  assert.strictEqual(costruisciVerdetto(input({ note: "x".repeat(5000) }), RISORSE).verdetto.note_utente.length, 2000);
});


/* --- revisione indipendente 18/11/2026 --- */
test("discrepanza segnalata anche per un segnale assorbito da un'altra domanda (punto 6)", () => {
  const r = risposteSicure(); // "No" alla domanda sulle esche, che assorbe urgenza_pressione
  const { verdetto, contrasti } = costruisciVerdetto(input({ risposte: r,
    testi: [{ origine: "incollato", testo: "Offerta a tempo limitato: agisci ora, restano poche ore per partecipare." }] }), RISORSE);
  assert.ok(verdetto.aree.promesse.segnali.some((s) => s.codice === "urgenza_pressione"));
  assert.ok(contrasti.some((c) => c.codice === "urgenza_pressione"), JSON.stringify(contrasti));
});

test("nessuna discrepanza se la risposta conferma il segnale o è \"Non so\"", () => {
  const r = risposteSicure();
  const esche = tutteDomande().find((d) => (d.assorbe || []).includes("urgenza_pressione"));
  for (const v of ["si", "nonso"]) {
    r[esche.codice] = v;
    const { contrasti } = costruisciVerdetto(input({ risposte: r,
      testi: [{ origine: "incollato", testo: "Offerta a tempo limitato: agisci ora, restano poche ore per partecipare." }] }), RISORSE);
    assert.ok(!contrasti.some((c) => c.codice === "urgenza_pressione"), v);
  }
});


/* --- Tester UX 26/11/2026 (Luca): risposte contraddittorie --- */
const { contraddizioniAttive } = require(path.join(KIT, "app", "assembla.js"));

test("contraddizioni: badge blu e etichetta SCAM insieme → avviso, certezza bassa, motivo spiegato", () => {
  const r = risposteSicure(); r.bot_ufficiale_verificato = "si"; r.etichetta_scam_telegram = "si";
  assert.strictEqual(contraddizioniAttive(QUESTIONARIO, r).length, 1);
  const out = costruisciVerdetto(input({ risposte: r, testi: [{ origine: "incollato", testo: TESTO_LUNGO }] }), RISORSE);
  assert.strictEqual(out.verdetto.contesto.risposte_contraddittorie, true);
  assert.strictEqual(out.verdetto.verdetto, "rosso");
  assert.strictEqual(out.verdetto.fiducia, "bassa");
  assert.ok(out.motiviCertezzaBassa.includes("risposte_contraddittorie"));
  assert.ok(out.contraddizioni.length === 1 && /SCAM/.test(out.contraddizioni[0]));
});

test("contraddizioni: risposte coerenti → nessuna", () => {
  assert.deepStrictEqual(contraddizioniAttive(QUESTIONARIO, risposteSicure()), []);
  const out = costruisciVerdetto(input(), RISORSE);
  assert.strictEqual(out.verdetto.contesto.risposte_contraddittorie, false);
});

test("contraddizioni: anche le discrepanze tra risposte e testo incollato contano", () => {
  const r = risposteSicure(); // seed phrase: No
  const out = costruisciVerdetto(input({ risposte: r,
    testi: [{ origine: "incollato", testo: "Benvenuto! Enter your 12-word seed phrase to verify your wallet and claim the reward." }] }), RISORSE);
  assert.ok(out.contrasti.length >= 1);
  assert.strictEqual(out.verdetto.contesto.risposte_contraddittorie, true);
  assert.strictEqual(out.verdetto.fiducia, "bassa");
});

test("contraddizioni: ogni regola del questionario usa codici e risposte esistenti", () => {
  const codici = new Set(tutteDomande().map((d) => d.codice));
  for (const c of QUESTIONARIO.contraddizioni) {
    assert.ok(c.testo && c.quando.length >= 2);
    for (const [codice, risposta] of c.quando) assert.ok(codici.has(codice) && ["si", "no"].includes(risposta), codice);
  }
});


/* --- Tester UX 26/11/2026 (Giulia): scorciatoia quando il testo contiene già una linea rossa --- */
const { lineeRosseNelTesto } = require(path.join(KIT, "app", "assembla.js"));
const SEED = "Benvenuto! Per ricevere i fondi inserisci la tua frase di recupero di 24 parole per la verifica.";

test("lineeRosseNelTesto: trova la richiesta della seed phrase nel testo incollato", () => {
  assert.deepStrictEqual(lineeRosseNelTesto([{ origine: "incollato", testo: SEED }], RISORSE), ["richiesta_seed_o_codici"]);
});

test("lineeRosseNelTesto: niente se la frase è una negazione o se mancano testi", () => {
  assert.deepStrictEqual(lineeRosseNelTesto([{ origine: "incollato", testo: "Non condividere mai la tua seed phrase con nessuno." }], RISORSE), []);
  assert.deepStrictEqual(lineeRosseNelTesto([], RISORSE), []);
  assert.deepStrictEqual(lineeRosseNelTesto([{ origine: "incollato", testo: "Promette guadagni a chi invita amici" }], RISORSE), []);
});

test("esito rapido: senza risposte, solo il testo → rosso per la linea rossa, nessuna risposta inventata", () => {
  const out = costruisciVerdetto({ username: "TonkeeperWalIetEsempioBot", nomeVisualizzato: "", risposte: {}, sezioniViste: null,
    testi: [{ origine: "incollato", testo: SEED }], linkMiniApp: "", linkSegnalazioni: [], linkPositivi: [], rapido: true }, RISORSE);
  assert.strictEqual(out.verdetto.verdetto, "rosso");
  assert.ok(out.verdetto.linee_rosse.some((l) => l.codice === "richiesta_seed_o_codici"));
  assert.ok(out.verdetto.non_verificato.some((t) => /esito rapido/i.test(t)));
  assert.strictEqual(out.verdetto.contesto.risposte_complete, false);
  // nessun segnale nasce da una risposta: tutti dal testo o dal nome
  for (const a of Object.values(out.verdetto.aree)) for (const s of a.segnali) assert.ok(!/risposta/i.test(s.fonte || ""), s.codice);
});


/* --- Tester UX 26/11/2026 (Giulia): "quante domande mancano?" --- */
const { contatoreDomande } = require(path.join(KIT, "app", "assembla.js"));

test("contatoreDomande: pagine in sequenza, totale con la domanda finale sui pulsanti", () => {
  const r = risposteSicure(); // non promette guadagni: le condizionali restano nascoste
  const visibili = domandeVisibili(QUESTIONARIO, r).length;
  const p0 = contatoreDomande(QUESTIONARIO, r, 0);
  assert.deepStrictEqual([p0.da, p0.a, p0.totale], [1, QUESTIONARIO.pagine[0].domande.length, visibili + 1]);
  const p1 = contatoreDomande(QUESTIONARIO, r, 1);
  assert.strictEqual(p1.da, p0.a + 1);
  const finale = contatoreDomande(QUESTIONARIO, r, QUESTIONARIO.pagine.length);
  assert.deepStrictEqual([finale.da, finale.a], [visibili + 1, visibili + 1]);
});

test("contatoreDomande: le condizionali che compaiono allungano il totale", () => {
  const r = risposteSicure();
  const prima = contatoreDomande(QUESTIONARIO, r, 1).totale;
  r.promessa_guadagno = "si";
  assert.ok(contatoreDomande(QUESTIONARIO, r, 1).totale > prima);
});


/* --- Tester UX 26/11/2026 (Renato, 2° giro): "Cosa fare" concreto nel giallo dovuto solo a verifiche mancanti --- */
test("giallo di sola prudenza: azioni concrete al posto di 'massima cautela'", () => {
  const out = costruisciVerdetto(input({ sezioniViste: false, testi: [{ origine: "incollato", testo: TESTO_LUNGO }] }), RISORSE);
  assert.strictEqual(out.verdetto.verdetto, "giallo");
  const fare = out.verdetto.cosa_fare.join(" | ");
  assert.match(fare, /esci senza confermare/);
  assert.doesNotMatch(fare, /massima cautela/);
});

test("giallo di sola prudenza con Non so sulle richieste: invita a completarle", () => {
  const r = risposteSicure(); r.richiesta_deposito = "nonso";
  const out = costruisciVerdetto(input({ risposte: r, testi: [{ origine: "incollato", testo: TESTO_LUNGO }] }), RISORSE);
  assert.strictEqual(out.verdetto.verdetto, "giallo");
  assert.match(out.verdetto.cosa_fare.join(" | "), /Non so/);
});

test("giallo con segnali veri: restano le cautele normali", () => {
  const r = risposteSicure(); r.richiesta_deposito = "si"; r.richiesta_dati_personali = "si";
  const out = costruisciVerdetto(input({ risposte: r, testi: [{ origine: "incollato", testo: TESTO_LUNGO }] }), RISORSE);
  assert.strictEqual(out.verdetto.verdetto, "giallo");
  assert.match(out.verdetto.cosa_fare.join(" | "), /massima cautela/);
});


/* --- Giro finale 26/11/2026 (Luca): imitazione + badge dichiarato dava un falso verde --- */
const { contraddizioniNome } = require(path.join(KIT, "app", "assembla.js"));
const imitazioneConBadge = (extra) => {
  const r = risposteSicure(); r.bot_ufficiale_verificato = "si";
  return costruisciVerdetto(input(Object.assign({ username: "TonkeeperWalIetEsempioBot", risposte: r }, extra)), RISORSE);
};

test("imitazione trovata dal controllo + badge dichiarato → prevale il controllo: niente verde", () => {
  const out = imitazioneConBadge({ nomeVisualizzato: "Tonkeeper Wallet" });
  const codici = Object.values(out.verdetto.aree).flatMap((a) => a.segnali.map((s) => s.codice));
  assert.ok(codici.includes("nome_imita_marchio"));
  assert.ok(!codici.includes("bot_ufficiale_verificato"), "il badge dichiarato non toglie punti");
  assert.notStrictEqual(out.verdetto.verdetto, "verde");
  assert.ok(out.contrasti.some((c) => c.codice === "bot_ufficiale_verificato"));
  assert.strictEqual(out.verdetto.fiducia, "bassa");
});

test("spunta emoji nel nome + badge Sì → contraddizione spiegata", () => {
  assert.strictEqual(contraddizioniNome("Tonkeeper Wallet ✅", { bot_ufficiale_verificato: "si" }).length, 1);
  assert.strictEqual(contraddizioniNome("Tonkeeper Wallet ☑️", { bot_ufficiale_verificato: "si" }).length, 1);
  assert.strictEqual(contraddizioniNome("Tonkeeper Wallet ✔", { bot_ufficiale_verificato: "si" }).length, 1);
  assert.deepStrictEqual(contraddizioniNome("Tonkeeper Wallet ✅", { bot_ufficiale_verificato: "no" }), []);
  assert.deepStrictEqual(contraddizioniNome("Wallet", { bot_ufficiale_verificato: "si" }), []);
  const out = imitazioneConBadge({ nomeVisualizzato: "Tonkeeper Wallet ✅" });
  assert.ok(out.contraddizioni.some((t) => /emoji/.test(t)));
});

test("il bot ufficiale vero con badge resta pulito (nessuna imitazione, nessuna contraddizione)", () => {
  const r = risposteSicure(); r.bot_ufficiale_verificato = "si";
  const out = costruisciVerdetto(input({ username: "wallet", nomeVisualizzato: "Wallet", risposte: r,
    testi: [{ origine: "incollato", testo: TESTO_LUNGO }] }), RISORSE);
  assert.strictEqual(out.verdetto.verdetto, "verde");
  assert.deepStrictEqual(out.contraddizioni, []);
  assert.deepStrictEqual(out.contrasti, []);
});


test("rosso: cosa fare distingue 'non ho pagato' da 'ho già pagato' e indica dove segnalare", () => {
  const r = risposteSicure(); r.richiesta_seed_o_codici = "si";
  const fare = costruisciVerdetto(input({ risposte: r }), RISORSE).verdetto.cosa_fare.join(" | ");
  assert.match(fare, /blocca/i);
  assert.match(fare, /Se non hai ancora pagato/);
  assert.match(fare, /commissariatodips\.it/);
  assert.match(fare, /tre puntini/);
});
