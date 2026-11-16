"""Calcolo deterministico di rischio per area, punteggio, fiducia e verdetto."""
import copy
import json
from pathlib import Path
from urllib.parse import urlparse

KIT = Path(__file__).resolve().parent
PESI = {"identita": 2, "promesse": 1, "richieste": 2, "tecnica": 2, "reputazione": 1, "trasparenza": 1}
SOGLIA_VERDE = 30
SOGLIA_GIALLO = 60


class ErroreVerdetto(ValueError):
    pass


def carica_catalogo(percorso: Path | None = None) -> dict[str, dict]:
    percorso = percorso or KIT / "segnali.json"
    voci = json.loads(Path(percorso).read_text(encoding="utf-8"))
    return {v["codice"]: v for v in voci}


def _dominio(fonte: str) -> str:
    host = urlparse(fonte).hostname or fonte
    host = host.lower()
    return host[4:] if host.startswith("www.") else host


def _dominio_base(fonte: str) -> str:
    parti = _dominio(fonte).split(".")
    return ".".join(parti[-2:]) if len(parti) >= 2 else parti[0]


PUNTI_FUORI_CATALOGO = (-50, 100)
SOGLIA_AREA_PIENA = 80  # un'area a questo rischio o più impedisce il verde
MIN_FONTI_UFFICIALE = 2  # bot con spunta ufficiale: fonti indipendenti per fiducia almeno media


def _punti(segnale: dict, catalogo: dict, area: str) -> float:
    codice = segnale.get("codice", "")
    if segnale.get("fuori_catalogo"):
        if codice in catalogo:
            raise ErroreVerdetto(f"'{codice}' è nel catalogo: non marcarlo fuori_catalogo")
        punti = segnale.get("punti")
        if isinstance(punti, bool) or not isinstance(punti, (int, float)):
            raise ErroreVerdetto(f"il segnale fuori catalogo '{codice}' non ha 'punti' numerici")
        return max(PUNTI_FUORI_CATALOGO[0], min(PUNTI_FUORI_CATALOGO[1], punti))
    if codice not in catalogo:
        raise ErroreVerdetto(f"codice '{codice}' non presente in segnali.json "
                             "(usa un codice del catalogo o marca fuori_catalogo con punti)")
    if catalogo[codice]["area"] != area:
        raise ErroreVerdetto(f"'{codice}' va nell'area '{catalogo[codice]['area']}', non in '{area}'")
    return catalogo[codice]["punti"]


def valida(verdetto) -> None:
    """Controlla la forma di verdetto.json; solleva ErroreVerdetto con un messaggio in italiano."""
    if not isinstance(verdetto, dict):
        raise ErroreVerdetto("verdetto.json deve essere un oggetto")
    if not isinstance(verdetto.get("bot", {}), dict):
        raise ErroreVerdetto("'bot' deve essere un oggetto con 'username'")
    aree = verdetto.get("aree")
    if not isinstance(aree, dict):
        raise ErroreVerdetto("manca il campo 'aree' (oggetto con le sei aree)")
    sconosciute = [a for a in aree if a not in PESI]
    if sconosciute:
        raise ErroreVerdetto(f"area sconosciuta {sconosciute} (usa: {', '.join(PESI)})")
    for nome, area in aree.items():
        if not isinstance(area, dict) or not isinstance(area.get("segnali", []), list):
            raise ErroreVerdetto(f"l'area '{nome}' deve avere 'segnali' come elenco")
        for seg in area.get("segnali", []):
            if not isinstance(seg, dict) or not isinstance(seg.get("codice"), str):
                raise ErroreVerdetto(f"in '{nome}' c'è un segnale non valido: {str(seg)[:60]}")
            if seg.get("tipo_prova") not in ("diretta", "segnalazione"):
                raise ErroreVerdetto(f"'{seg['codice']}': tipo_prova deve essere 'diretta' o 'segnalazione'")
    ctx = verdetto.get("contesto", {})
    if not isinstance(ctx, dict):
        raise ErroreVerdetto("'contesto' deve essere un oggetto")
    for chiave in ("materiale_utente", "tecnica_completa"):
        if not isinstance(ctx.get(chiave, False), bool):
            raise ErroreVerdetto(f"contesto.{chiave} deve essere true o false (senza virgolette)")
    fonti = ctx.get("fonti_indipendenti", 0)
    if isinstance(fonti, bool) or not isinstance(fonti, int) or fonti < 0:
        raise ErroreVerdetto("contesto.fonti_indipendenti deve essere un numero intero")
    for chiave in ("cosa_fare", "cosa_non_fare", "non_verificato", "fonti"):
        if not isinstance(verdetto.get(chiave, []), list):
            raise ErroreVerdetto(f"'{chiave}' deve essere un elenco")


