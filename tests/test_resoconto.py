import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from punteggio import calcola, carica_catalogo  # noqa: E402
from resoconto import NOTA_FINALE, genera_md  # noqa: E402

AREE = ["identita", "promesse", "richieste", "tecnica", "reputazione", "trasparenza"]
CAT = carica_catalogo()


def base(segnali=None, fonti=2, **extra):
    aree = {a: {"rischio": 0, "segnali": []} for a in AREE}
    for area, lista in (segnali or {}).items():
        aree[area]["segnali"] = lista
    v = {"versione_schema": 1, "data": "2026-11-13T10:00:00",
         "bot": {"username": "ProvaBot", "tipo": "strumento", "link": []},
         "aree": aree,
         "contesto": {"materiale_utente": True, "tecnica_completa": True, "fonti_indipendenti": fonti},
         "cosa_fare": ["Puoi leggere i messaggi"], "cosa_non_fare": ["Non collegare il wallet"],
         "non_verificato": ["Codice lato server"],
         "fonti": [{"titolo": "Pagina t.me", "url": "https://t.me/ProvaBot", "consultata": "2026-11-13"}]}
    v.update(extra)
    return calcola(v, CAT)


def seg(codice, tipo="diretta", fonte="materiale dell'utente"):
    return {"codice": codice, "tipo_prova": tipo, "testo": "testo " + codice, "fonte": fonte}


def test_verde_non_dice_sicuro():
    md = genera_md(base())
    assert "🟢" in md
    corpo = md.replace(NOTA_FINALE, "").lower()
    assert "sicuro" not in corpo and "garantito" not in corpo


def test_rosso_da_segnalazioni_dichiarato():
    md = genera_md(base({"reputazione": [
        seg("segnalazione_truffa", "segnalazione", "https://reddit.com/a"),
        seg("segnalazione_truffa", "segnalazione", "https://trustpilot.com/b")]}))
    assert "🔴" in md
    assert "Segnalato da terzi, non verificato direttamente" in md


def test_a_rosso_da_imitazione_dichiarato():
    md = genera_md(base({"identita": [seg("nome_imita_marchio"), seg("nome_parole_esca")]}))
    assert "🔴" in md
    assert "rischio **61/100** (imitazione evidente di un marchio; punteggio delle aree" in md
    assert ("> Prevale la regola sull'imitazione: il nome richiama un marchio noto e contiene parole esca "
            "o rimanda a un dominio che usa lo stesso marchio.") in md


def test_a_senza_imitazione_nessuna_frase():
    md = genera_md(base({"identita": [seg("nome_imita_marchio")]}))
    assert "imitazione" not in md.lower()


def test_sezioni_presenti():
    md = genera_md(base())
    for titolo in ["## Le sei aree", "## Cosa puoi fare", "## Cosa NON fare",
                   "## Cosa non ho potuto verificare", "## Fonti"]:
        assert titolo in md


def test_linee_rosse_assenti_niente_sezione():
    assert "## Linee rosse" not in genera_md(base())


def test_linee_rosse_presenti():
    md = genera_md(base({"richieste": [seg("richiesta_seed_o_codici")]}))
    assert "## Linee rosse" in md and "richiesta_seed_o_codici" not in md.split("## Linee rosse")[0]


def test_nota_finale_presente():
    assert genera_md(base()).rstrip().endswith(NOTA_FINALE)


def test_intestazione():
    md = genera_md(base())
    assert md.startswith("# Verifica @ProvaBot — 13/11/2026")


# Etichette 13/11/2026: la "fiducia nel bot" segue il semaforo;
# la vecchia "fiducia" si mostra come "certezza della valutazione". Nessun cambio al calcolo.
def test_verde_fiducia_nel_bot_alta():
    md = genera_md(base())
    assert "fiducia nel bot **alta**" in md
    assert "certezza della valutazione **" in md


def test_rosso_fiducia_nel_bot_bassa():
    md = genera_md(base({"richieste": [seg("richiesta_seed_o_codici")]}))
    assert "🔴" in md and "fiducia nel bot **bassa**" in md
    assert "certezza della valutazione **alta**" in md


def test_giallo_fiducia_nel_bot_media():
    md = genera_md(base(fonti=0))
    assert "🟡" in md and "fiducia nel bot **media**" in md


def test_parola_fiducia_mai_da_sola():
    md = genera_md(base())
    assert "· fiducia **" not in md


# Etichette 13/11/2026: se il rosso nasce da una linea rossa o da segnalazioni concordi,
# il numero medio non compare accanto al semaforo (sembrerebbe contraddirlo).
def test_rosso_da_linea_rossa_niente_punteggio_medio():
    md = genera_md(base({"richieste": [seg("richiesta_seed_o_codici")]}))
    intestazione = md.split("## ")[0]
    assert "linea rossa superata" in intestazione
    assert "punteggio di rischio" not in intestazione


