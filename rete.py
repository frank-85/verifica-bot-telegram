"""Controlli di rete in sicurezza: download statico, anteprima t.me, RDAP dei domini.

Niente esecuzione di contenuti, niente cookie, niente indirizzi locali.
L'analisi avviene in memoria; il salvataggio su disco è facoltativo perché
l'antivirus può (giustamente) bloccarlo.
"""
import html as html_mod
import http.client
import ipaddress
import json
import re
import socket
import unicodedata
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

from nome import analizza_nome, carica_marchi, normalizza_username
from pagina import analizza_testo, script_esterni

USER_AGENT = "Mozilla/5.0 (compatible; verifica-bot/1.0)"
TIMEOUT = 15
MAX_BYTE = 2_000_000
MAX_SCRIPT = 10
GIOVANE_GIORNI = 90
SECONDO_LIVELLO = {"co", "com", "org", "net", "gov", "ac"}
TIPI_TESTO = ("text/", "application/javascript", "application/x-javascript",
              "application/xhtml", "application/json", "application/ecmascript")


MAX_REDIRECT = 5
ERRORI_RETE = (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError, ValueError)


def _host_vietato(host: str) -> bool:
    if not host or host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return not ip.is_global


class _RedirectSicuro(urllib.request.HTTPRedirectHandler):
    """Ogni redirect viene ricontrollato: solo http/https, mai indirizzi locali."""
    max_redirections = MAX_REDIRECT

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        p = urlparse(newurl)
        if p.scheme not in ("http", "https") or _host_vietato((p.hostname or "").lower()):
            raise urllib.error.URLError(f"redirect rifiutato verso {p.scheme}://{p.hostname or '?'}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _apri(url: str):
    opener = urllib.request.OpenerDirector()
    for h in (urllib.request.HTTPHandler(), urllib.request.HTTPSHandler(), _RedirectSicuro(),
              urllib.request.HTTPDefaultErrorHandler(), urllib.request.HTTPErrorProcessor(),
              urllib.request.UnknownHandler()):
        opener.add_handler(h)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return opener.open(req, timeout=TIMEOUT)


def _non_verificato(motivo: str, **extra) -> dict:
    return {"esito": "non_verificato", "motivo": motivo, **extra}


def scarica(url: str, cartella: Path, nome_file: str) -> dict:
    """Scarica al massimo MAX_BYTE. Il campo 'dati' (bytes) serve all'analisi in memoria."""
    try:
        p = urlparse(url)
        host = (p.hostname or "").lower()
    except ValueError as e:
        return _non_verificato(f"indirizzo non valido: {e}")
    if p.scheme not in ("http", "https"):
        return _non_verificato(f"schema non ammesso: {p.scheme or '?'}")
    if _host_vietato(host):
        return _non_verificato(f"indirizzo locale o non valido: {host or '?'}")
    try:
        with _apri(url) as risp:
            dati = risp.read(MAX_BYTE + 1)
            tipo = risp.headers.get_content_type() if risp.headers else "application/octet-stream"
    except urllib.error.HTTPError as e:
        return _non_verificato(f"HTTP {e.code}")
    except ERRORI_RETE as e:
        return _non_verificato(f"rete: {type(e).__name__}: {e}")
    troncato = len(dati) > MAX_BYTE
    dati = dati[:MAX_BYTE]
    percorso = Path(cartella) / nome_file
    salvato = True
    try:
        Path(cartella).mkdir(parents=True, exist_ok=True)
        percorso.write_bytes(dati)
    except OSError:
        salvato = False
    return {"esito": "ok", "url": url, "percorso": str(percorso), "salvato": salvato,
            "tipo": tipo, "byte": len(dati), "troncato": troncato, "dati": dati}


def _testo(frammento: str) -> str:
    frammento = re.sub(r"<br\s*/?>", "\n", frammento, flags=re.I)
    frammento = re.sub(r"<[^>]+>", "", frammento)
    return html_mod.unescape(frammento).strip()


def _meta(html: str, prop: str) -> str:
    m = re.search(r'<meta property="' + re.escape(prop) + r'" content="([^"]*)"', html)
    return html_mod.unescape(m.group(1)) if m else ""


def leggi_anteprima(html: str) -> dict:
    blocco = re.search(r'<div class="tgme_page_title"[^>]*>(.*?)</div>', html, re.S)
    blocco = blocco.group(1) if blocco else ""
    span = re.search(r'<span dir="auto">(.*?)</span>', blocco, re.S)
    titolo = _testo(span.group(1)) if span else (_meta(html, "og:title") or "")
    desc = re.search(r'<div class="tgme_page_description[^"]*">(.*?)</div>', html, re.S)
    descrizione = _testo(desc.group(1)) if desc else _meta(html, "og:description")
    utenti = re.search(r">\s*([\d][\d\s .,]*)\s+monthly users", html)
    normalizzato = unicodedata.normalize("NFKC", titolo)
    return {
        "titolo": titolo,
        "titolo_normalizzato": normalizzato,
        "caratteri_decorativi": normalizzato != titolo,
        "descrizione": descrizione,
        "utenti_mensili": int(re.sub(r"\D", "", utenti.group(1))) if utenti else None,
        "scam": bool(re.search(r'class="[^"]*scam|>\s*SCAM\s*<', blocco, re.I)),
        "fake": bool(re.search(r'class="[^"]*fake|>\s*FAKE\s*<', blocco, re.I)),
        "verificato": "verified-icon" in blocco,
    }


def anteprima(username: str, cartella: Path) -> dict:
    u = normalizza_username(username)
    r = scarica(f"https://t.me/{u}", cartella, "anteprima_tme.html")
    if r["esito"] != "ok":
        return r
    dati = leggi_anteprima(r["dati"].decode("utf-8", "replace"))
    dati["esiste"] = bool(dati["titolo"]) and "tgme_action_button" in r["dati"].decode("utf-8", "replace")
    return {"esito": "ok", "username": u, **dati}


def leggi_rdap(dati: dict, oggi: date) -> dict:
    creato = None
    for ev in dati.get("events", []) or []:
        if ev.get("eventAction") == "registration" and ev.get("eventDate"):
            try:
                creato = datetime.fromisoformat(ev["eventDate"].replace("Z", "+00:00")).date()
            except ValueError:
                pass
            break
    registrar = None
    for ent in dati.get("entities", []) or []:
        if "registrar" in (ent.get("roles") or []):
            for campo in (ent.get("vcardArray") or [None, []])[1]:
                if campo and campo[0] == "fn":
                    registrar = campo[3]
    eta = (oggi - creato).days if creato else None
    return {"creato": creato.isoformat() if creato else None, "eta_giorni": eta,
            "registrar": registrar, "giovane": eta is not None and eta < GIOVANE_GIORNI}


def dominio_registrabile(host: str) -> str:
    parti = [p for p in host.lower().strip(".").split(".") if p]
    if parti and parti[0] == "www":
        parti = parti[1:]
    if len(parti) >= 3 and parti[-2] in SECONDO_LIVELLO and len(parti[-1]) == 2:
        return ".".join(parti[-3:])
    return ".".join(parti[-2:])


def _e_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


def marchi_nel_host(host: str) -> list[dict]:
    """Marchi imitati in TUTTO l'indirizzo, sottodomini compresi ("binance.sito-falso.xyz").

    Escluso il sito ufficiale: se il nome registrato coincide con il marchio (binance.com),
    né lui né i suoi sottodomini contano. Nei sottodomini i marchi generici ("wallet") non
    contano: "wallet.negozio.it" è un nome comune.
    """
    host = host.lower().strip(".")
    if not host or _e_ip(host):
        return []
    reg = dominio_registrabile(host)
    etichetta = reg.split(".")[0]
    piatta = etichetta.replace("-", "")
    marchi = carica_marchi()
    if piatta in {m for m, _, _ in marchi}:
        return []
    generici = {m for m, _, g in marchi if g}
    sotto = [x for x in host[:-len(reg)].strip(".").split(".") if x and x != "www"] if host != reg else []
    trovati, visti = [], set()
    for parte, e_sotto in [(etichetta, False)] + [(s, True) for s in sotto]:
        for i in analizza_nome(parte)["imitazioni"]:
            if i["marchio"] in visti or (e_sotto and i["marchio"] in generici):
                continue
            visti.add(i["marchio"])
            trovati.append({**i, "parte": parte})
    return trovati


def dominio(url_o_dominio: str, oggi: date | None = None) -> dict:
    oggi = oggi or date.today()
    testo = url_o_dominio.strip()
    try:
        host = urlparse(testo).hostname if "://" in testo else testo.split("/")[0].split(":")[0]
    except ValueError as e:
        return _non_verificato(f"indirizzo non valido: {e}", dominio=None, risolve=False)
    host = (host or "").lower()
    if _e_ip(host):  # un IP non ha registrazione di dominio: non lo mandiamo a RDAP
        return _non_verificato("indirizzo IP numerico al posto di un nome di dominio: "
                               "nessuna registrazione da controllare", dominio=None, host=host,
                               risolve=True, ip_diretto=True, contiene_marchio=[])
    dom = dominio_registrabile(host)
    try:
        socket.getaddrinfo(host, None)
        risolve = True
    except (OSError, ValueError):
        risolve = False
    base = {"dominio": dom, "host": host, "risolve": risolve,
            "contiene_marchio": marchi_nel_host(host)}
    if _host_vietato(host):
        return _non_verificato("indirizzo locale", **base)
    try:
        with _apri(f"https://rdap.org/domain/{dom}") as risp:
            dati = json.loads(risp.read(MAX_BYTE).decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return _non_verificato(f"RDAP HTTP {e.code}", **base)
    except ERRORI_RETE as e:
        return _non_verificato(f"RDAP: {type(e).__name__}", **base)
    return {"esito": "ok", **base, **leggi_rdap(dati, oggi)}


def _e_testo(tipo: str) -> bool:
    return tipo.startswith(TIPI_TESTO)


def analizza_pagina(url: str, cartella: Path) -> dict:
    r = scarica(url, cartella, "pagina.html")
    vuoto = {"segnali": [], "script_esterni": [], "contenuto_non_html": False,
             "bloccato_antivirus": False}
    if r["esito"] != "ok":
        return {**r, **vuoto}
    out = {"esito": "ok", "url": url, **vuoto, "bloccato_antivirus": not r["salvato"],
           "troncato": r["troncato"]}
    if not _e_testo(r["tipo"]):
        out["contenuto_non_html"] = True
        return out
    testo = r["dati"].decode("utf-8", "replace")
    segnali = analizza_testo(testo, url)
    scr = script_esterni(testo, url)
    for i, s_url in enumerate(scr["stessa_origine"][:MAX_SCRIPT]):
        rs = scarica(s_url, cartella, f"script_{i + 1}.js")
        if rs["esito"] != "ok":
            continue
        if not rs["salvato"]:
            out["bloccato_antivirus"] = True
        for s in analizza_testo(rs["dati"].decode("utf-8", "replace"), url):
            if s["codice"] not in {x["codice"] for x in segnali}:
                segnali.append(s)
    if scr["esterni"]:
        segnali.append({"codice": "pagina_script_esterni",
                        "prova": ("script da: " + ", ".join(scr["esterni"]))[:120]})
    out["segnali"] = segnali
    out["script_esterni"] = scr["esterni"]
    return out