def calcola(verdetto: dict, catalogo: dict) -> dict:
    valida(verdetto)
    r = copy.deepcopy(verdetto)
    aree = r["aree"]
    linee_rosse = []
    fonti_segnalazioni = set()
    ufficiale = False
    somma = 0.0
    for area, peso in PESI.items():
        dati = aree.setdefault(area, {"rischio": 0, "segnali": []})
        totale_area = 0.0
        for seg in dati.get("segnali", []):
            totale_area += _punti(seg, catalogo, area)
            voce = catalogo.get(seg.get("codice"))
            diretta = seg.get("tipo_prova") == "diretta"
            if voce and voce["linea_rossa"] and not seg.get("fuori_catalogo") and diretta:
                linee_rosse.append({"codice": seg["codice"], "tipo_prova": "diretta",
                                    "prova": seg.get("testo", "")})
            if seg.get("codice") == "bot_ufficiale_verificato" and diretta:
                ufficiale = True
            if (seg.get("codice") == "segnalazione_truffa" and not diretta
                    and str(seg.get("fonte") or "").strip()):
                fonti_segnalazioni.add(_dominio_base(str(seg["fonte"])))
        rischio = round(max(0.0, min(100.0, totale_area)))
        dati["rischio"] = rischio
        somma += rischio * peso
    totale = round(somma / sum(PESI.values()))

    ctx = r.get("contesto", {})
    materiale = ctx.get("materiale_utente", False)
    tecnica = ctx.get("tecnica_completa", False)
    fonti = ctx.get("fonti_indipendenti", 0)
    if linee_rosse or (fonti >= 2 and tecnica and materiale):
        fiducia = "alta"
    elif ufficiale and fonti >= MIN_FONTI_UFFICIALE:
        # taratura 13/11/2026: la spunta di Telegram è una prova diretta forte
        fiducia = "media"
    elif fonti == 0 or (not materiale and not tecnica):
        fiducia = "bassa"
    else:
        fiducia = "media"

    da_segnalazioni = len(fonti_segnalazioni) >= 2 and not ufficiale
    if linee_rosse or da_segnalazioni:
        esito = "rosso"
    elif totale <= SOGLIA_VERDE:
        esito = "verde"
    elif totale <= SOGLIA_GIALLO:
        esito = "giallo"
    else:
        esito = "rosso"
    if esito == "verde" and fiducia == "bassa":
        esito = "giallo"
    # taratura 13/11/2026: un'area piena non si diluisce nella media → mai verde
    if esito == "verde" and any(aree[a]["rischio"] >= SOGLIA_AREA_PIENA for a in PESI):
        esito = "giallo"

    # rischio finale (14/11/2026): il numero mostrato cade sempre nella zona del colore.
    # Una linea rossa è un'espulsione diretta: rischio massimo, non la media.
    if linee_rosse:
        finale = 100
    elif da_segnalazioni:
        finale = max(totale, SOGLIA_GIALLO + 1)
    elif esito == "giallo":
        finale = max(totale, SOGLIA_VERDE + 1)
    else:
        finale = totale

    r.update({"pesi": dict(PESI), "punteggio_totale": totale, "rischio_finale": finale,
              "linee_rosse": linee_rosse,
              "fiducia": fiducia, "verdetto": esito, "rosso_da_segnalazioni": da_segnalazioni})
    return r
