"""Analisi statica (senza esecuzione) di HTML e JavaScript di una pagina o Mini App."""
import re
from urllib.parse import urljoin, urlparse

_I = re.I | re.S
SEED = re.compile(r"seed[\s_-]*phrase|mnemonic|recovery[\s_-]*phrase|secret[\s_-]*phrase|"
                  r"frase\s+di\s+recupero|private[\s_-]*key|chiave\s+privata|"
                  r"\b(12|24)\s*(words|parole)\b|login[\s_-]*code|codice\s+di\s+accesso", _I)
RACCOLTA = re.compile(r"<input|<textarea|\bfetch\s*\(|XMLHttpRequest|sendBeacon", _I)
APPUNTI = re.compile(r"clipboard\s*\.\s*writeText|execCommand\s*\(\s*['\"]copy", _I)
COMANDO = re.compile(r"powershell|mshta|cmd(\.exe)?\s*/c|\biex\b|win\s*\+\s*r|windows\s*\+\s*r", _I)
OFFUSCATO = re.compile(r"eval\s*\(\s*atob\s*\(|eval\s*\(\s*function\s*\(\s*p\s*,\s*a\s*,\s*c\s*,"
                       r"\s*k\s*,\s*e|[A-Za-z0-9+/=]{2000,}|(?:\\x[0-9a-f]{2}){500,}", _I)
WALLET = re.compile(r"tonconnect|walletconnect|window\s*\.\s*ethereum", _I)
INVIO = re.compile(r"(?:fetch\s*\(|\.open\s*\(\s*['\"](?:POST|GET)['\"]\s*,|sendBeacon\s*\()"
                   r"\s*['\"](https?://[^'\"\s]+)", _I)
SCRIPT_SRC = re.compile(r"<script[^>]*\bsrc\s*=\s*['\"]([^'\"]+)['\"]", _I)
ARG_APPUNTI = re.compile(r"writeText\s*\(\s*(['\"`])(.{0,500}?)\1", _I)
DATA_URI = re.compile(r"data:[\w/+.-]{1,100}(;[\w=-]+)*;base64,[A-Za-z0-9+/=]+", re.I)
MAX_PROVA = 120
VICINANZA = 300  # caratteri: le due parti di un segnale devono stare vicine


def _vicino(testo: str, m: re.Match, schema: re.Pattern) -> bool:
    finestra = testo[max(0, m.start() - VICINANZA):m.end() + VICINANZA]
    return bool(schema.search(finestra))


def _prova(testo: str, m: re.Match) -> str:
    inizio = max(0, m.start() - 30)
    estratto = " ".join(testo[inizio:m.end() + 60].split())
    return estratto[:MAX_PROVA]


def _host(url: str) -> str:
    h = (urlparse(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def analizza_testo(testo: str, url_base: str | None = None) -> list[dict]:
    segnali = []

    def aggiungi(codice, m, sorgente=testo):
        if codice not in {s["codice"] for s in segnali}:
            segnali.append({"codice": codice, "prova": _prova(sorgente, m)})

    for m in SEED.finditer(testo):
        if _vicino(testo, m, RACCOLTA):
            aggiungi("pagina_seed_phrase", m)
            break
    for m in ARG_APPUNTI.finditer(testo):
        if COMANDO.search(m.group(2)):
            aggiungi("pagina_clickfix", m)
            break
    for m in APPUNTI.finditer(testo):
        if _vicino(testo, m, COMANDO):
            aggiungi("pagina_clickfix", m)
            break
    senza_immagini = DATA_URI.sub("data:", testo)
    m = OFFUSCATO.search(senza_immagini)
    if m:
        aggiungi("pagina_offuscata", m, senza_immagini)
    if url_base:
        base = _host(url_base)
        for m in INVIO.finditer(testo):
            if _host(m.group(1)) and _host(m.group(1)) != base:
                aggiungi("pagina_invio_dati_esterno", m)
                break
    m = WALLET.search(testo)
    if m:
        aggiungi("wallet_lib_presente", m)
    return segnali


def script_esterni(html: str, url_base: str) -> dict:
    base = _host(url_base)
    stessa, esterni = [], []
    for src in SCRIPT_SRC.findall(html):
        url = urljoin(url_base, src)
        if urlparse(url).scheme not in ("http", "https"):
            continue
        h = _host(url)
        if h == base:
            if url not in stessa:
                stessa.append(url)
        elif h and h not in esterni:
            esterni.append(h)
    return {"stessa_origine": stessa, "esterni": esterni}
