"""Resoconto Markdown generato da verdetto.json (già passato da punteggio.calcola)."""
import re
from datetime import datetime
from urllib.parse import urlparse

from punteggio import carica_catalogo

SEMAFORO = {
    "verde": ("🟢", "Nessun segnale di rischio trovato"),
    "giallo": ("🟡", "Attenzione"),
    "rosso": ("🔴", "Da evitare"),
}
# Solo etichetta: la fiducia nel bot segue il colore del semaforo (il calcolo non cambia).
FIDUCIA_NEL_BOT = {"verde": "alta", "giallo": "media", "rosso": "bassa"}
NOMI_AREE = {"identita": "Identità", "promesse": "Promesse", "richieste": "Richieste",
             "tecnica": "Tecnica", "reputazione": "Reputazione", "trasparenza": "Trasparenza"}
NOTA_FINALE = ("_Valutazione basata su segnali pubblici e sul materiale fornito: non è un accertamento. "
               "Un verde significa che non sono emersi segnali di rischio, non che il servizio è "
               "garantito._")


# Stesso elenco di app/sicurezza.js (un test li tiene allineati). Tutto il resto, t.me compreso,
# nel resoconto diventa testo non cliccabile: chi rilegge non deve poter aprire per sbaglio un sito truffa.
FONTI_AFFIDABILI = ["telegram.org", "consob.it", "bancaditalia.it", "bitget.com", "crypto.news",
                    "dev.to", "linkedin.com", "github.com", "blockworks.co", "cointelegraph.com",
                    "binance.com", "kaspersky.com"]
_URL = re.compile(r"(?i)(?<![\w.@/])(?:https?://|www\.)[^\s<>`|\[\]()]+")


def _dominio_base(host: str) -> str:
    parti = [x for x in host.lower().rstrip(".").split(".") if x]
    if parti and parti[0] == "www":
        parti = parti[1:]
    return ".".join(parti[-2:])


def _affidabile(url: str) -> bool:
    try:
        u = urlparse(url.strip())
        host = u.hostname
    except ValueError:
        return False
    return (u.scheme == "https" and not u.username and not u.password and bool(host)
            and _dominio_base(host) in FONTI_AFFIDABILI)


def _disinnescato(url: str) -> str:
    """hxxps://… dentro uno span di codice: leggibile, copiabile a mano, mai cliccabile."""
    s = url.replace("`", "")
    s = re.sub(r"(?i)^http(s?):", r"hxxp\1:", s)
    s = re.sub(r"(?i)^www\.", "www[.]", s)
    return f"`{s}`"


def _scappa(s: str) -> str:
    """Neutralizza la sintassi Markdown/HTML che potrebbe creare link: [..](..) e <..>."""
    return (s.replace("`", "'").replace("[", r"\[").replace("]", r"\]")
            .replace("<", "&lt;").replace(">", "&gt;"))


def _testo_sicuro(testo) -> str:
    """Testo libero (anche copiato dal bot): niente link Markdown/HTML attivi, URL disinnescati."""
    s, pezzi, ultimo = str(testo), [], 0
    for m in _URL.finditer(s):
        url = m.group(0).rstrip(".,;:!?")
        pezzi.append(_scappa(s[ultimo:m.start()]))
        pezzi.append(url if _affidabile(url) else _disinnescato(url))
        ultimo = m.start() + len(url)
    pezzi.append(_scappa(s[ultimo:]))
    return "".join(pezzi)


def _link_fonte(titolo, url) -> str:
    url = str(url or "")
    etichetta = _testo_sicuro(titolo) if titolo else ""
    if url and _affidabile(url):
        return f"[{etichetta or url}]({url})"
    return f"{etichetta} {_disinnescato(url)}".strip() if url else etichetta


def _data(iso: str | None) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return datetime.now().strftime("%d/%m/%Y")


def _misura_rischio(verdetto: dict) -> str:
    """Rischio finale (sempre nella zona del colore); se una regola prevale sulla media, lo dice."""
    media = verdetto.get("punteggio_totale", "?")
    finale = verdetto.get("rischio_finale", media)
    testo = f"rischio **{finale}/100**"
    if finale == media:
        return testo
    if verdetto.get("linee_rosse"):
        motivo = "linea rossa superata"
    elif verdetto.get("rosso_da_segnalazioni"):
        motivo = "segnalazioni concordi da più fonti"
    else:
        motivo = "regola di prudenza"
    return f"{testo} ({motivo}; media delle aree {media}/100)"


def _elenco(voci, gia_sicure: bool = False) -> list[str]:
    if not voci:
        return ["- (nessuna voce)"]
    return [f"- {v if gia_sicure else _testo_sicuro(v)}" for v in voci]


def _cella(testo: str) -> str:
    return " ".join(str(testo).split()).replace("|", "/")


def genera_md(verdetto: dict, catalogo: dict | None = None) -> str:
    catalogo = catalogo or carica_catalogo()
    bot = verdetto.get("bot", {})
    emoji, etichetta = SEMAFORO.get(verdetto.get("verdetto"), ("⚪", "Non calcolato"))
    righe = [f"# Verifica @{bot.get('username', '?')} — {_data(verdetto.get('data'))}", "",
             f"**{emoji} {etichetta}** · fiducia nel bot "
             f"**{FIDUCIA_NEL_BOT.get(verdetto.get('verdetto'), '?')}** · "
             + _misura_rischio(verdetto),
             "",
             f"_Quante prove c'erano per giudicare:_ certezza della valutazione "
             f"**{verdetto.get('fiducia', '?')}**"]
    if bot.get("tipo"):
        righe.append(f"Tipo di servizio: {_testo_sicuro(bot['tipo'])}")
    if verdetto.get("rosso_da_segnalazioni"):
        righe += ["", "> Segnalato da terzi, non verificato direttamente."]

    if verdetto.get("linee_rosse"):
        righe += ["", "## Linee rosse", ""]
        for lr in verdetto["linee_rosse"]:
            desc = catalogo.get(lr["codice"], {}).get("descrizione", lr["codice"])
            prova = f" — {_testo_sicuro(lr['prova'])}" if lr.get("prova") else ""
            righe.append(f"- **{desc}**{prova}")

    righe += ["", "## Le sei aree", "", "| Area | Rischio | Segnali principali |", "|---|---|---|"]
    for chiave, nome in NOMI_AREE.items():
        area = verdetto.get("aree", {}).get(chiave, {})
        segnali = area.get("segnali", [])
        testi = []
        for s in segnali[:3]:
            t = s.get("testo") or catalogo.get(s.get("codice"), {}).get("descrizione", "")
            if s.get("tipo_prova") == "segnalazione":
                t += " (segnalazione di terzi)"
            if s.get("fuori_catalogo"):
                t += " (fuori catalogo)"
            testi.append(_cella(_testo_sicuro(t)))
        righe.append(f"| {nome} | {area.get('rischio', 0)} | {'; '.join(testi) or '—'} |")

    righe += ["", "## Cosa puoi fare", "", *_elenco(verdetto.get("cosa_fare"))]
    righe += ["", "## Cosa NON fare", "", *_elenco(verdetto.get("cosa_non_fare"))]
    righe += ["", "## Cosa non ho potuto verificare", "", *_elenco(verdetto.get("non_verificato"))]
    fonti = [f"{_link_fonte(f.get('titolo'), f.get('url'))} — consultata {f.get('consultata', '?')}"
             for f in verdetto.get("fonti", [])]
    righe += ["", "## Fonti", "", *_elenco(fonti, gia_sicure=True), "", "---", "", NOTA_FINALE, ""]
    return "\n".join(righe)