def test_rosso_da_segnalazioni_etichetta():
    md = genera_md(base({"reputazione": [
        seg("segnalazione_truffa", "segnalazione", "https://reddit.com/a"),
        seg("segnalazione_truffa", "segnalazione", "https://trustpilot.com/b")]}))
    intestazione = md.split("## ")[0]
    assert "segnalazioni concordi da più fonti" in intestazione
    assert "punteggio di rischio" not in intestazione


def test_verde_mostra_punteggio():
    assert "rischio **0/100**" in genera_md(base())


# --- M6: nel resoconto i link dei bot e dei siti sospetti non devono essere cliccabili ---
import re  # noqa: E402

import resoconto  # noqa: E402

KIT = Path(__file__).resolve().parents[1]


def _link_attivi(md: str) -> list[str]:
    """Link che un visualizzatore Markdown renderebbe cliccabili (fuori dagli span di codice).
    Una ] preceduta da backslash è neutralizzata e non apre un link."""
    fuori_codice = re.sub(r"`[^`]*`", "", md)
    return re.findall(r"(?<!\\)\]\([^)]*\)|<https?://[^>]*>|https?://\S+|www\.\S+", fuori_codice)


def con_fonte(titolo, url):
    v = base()
    v["fonti"] = [{"titolo": titolo, "url": url, "consultata": "2026-11-14"}]
    return v


def test_fonte_tme_disinnescata():
    md = genera_md(base())
    assert _link_attivi(md) == []
    assert "`hxxps://t.me/ProvaBot`" in md


def test_fonte_affidabile_resta_cliccabile():
    md = genera_md(con_fonte("Avvisi CONSOB", "https://www.consob.it/web/avvisi"))
    assert "[Avvisi CONSOB](https://www.consob.it/web/avvisi)" in md


def test_fonte_affidabile_in_http_o_imitata_disinnescata():
    for url in ("http://www.consob.it/x", "https://consob.it.evil.com/x", "https://evilconsob.it/x",
                "https://user@consob.it/x", "javascript:alert(1)"):
        md = genera_md(con_fonte("Fonte", url))
        assert _link_attivi(md) == [], url


def test_link_nei_testi_disinnescati():
    s = seg("richiesta_seed_o_codici")
    s["testo"] = "La Mini App https://binance-wallet-app.com/seed chiede le 24 parole"
    md = genera_md(base({"richieste": [s]}, cosa_fare=["Confronta con www.bin4nce.top prima di tutto"],
                        non_verificato=["Il sito <https://evil.xyz> non risponde"]))
    assert _link_attivi(md) == []
    assert "hxxps://binance-wallet-app.com/seed" in md
    assert "www[.]bin4nce.top" in md


def test_link_markdown_iniettato_nel_testo_neutralizzato():
    s = seg("promessa_guadagno")
    s["testo"] = "Il bot scrive: [Ritira il premio](https://premio-facile.xyz/claim)"
    md = genera_md(base({"promesse": [s]}))
    assert _link_attivi(md) == []
    assert r"\[Ritira il premio\]" in md


def test_fonti_affidabili_uguali_all_app():
    js = (KIT / "app" / "sicurezza.js").read_text(encoding="utf-8")
    elenco = re.search(r"FONTI_AFFIDABILI = \[(.*?)\];", js, re.S).group(1)
    assert set(resoconto.FONTI_AFFIDABILI) == set(re.findall(r'"([^"]+)"', elenco))


# --- rischio finale nel resoconto (14/11/2026) ---

def test_resoconto_linea_rossa_mostra_100_e_media():
    md = genera_md(base({"richieste": [seg("richiesta_seed_o_codici")]}))
    assert "rischio **100/100**" in md
    assert "linea rossa superata" in md and "punteggio delle aree" in md


def test_resoconto_verde_ordinario_senza_nota_media():
    md = genera_md(base())
    assert "rischio **0/100**" in md and "punteggio delle aree" not in md


def test_resoconto_verdetto_vecchio_senza_rischio_finale():
    v = base()
    del v["rischio_finale"]
    v["punteggio_totale"] = 12
    assert "rischio **12/100**" in genera_md(v)


def test_resoconto_verde_con_riserva_spiega_i_20_punti():
    md = genera_md(base(contesto={"materiale_utente": False, "tecnica_completa": False, "fonti_indipendenti": 0,
                                  "risposte_complete": True}))
    assert "rischio **20/100**" in md and "verde con riserva" in md and "punteggio delle aree 0/100" in md
