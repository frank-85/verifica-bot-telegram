"use strict";
const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const path = require("path");
const KIT = path.join(__dirname, "..", "..");
const { analizzaTesto, analizzaLink, normalizzaTesto } = require(path.join(KIT, "app", "analizzatore.js"));
const { caricaMarchi } = require(path.join(KIT, "app", "nome.js"));
const REGOLE = JSON.parse(fs.readFileSync(path.join(KIT, "app", "analizzatore.json"), "utf8"));
const MARCHI = caricaMarchi(fs.readFileSync(path.join(KIT, "marchi.txt"), "utf8"));
const CATALOGO = JSON.parse(fs.readFileSync(path.join(KIT, "segnali.json"), "utf8"));

const codici = (t) => analizzaTesto(t, REGOLE).map((r) => r.codice).sort();

const VERE = [
  ["Withdrawals are available only for users with at least one active deposit (boost) or 50 invites", "prelievo_condizionato"],
  ["I prelievi sono disponibili solo per chi ha almeno un deposito attivo", "prelievo_condizionato"],
  ["To withdraw you must first pay a 10 USDT fee", "prelievo_condizionato"],
  ["deposit to withdraw your earnings", "prelievo_condizionato"],
  ["Enter your 12-word seed phrase to verify", "richiesta_seed_o_codici"],
  ["inserisci il codice che ti ha inviato Telegram", "richiesta_seed_o_codici"],
  ["Please type your private key", "richiesta_seed_o_codici"],
  ["Guaranteed 3% daily profit", "rendimento_garantito"],
  ["Rendimento garantito del 20% al mese", "rendimento_garantito"],
  ["Connect your wallet to claim", "richiesta_wallet_connect"],
  ["Connect your wallet to claim", "bonus_regalo_esca"],
  ["Collega il tuo wallet", "richiesta_wallet_connect"],
  ["Press Win+R and paste", "richiesta_comando_pc"],
  ["powershell -enc SQBFAFgA", "richiesta_comando_pc"],
  ["Offer ends in 10 minutes", "urgenza_pressione"],
  ["Ultimi posti disponibili, affrettati!", "urgenza_pressione"],
  ["Start earning real money", "promessa_guadagno"],
  ["Guadagna soldi veri ogni giorno", "promessa_guadagno"],
  ["Invite 5 friends to earn more", "referral_piramidale"],
  ["Make a deposit of 50 TON to start", "richiesta_deposito"],
  ["Free airdrop for early users", "bonus_regalo_esca"],
];

for (const [frase, codice] of VERE) {
  test(`frase vera → ${codice}: ${frase}`, () => {
    assert.ok(codici(frase).includes(codice), JSON.stringify(analizzaTesto(frase, REGOLE)));
  });
}

const INNOCUE = ["Benvenuto! Scegli la lingua", "Il tuo ordine è in consegna",
  "Never share your seed phrase with anyone", "Non condividere mai il codice di accesso",
  "Privacy policy", "Meteo di oggi: sole a Verona"];

for (const frase of INNOCUE) {
  test(`frase innocua → nessun segnale: ${frase}`, () => {
    assert.deepStrictEqual(codici(frase), []);
  });
}

test("un solo risultato per codice, con la frase trovata", () => {
  const r = analizzaTesto("Guaranteed profit! Guaranteed 2% daily return!", REGOLE);
  const garantiti = r.filter((x) => x.codice === "rendimento_garantito");
  assert.strictEqual(garantiti.length, 1);
  assert.ok(garantiti[0].frase.length > 0 && garantiti[0].frase.length <= 160);
});

test("testo da 200.000 caratteri analizzato in meno di 500 ms", () => {
  const t0 = Date.now();
  analizzaTesto("a".repeat(200000) + " seed phrase", REGOLE);
  analizzaTesto("deposit ".repeat(25000), REGOLE);
  assert.ok(Date.now() - t0 < 500, `durata ${Date.now() - t0} ms`);
});

test("ogni regola usa un codice del catalogo con l'area giusta", () => {
  const cat = Object.fromEntries(CATALOGO.map((c) => [c.codice, c]));
  for (const r of REGOLE) {
    assert.ok(cat[r.codice], r.codice);
    assert.strictEqual(cat[r.codice].area, r.area, r.codice);
  }
});

test("normalizzaTesto: NFKC, minuscole, spazi compattati", () => {
  assert.strictEqual(normalizzaTesto("  𝐒𝐄𝐄𝐃\n\n Phrase "), "seed phrase");
});

