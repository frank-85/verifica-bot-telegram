"""Genera index.html: un solo file offline con dati, motore JS e interfaccia.

Uso:  python -I costruisci_app.py [--numero-test N]
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

KIT = Path(__file__).resolve().parent
# sicurezza.js per primo: ha la regola unica del dominio base usata da motore.js e analizzatore.js
ORDINE_JS = ["sicurezza.js", "motore.js", "aspetto.js", "nome.js", "analizzatore.js", "assembla.js"]
USCITA = "index.html"


def _json(percorso: Path):
    return json.loads(percorso.read_text(encoding="utf-8"))


def _controlla_codici(nome: str, codici, catalogo: dict) -> None:
    ignoti = sorted({c for c in codici if c not in catalogo})
    if ignoti:
        raise SystemExit(f"{nome}: codici non presenti in segnali.json: {', '.join(ignoti)}")


def costruisci(kit: Path = KIT, uscita: Path | None = None, numero_test: int | None = None) -> Path:
    app = kit / "app"
    catalogo_lista = _json(kit / "segnali.json")
    catalogo = {v["codice"]: v for v in catalogo_lista}
    questionario = _json(app / "questionario.json")
    regole = _json(app / "analizzatore.json")
    domande = [d for p in questionario["pagine"] for d in p["domande"]]
    _controlla_codici("questionario.json",
                      [d["codice"] for d in domande]
                      + [c for d in domande for c in d.get("assorbe", [])]
                      + [d["mostra_se"]["codice"] for d in domande if d.get("mostra_se")]
                      + questionario.get("non_coperti", []), catalogo)
    _controlla_codici("analizzatore.json", [r["codice"] for r in regole], catalogo)

    dati = {"catalogo": catalogo_lista, "marchi": (kit / "marchi.txt").read_text(encoding="utf-8"),
            "questionario": questionario, "regole": regole,
            "generato": datetime.now().isoformat(timespec="seconds"), "numero_test": numero_test}
    blocco_dati = ('<script type="application/json" id="dati">'
                   + json.dumps(dati, ensure_ascii=False).replace("</", "<\\/") + "</script>")
    blocco_js = "\n".join(f"<script>\n{(app / f).read_text(encoding='utf-8')}\n</script>" for f in ORDINE_JS)

    modello = (app / "modello.html").read_text(encoding="utf-8")
    for segnaposto in ("<!--DATI-->", "<!--SCRIPT-->"):
        if modello.count(segnaposto) != 1:
            raise SystemExit(f"modello.html: il segnaposto {segnaposto} deve comparire una volta")
    html = modello.replace("<!--DATI-->", blocco_dati).replace("<!--SCRIPT-->", blocco_js)

    uscita = Path(uscita) if uscita else kit / USCITA
    dati_bin = html.encode("utf-8")
    uscita.write_bytes(dati_bin)
    return uscita


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Genera l'app Verifica Bot in un solo file")
    p.add_argument("--numero-test", type=int, default=None)
    args = p.parse_args(argv)
    print(costruisci(numero_test=args.numero_test))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
