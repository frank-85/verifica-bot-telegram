"""Analisi dello username di un bot: imitazione di marchi e parole esca."""
import re
from pathlib import Path

KIT = Path(__file__).resolve().parent
PAROLE_ESCA = ["official", "support", "app", "web", "airdrop", "claim", "bonus", "gift", "free",
               "verify", "safeguard", "help", "admin", "reward", "profit", "invest"]
OMOGLIFI = [("rn", "m"), ("vv", "w"), ("0", "o"), ("3", "e"), ("4", "a"), ("5", "s"), ("7", "t")]
MIN_LUNGO = 5   # marchi da almeno 5 lettere: anche varianti con una lettera di differenza
MIN_SOTTOSTRINGA = 4  # marchi più corti: solo come parola separata


TME = r"^(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me|telegram\.dog)/"


def e_link_invito(testo: str) -> bool:
    """Link d'invito a un gruppo o canale (t.me/+…, t.me/joinchat/…, tg://join): non indica un bot."""
    t = testo.strip()
    return bool(re.match(TME + r"(?:\+|joinchat/)", t, re.I) or re.match(r"^tg://join\b", t, re.I))


def normalizza_username(testo: str) -> str:
    """Username da @nome o da qualsiasi link Telegram. "" se il link non indica un bot."""
    t = testo.strip()
    if re.match(r"^tg://", t, re.I):  # tg://resolve?domain=Nome&start=…
        m = re.match(r"^tg://resolve\?(?:.*&)?domain=([^&#\s]*)", t, re.I)
        return m.group(1).lstrip("@").strip() if m else ""
    web = re.match(r"^(?:https?://)?(?:www\.)?web\.telegram\.org(?:/[a-z])?/?(#.*)?$", t, re.I)
    if web:  # web.telegram.org/k/#@Nome · /a/#Nome · #-100… (id numerico di una chat: non risolvibile)
        nome = (web.group(1) or "#")[1:].lstrip("@").split("?")[0].strip()
        return "" if not nome or nome.lstrip("-").isdigit() else nome
    if e_link_invito(t):
        return ""
    link = re.match(TME, t, re.I)
    t = re.sub(r"^https?://", "", t, flags=re.I)
    t = re.sub(r"^(www\.)?(t\.me|telegram\.me|telegram\.dog)/", "", t, flags=re.I)
    if link and re.match(r"^s(/|$)", t, re.I):  # t.me/s/Nome = anteprima web della stessa pagina
        t = t[2:]
    t = t.split("?")[0].split("#")[0].strip("/")
    t = t.split("/")[0]
    return t.lstrip("@").strip()


def carica_marchi(percorso: Path | None = None) -> list[tuple[str, set[str], bool]]:
    """Righe "marchio|ufficiale1,ufficiale2|generico": il terzo campo è facoltativo."""
    percorso = percorso or KIT / "marchi.txt"
    marchi = []
    for riga in Path(percorso).read_text(encoding="utf-8").splitlines():
        riga = riga.split("#")[0].strip()
        if not riga:
            continue
        campi = riga.split("|")
        ufficiali = {u.strip().lower() for u in (campi[1] if len(campi) > 1 else "").split(",") if u.strip()}
        generico = len(campi) > 2 and campi[2].strip().lower() == "generico"
        marchi.append((campi[0].strip().lower(), ufficiali, generico))
    return marchi


def _parole(username: str) -> list[str]:
    pezzi = re.split(r"[_\W]+", username)
    parole = []
    for p in pezzi:
        parole += re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z0-9]+", p)
    return [p.lower() for p in parole if p]


def _compatto(username: str) -> str:
    t = username.lower().replace("_", "")
    return t[:-3] if t.endswith("bot") and len(t) > 3 else t


def _candidati(compatto: str) -> set[str]:
    t = compatto
    for a, b in OMOGLIFI:
        t = t.replace(a, b)
    return {t.replace("1", "l"), t.replace("1", "i")}


def _levenshtein(a: str, b: str) -> int:
    prec = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prec[j] + 1, cur[j - 1] + 1, prec[j - 1] + (ca != cb)))
        prec = cur
    return prec[-1]


def _contiene(marchio: str, candidato: str) -> str | None:
    pos = candidato.find(marchio)
    if pos < 0:
        return None
    prima = candidato[pos - 1] + "+" if pos > 0 else ""
    fine = pos + len(marchio)
    dopo = "+" + candidato[fine] if fine < len(candidato) else ""
    return prima + marchio + dopo


