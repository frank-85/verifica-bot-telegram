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
