"use strict";
const test = require("node:test");
const assert = require("node:assert");
const path = require("path");
const { disinnesca, dominioBase, FONTI_AFFIDABILI } = require(path.join(__dirname, "..", "..", "app", "sicurezza.js"));

test("link a un bot: non cliccabile e disinnescato", () => {
  const r = disinnesca("https://t.me/MetamasksAppWebBot");
  assert.strictEqual(r.href, null);
  assert.ok(r.testo.startsWith("hxxps://"), r.testo);
});

test("fonte affidabile: cliccabile", () => {
  assert.strictEqual(disinnesca("https://www.consob.it/x").href, "https://www.consob.it/x");
  assert.strictEqual(disinnesca("https://dev.to/a").href, "https://dev.to/a");
});

test("http semplice di fonte affidabile: non cliccabile", () => {
  const r = disinnesca("http://www.consob.it/x");
  assert.strictEqual(r.href, null);
  assert.ok(r.testo.startsWith("hxxp://"));
});

test("schemi pericolosi: mai cliccabili", () => {
  for (const u of ["javascript:alert(1)", "data:text/html,<b>x</b>", "JaVaScRiPt:alert(1)"]) {
    assert.strictEqual(disinnesca(u).href, null, u);
  }
});

test("dominio che finisce come una fonte affidabile ma non lo è", () => {
  assert.strictEqual(disinnesca("https://evilconsob.it/x").href, null);
  assert.strictEqual(disinnesca("https://consob.it.evil.com/x").href, null);
});

test("dominioBase", () => {
  assert.strictEqual(dominioBase("a.b.example.com"), "example.com");
  assert.strictEqual(dominioBase("www.consob.it"), "consob.it");
});

test("t.me non è tra le fonti affidabili", () => {
  assert.ok(!FONTI_AFFIDABILI.includes("t.me"));
});

test("revisione: in autovalutazione i link non sono mai cliccabili, neanche se affidabili", () => {
  assert.strictEqual(disinnesca("https://github.com/evil/x/releases/download/a.exe", { sempre: true }).href, null);
  assert.ok(disinnesca("https://github.com/evil/x", { sempre: true }).testo.startsWith("hxxps://"));
});

test("revisione: URL con credenziali (userinfo) mai cliccabili", () => {
  assert.strictEqual(disinnesca("https://evil.com@github.com/").href, null);
});
