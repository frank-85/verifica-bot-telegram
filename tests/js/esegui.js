/* Ponte per i test di parità: legge {op, casi, ...} da stdin, scrive l'elenco dei risultati su stdout. */
"use strict";
const path = require("path");
const APP = path.join(__dirname, "..", "..", "app");
const motore = require(path.join(APP, "motore.js"));

function esegui(op, caso, payload) {
  if (op === "calcola") return motore.calcola(caso, motore.catalogoDaLista(payload.catalogo));
  if (op === "nome") {
    const nome = require(path.join(APP, "nome.js"));
    return nome.analizzaNome(caso, nome.caricaMarchi(payload.marchi));
  }
  if (op === "dominio") return require(path.join(APP, "sicurezza.js")).dominioBase(caso);
  if (op === "assembla") {
    const assembla = require(path.join(APP, "assembla.js"));
    return assembla.costruisciVerdetto(caso, assembla.risorseDaPayload(payload));
  }
  throw new Error("op sconosciuta: " + op);
}

let ingresso = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (c) => { ingresso += c; });
process.stdin.on("end", () => {
  const payload = JSON.parse(ingresso);
  const out = payload.casi.map((caso) => {
    try {
      return { ok: true, risultato: esegui(payload.op, caso, payload) };
    } catch (e) {
      if (e instanceof motore.ErroreVerdetto) return { ok: false, errore: true, messaggio: e.message };
      return { ok: false, errore: true, messaggio: String(e && e.message), tipo: "altro" };
    }
  });
  process.stdout.write(JSON.stringify(out));
});