def _variante(marchio: str, candidato: str) -> str | None:
    n = len(marchio)
    for lung, tipo in ((n - 1, "lettera mancante"), (n + 1, "lettera aggiunta"),
                       (n, "lettera sostituita")):
        for i in range(0, len(candidato) - lung + 1):
            finestra = candidato[i:i + lung]
            if finestra != marchio and _levenshtein(finestra, marchio) == 1:
                return tipo
    return None


def _composto(candidato: str, marchio: str, varianti: bool) -> str | None:
    """Il candidato è fatto SOLO di marchio + parole esca + cifre? ("okxofficial", "walletsupport")

    Serve per i marchi corti (attaccati ad altre parole sarebbero ovunque) e per i marchi
    generici come "wallet" (parola comune: conta solo se il nome non dice altro).
    Ritorna "contiene", "variante" (marchio con una lettera di differenza) oppure None.
    """
    n = len(marchio)
    memo: dict[int, str | None] = {}

    def da(i: int) -> str | None:  # miglior esito per candidato[i:], "" = finito senza marchio
        if i == len(candidato):
            return ""
        if i in memo:
            return memo[i]
        esiti = []
        if candidato.startswith(marchio, i):
            resto = da(i + n)
            if resto is not None:
                esiti.append("contiene")
        if varianti:
            for lung in (n - 1, n, n + 1):
                finestra = candidato[i:i + lung]
                if len(finestra) == lung and finestra != marchio and _levenshtein(finestra, marchio) == 1:
                    resto = da(i + lung)
                    if resto is not None:
                        esiti.append(resto or "variante")
        for p in PAROLE_ESCA:
            if candidato.startswith(p, i):
                resto = da(i + len(p))
                if resto is not None:
                    esiti.append(resto)
        cifre = re.match(r"\d+", candidato[i:])
        if cifre:
            resto = da(i + len(cifre.group()))
            if resto is not None:
                esiti.append(resto)
        memo[i] = ("contiene" if "contiene" in esiti else "variante" if "variante" in esiti
                   else "" if "" in esiti else None)
        return memo[i]

    return da(0) or None


def analizza_nome(username: str, marchi_path: Path | None = None) -> dict:
    username = normalizza_username(username)
    parole = _parole(username)
    compatto = _compatto(username)
    candidati = _candidati(compatto)
    imitazioni = []
    ufficiale = False
    for marchio, ufficiali, generico in carica_marchi(marchi_path):
        if username.lower() in ufficiali:
            ufficiale = True
            continue
        if len(marchio) < MIN_SOTTOSTRINGA and (marchio in parole or compatto == marchio):
            imitazioni.append({"marchio": marchio, "tipo": "contiene", "dettaglio": marchio})
            continue
        if generico or len(marchio) < MIN_SOTTOSTRINGA:
            varianti = generico and len(marchio) >= MIN_LUNGO
            esiti = {c: _composto(c, marchio, varianti) for c in sorted(candidati)}
            for c in sorted(candidati):
                if esiti[c] == "contiene":
                    imitazioni.append({"marchio": marchio, "tipo": "contiene",
                                       "dettaglio": _contiene(marchio, c)})
                    break
            else:
                for c in sorted(candidati):
                    if esiti[c] == "variante":
                        imitazioni.append({"marchio": marchio, "tipo": "variante",
                                           "dettaglio": _variante(marchio, c)})
                        break
            continue
        trovato = None
        for c in sorted(candidati):
            det = _contiene(marchio, c)
            if det:
                trovato = {"marchio": marchio, "tipo": "contiene", "dettaglio": det}
                break
        if not trovato and len(marchio) >= MIN_LUNGO:
            for c in sorted(candidati):
                tipo = _variante(marchio, c)
                if tipo:
                    trovato = {"marchio": marchio, "tipo": "variante", "dettaglio": tipo}
                    break
        if trovato:
            imitazioni.append(trovato)
    if len(parole) > 1:
        esca = [p for p in PAROLE_ESCA if p in parole]
    else:
        esca = [p for p in PAROLE_ESCA if len(p) >= 4 and p in compatto]
    return {"username": username, "imitazioni": imitazioni, "ufficiale": ufficiale,
            "parole_esca": esca}
