"""Riga di comando del kit /verifica-bot. Ogni sottocomando stampa JSON su stdout.

Uso:  python -I controlli.py <sottocomando> ...
Exit: 0 ok (anche con esito non_verificato) · 1 errore di input.
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

KIT = Path(__file__).resolve().parent
if str(KIT) not in sys.path:  # python -I non aggiunge la cartella dello script
    sys.path.insert(0, str(KIT))

from file_check import analizza_file  # noqa: E402
from nome import analizza_nome, e_link_invito, normalizza_username  # noqa: E402
from punteggio import PESI, ErroreVerdetto, calcola, carica_catalogo  # noqa: E402
from resoconto import FIDUCIA_NEL_BOT, genera_md  # noqa: E402
import rete  # noqa: E402


class ErroreInput(Exception):
    pass


USO = ("python -I controlli.py [--radice CARTELLA] "
       "<nome|anteprima|dominio|pagina|file|punteggio|nuova> …  (--help per l'elenco completo)")
TRADUZIONI_ARGPARSE = [("the following arguments are required", "mancano argomenti obbligatori"),
                       ("invalid choice", "comando sconosciuto"), ("choose from", "scegli tra"),
                       ("unrecognized arguments", "argomenti non riconosciuti"),
                       ("expected one argument", "manca il valore dell'opzione")]


class _Parser(argparse.ArgumentParser):
    """Errori di argomenti come gli altri: messaggio in italiano ed exit 1 (non l'exit 2 di argparse)."""

    def error(self, message):
        for inglese, italiano in TRADUZIONI_ARGPARSE:
            message = message.replace(inglese, italiano)
        raise ErroreInput(f"argomenti non validi ({message}).\nUso: {USO}")


FILE_KIT = ("segnali.json", "marchi.txt")


def _controlla_kit() -> None:
    """Un kit incompleto o danneggiato dà un messaggio chiaro, non un traceback."""
    for nome_file in FILE_KIT:
        f = KIT / nome_file
        try:
            testo = f.read_text(encoding="utf-8")
            if nome_file.endswith(".json"):
                json.loads(testo)
        except FileNotFoundError:
            raise ErroreInput(f"file del kit mancante: {nome_file} (atteso in {KIT}). "
                              "Ripristinalo dalla copia del kit.") from None
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            raise ErroreInput(f"file del kit danneggiato: {nome_file} ({e}). "
                              "Ripristinalo dalla copia del kit.") from None


def _username_valido(testo: str) -> str:
    username = normalizza_username(testo)
    if username:
        return username
    if e_link_invito(testo):
        raise ErroreInput("questo è un link d'invito a un gruppo o canale, non a un bot: "
                          "apri il bot su Telegram e copia il suo @username")
    raise ErroreInput("username vuoto o link che non indica un bot: usa @NomeDelBot o t.me/NomeDelBot")


def _stampa(dati: dict) -> None:
    pulito = {k: v for k, v in dati.items() if k != "dati"}
    sys.stdout.write(json.dumps(pulito, ensure_ascii=False, indent=2) + "\n")


def _scrivi_json(percorso: Path, dati: dict) -> None:
    percorso.write_bytes(json.dumps(dati, ensure_ascii=False, indent=2).encode("utf-8"))


def scheletro(username: str) -> dict:
    return {
        "versione_schema": 1,
        "data": datetime.now().isoformat(timespec="seconds"),
        "bot": {"username": username, "tipo": "", "link": []},
        "verdetto": None, "fiducia": None, "punteggio_totale": None, "rischio_finale": None,
        "pesi": dict(PESI),
        "linee_rosse": [], "rosso_da_segnalazioni": False, "rosso_da_imitazione": False,
        "aree": {a: {"rischio": 0, "segnali": []} for a in PESI},
        "contesto": {"materiale_utente": False, "tecnica_completa": False, "fonti_indipendenti": 0},
        "cosa_fare": [], "cosa_non_fare": [], "non_verificato": [], "fonti": [],
    }


def cmd_nuova(args) -> dict:
    username = _username_valido(args.username)
    sicuro = re.sub(r"[^\w-]", "_", username)
    cartella = Path(args.radice) / "verifiche" / f"{datetime.now():%Y-%m-%d}_{sicuro}"
    (cartella / "scaricati").mkdir(parents=True, exist_ok=True)
    f = cartella / "verdetto.json"
    nuova = not f.exists()
    if nuova:
        _scrivi_json(f, scheletro(username))
    return {"cartella": str(cartella), "verdetto_json": str(f), "creata": nuova}


def cmd_punteggio(args) -> dict:
    f = Path(args.verdetto)
    if not f.is_file():
        raise ErroreInput(f"file non trovato: {f}")
    try:
        dati = json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ErroreInput(f"verdetto.json non è un JSON valido: {e}") from e
    if not isinstance(dati, dict):
        raise ErroreInput("verdetto.json non è un JSON valido: atteso un oggetto")
    catalogo = carica_catalogo()
    r = calcola(dati, catalogo)
    testo_md = genera_md(r, catalogo)  # prima il resoconto: se fallisce, il JSON resta intatto
    md = f.parent / "resoconto.md"
    md.write_bytes(testo_md.encode("utf-8"))
    _scrivi_json(f, r)
    return {"verdetto": r["verdetto"], "fiducia_nel_bot": FIDUCIA_NEL_BOT[r["verdetto"]],
            "certezza_valutazione": r["fiducia"],
            "rischio_finale": r["rischio_finale"], "punteggio_totale": r["punteggio_totale"],
            "linee_rosse": [l["codice"] for l in r["linee_rosse"]], "resoconto": str(md)}


def costruisci_parser() -> argparse.ArgumentParser:
    p = _Parser(prog="controlli.py", description="Kit /verifica-bot")
    p.add_argument("--radice", default=str(KIT), help="cartella che contiene verifiche/")
    sub = p.add_subparsers(dest="comando", required=True)
    s = sub.add_parser("nome"); s.add_argument("username")
    s = sub.add_parser("anteprima"); s.add_argument("username"); s.add_argument("--cartella", required=True)
    s = sub.add_parser("dominio"); s.add_argument("url")
    s = sub.add_parser("pagina"); s.add_argument("url"); s.add_argument("--cartella", required=True)
    s = sub.add_parser("file"); s.add_argument("percorso")
    s = sub.add_parser("punteggio"); s.add_argument("verdetto")
    s = sub.add_parser("nuova"); s.add_argument("username")
    return p


def main(argv: list[str] | None = None) -> int:
    for flusso in (sys.stdout, sys.stderr):
        try:
            flusso.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    try:
        args = costruisci_parser().parse_args(argv)
        _controlla_kit()
        if args.comando == "nome":
            out = analizza_nome(_username_valido(args.username))
        elif args.comando in ("anteprima", "dominio", "pagina"):
            try:
                if args.comando == "anteprima":
                    out = rete.anteprima(args.username, Path(args.cartella))
                elif args.comando == "dominio":
                    out = rete.dominio(args.url)
                else:
                    out = rete.analizza_pagina(args.url, Path(args.cartella))
            except Exception as e:  # rete: un imprevisto non deve fermare la verifica
                out = {"esito": "non_verificato", "motivo": f"errore imprevisto: {type(e).__name__}: {e}"}
        elif args.comando == "file":
            if not Path(args.percorso).is_file():
                raise ErroreInput(f"file non trovato: {args.percorso}")
            out = analizza_file(Path(args.percorso))
        elif args.comando == "punteggio":
            out = cmd_punteggio(args)
        else:
            out = cmd_nuova(args)
    except (ErroreInput, ErroreVerdetto) as e:
        sys.stderr.write(f"Errore: {e}\n")
        return 1
    _stampa(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