test("link con marchio nel dominio → dominio_con_marchio", () => {
  const r = analizzaLink("https://binance-wallet-app.com/x", MARCHI);
  assert.strictEqual(r.valido, true);
  assert.deepStrictEqual(r.segnali.map((s) => s.codice), ["dominio_con_marchio"]);
});

test("sito ufficiale del marchio → nessun segnale", () => {
  const r = analizzaLink("https://www.binance.com", MARCHI);
  assert.strictEqual(r.valido, true);
  assert.deepStrictEqual(r.segnali, []);
});

test("punycode → avviso caratteri ingannevoli", () => {
  const r = analizzaLink("https://xn--bnance-7ua.com", MARCHI);
  assert.ok(r.avvisi.some((a) => /ingannevol/.test(a)));
});

test("link non validi → valido false", () => {
  for (const u of ["javascript:alert(1)", "non un link", "data:text/html,x", ""]) {
    assert.strictEqual(analizzaLink(u, MARCHI).valido, false, u);
  }
});

// --- revisione finale: falsi positivi sulle linee rosse e negazione aggirabile ---
const INNOCUE_REVISIONE = [
  "Codice di accesso: 12345. Non dare questo codice a nessuno, neanche se dice di essere Telegram.",
  "Write down your 24 words recovery phrase and keep it offline",
  "Scrivi le tue 24 parole su un foglio e conservalo in un luogo sicuro",
  "Your 2FA code for login is 123456",
  "Sconto del 20% al mese per i nuovi iscritti",
  "Cashback 5% monthly on all purchases",
  "Prezzo garantito: 20% in meno",
  "Open PowerShell and run winget upgrade",
  "Never enter your seed phrase on any website",
];
for (const frase of INNOCUE_REVISIONE) {
  test(`revisione: nessuna linea rossa per frase innocua: ${frase}`, () => {
    const rosse = ["richiesta_seed_o_codici", "richiesta_comando_pc", "rendimento_garantito", "prelievo_condizionato"];
    assert.deepStrictEqual(codici(frase).filter((c) => rosse.includes(c)), []);
  });
}
const VERE_REVISIONE = [
  ["Don't worry, just enter your seed phrase", "richiesta_seed_o_codici"],
  ["Nevertheless, enter your seed phrase to continue", "richiesta_seed_o_codici"],
  ["Send us your 6-digit Telegram code", "richiesta_seed_o_codici"],
  ["Importa il wallet inserendo la frase di recupero di 12 parole", "richiesta_seed_o_codici"],
  ["Copy this and paste it into PowerShell", "richiesta_comando_pc"],
  ["Earn a 3% daily return on your deposit", "rendimento_garantito"],
];
for (const [frase, codice] of VERE_REVISIONE) {
  test(`revisione: frase vera → ${codice}: ${frase}`, () => {
    assert.ok(codici(frase).includes(codice), JSON.stringify(analizzaTesto(frase, REGOLE)));
  });
}

// --- M2: marchio nei sottodomini, sito ufficiale escluso, IP numerici ---
const codiciLink = (u) => analizzaLink(u, MARCHI).segnali.map((s) => s.codice);

test("marchio nel sottodominio → dominio_con_marchio", () => {
  assert.deepStrictEqual(codiciLink("https://binance.sito-falso.xyz/login"), ["dominio_con_marchio"]);
  assert.deepStrictEqual(codiciLink("https://secure-metamask.login.verifica.app"), ["dominio_con_marchio"]);
  assert.match(analizzaLink("https://binance.sito-falso.xyz", MARCHI).segnali[0].frase, /binance\.sito-falso\.xyz/);
});

test("sottodomini del sito ufficiale → nessun segnale", () => {
  for (const u of ["https://accounts.binance.com/it", "https://wallet.binance.com"])
    assert.deepStrictEqual(codiciLink(u), [], u);
});

test("parola generica nel sottodominio → nessun segnale", () => {
  assert.deepStrictEqual(codiciLink("https://wallet.negozio.it"), []);
});

test("indirizzo IP numerico → avviso, nessun controllo marchio", () => {
  for (const u of ["http://185.23.10.4/app", "https://[2001:db8::1]/x"]) {
    const r = analizzaLink(u, MARCHI);
    assert.strictEqual(r.valido, true, u);
    assert.deepStrictEqual(r.segnali, [], u);
    assert.ok(r.avvisi.some((a) => /indirizzo IP/.test(a)), u);
  }
});
