"use strict";
const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const path = require("path");
const KIT = path.join(__dirname, "..", "..");
const { caricaMarchi, analizzaNomeVisualizzato } = require(path.join(KIT, "app", "nome.js"));
const MARCHI = caricaMarchi(fs.readFileSync(path.join(KIT, "marchi.txt"), "utf8"));

test("nome con lettere decorative: riconosciuto e normalizzato", () => {
  const r = analizzaNomeVisualizzato("𝐁𝐈𝐍𝐀𝐍𝐂𝐄 𝐖𝐀𝐋𝐋𝐄𝐓", MARCHI);
  assert.strictEqual(r.decorato, true);
  assert.ok(r.imitazioni.some((i) => i.marchio === "binance"));
});

test("nome normale: non decorato", () => {
  const r = analizzaNomeVisualizzato("Meteo Verona", MARCHI);
  assert.strictEqual(r.decorato, false);
  assert.deepStrictEqual(r.imitazioni, []);
});

// --- M1: link d'invito riconosciuti (stessi casi di tests/test_nome.py) ---
const { eLinkInvito } = require(path.join(KIT, "app", "nome.js"));

test("link d'invito riconosciuti", () => {
  for (const t of ["https://t.me/+AbCdEf123", "t.me/joinchat/AbCdEf", "tg://join?invite=AbCd", "https://telegram.me/+xyz"])
    assert.strictEqual(eLinkInvito(t), true, t);
  for (const t of ["@wallet", "https://t.me/wallet", "+39 333 1234567", "tg://resolve?domain=wallet"])
    assert.strictEqual(eLinkInvito(t), false, t);
});


/* --- Tester UX 26/11/2026 (Luca): username con spazi, simboli o troppo corto accettati in silenzio --- */
const { problemaUsername } = require(path.join(KIT, "app", "nome.js"));

test("problemaUsername: username validi → nessun problema", () => {
  for (const u of ["wallet", "TapMinerEsempioBot", "Tonkeeper_Wal1et_bot", "abcd"]) assert.strictEqual(problemaUsername(u), "", u);
});

test("problemaUsername: spazi → suggerisce la versione senza spazi", () => {
  const m = problemaUsername("Tap Miner EsempioBot");
  assert.match(m, /non hanno spazi/);
  assert.match(m, /@TapMinerEsempioBot/);
});

test("problemaUsername: simboli non ammessi → lo dice senza ripeterli", () => {
  const m = problemaUsername("<b>x</b><script>alert(1)</script>");
  assert.match(m, /solo lettere, numeri e trattino basso/);
  assert.ok(!/script/.test(m));
  assert.match(problemaUsername("Tap💎Miner"), /solo lettere, numeri/);
});

test("problemaUsername: troppo corto", () => {
  assert.match(problemaUsername("ab"), /troppo corto/);
});


/* --- Giro finale 26/11/2026: messaggi più precisi e "cosa fare" sul rosso --- */
test("problemaUsername: lettere non latine nominate, username troppo lungo", () => {
  assert.match(problemaUsername("TonkeeperWalletBоt"), /lettere non latine/); // o cirillica
  assert.match(problemaUsername("a".repeat(40)), /troppo lungo/);
});
