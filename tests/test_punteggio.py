import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from punteggio import ErroreVerdetto, calcola, carica_catalogo  # noqa: E402

AREE = ["identita", "promesse", "richieste", "tecnica", "reputazione", "trasparenza"]
CODICI = {
    "identita": ["nome_imita_marchio", "nome_parole_esca", "nome_incoerente_servizio",
                 "imitazione_brand_finanza", "bot_ufficiale_verificato"],
    "promesse": ["rendimento_garantito", "promessa_guadagno", "urgenza_pressione",
                 "referral_piramidale", "bonus_regalo_esca"],
    "richieste": ["richiesta_seed_o_codici", "richiesta_comando_pc", "richiesta_wallet_connect",
                  "richiesta_deposito", "richiesta_dati_personali", "richiesta_numero_contatti",
                  "prelievo_condizionato"],
    "tecnica": ["dominio_giovane", "dominio_con_marchio", "pagina_seed_phrase", "pagina_clickfix",
                "pagina_offuscata", "pagina_script_esterni", "pagina_invio_dati_esterno",
                "wallet_lib_presente", "file_pericoloso_estensione", "file_malevolo_defender"],
    "reputazione": ["etichetta_scam_telegram", "consob_oscurato", "segnalazione_truffa",
                    "recensioni_sospette", "nessuna_storia_online", "recensioni_positive_indipendenti"],
    "trasparenza": ["nessun_sito", "nessun_termini_privacy", "gestore_non_dichiarato",
                    "gestore_dichiarato_verificabile"],
}

CAT = carica_catalogo()


def s(codice, tipo="diretta", fonte="materiale dell'utente", **extra):
    d = {"codice": codice, "tipo_prova": tipo, "testo": "x", "fonte": fonte}
    d.update(extra)
    return d


def v(segnali=None, materiale=True, tecnica=True, fonti=1):
    aree = {a: {"rischio": 0, "segnali": []} for a in AREE}
    for area, lista in (segnali or {}).items():
        aree[area]["segnali"] = lista
    return {
        "versione_schema": 1,
        "bot": {"username": "ProvaBot"},
        "aree": aree,
        "contesto": {"materiale_utente": materiale, "tecnica_completa": tecnica,
                     "fonti_indipendenti": fonti},
    }


def test_catalogo_ha_tutti_i_codici():
    attesi = {c: a for a, lista in CODICI.items() for c in lista}
    assert len(attesi) == 37
    assert set(CAT) == set(attesi)
    for codice, area in attesi.items():
        assert CAT[codice]["area"] == area


def test_rischio_area_limitato_a_100():
    r = calcola(v({"identita": [s("nome_imita_marchio"), s("nome_imita_marchio")]}), CAT)
    assert r["aree"]["identita"]["rischio"] == 100


def test_rischio_area_mai_negativo():
    r = calcola(v({"identita": [s("bot_ufficiale_verificato")]}), CAT)
    assert r["aree"]["identita"]["rischio"] == 0


def test_totale_pesato():
    r = calcola(v({"identita": [s("nome_imita_marchio")]}), CAT)
    assert r["punteggio_totale"] == 13
    assert r["pesi"] == {"identita": 2, "promesse": 1, "richieste": 2, "tecnica": 2,
                         "reputazione": 1, "trasparenza": 1}


def test_linea_rossa_diretta_da_rosso():
    r = calcola(v({"richieste": [s("richiesta_seed_o_codici")]}, fonti=0), CAT)
    assert r["verdetto"] == "rosso"
    assert r["fiducia"] == "alta"
    assert [l["codice"] for l in r["linee_rosse"]] == ["richiesta_seed_o_codici"]


def test_linea_rossa_da_segnalazione_non_scatta():
    r = calcola(v({"richieste": [s("richiesta_seed_o_codici", tipo="segnalazione")]}), CAT)
    assert r["linee_rosse"] == []


def test_due_segnalazioni_indipendenti_danno_rosso():
    r = calcola(v({"reputazione": [
        s("segnalazione_truffa", tipo="segnalazione", fonte="https://www.reddit.com/r/x/1"),
        s("segnalazione_truffa", tipo="segnalazione", fonte="https://it.trustpilot.com/review/y"),
    ]}), CAT)
    assert r["rosso_da_segnalazioni"] is True
    assert r["verdetto"] == "rosso"


def test_due_segnalazioni_stesso_sito_no():
    r = calcola(v({"reputazione": [
        s("segnalazione_truffa", tipo="segnalazione", fonte="https://www.reddit.com/r/x/1"),
        s("segnalazione_truffa", tipo="segnalazione", fonte="https://reddit.com/r/y/2"),
    ]}), CAT)
    assert r["rosso_da_segnalazioni"] is False
    assert r["verdetto"] != "rosso"


def test_verde_con_fiducia_bassa_diventa_giallo():
    r = calcola(v(fonti=0), CAT)
    assert r["fiducia"] == "bassa"
    assert r["verdetto"] == "giallo"


def _con_totale(totale):
    # stesso rischio su tutte le aree (sotto 80): la media pesata è uguale al totale voluto
    segnali = {a: [s("x_" + a, fuori_catalogo=True, punti=totale)] for a in AREE}
    return v(segnali, materiale=True, tecnica=False, fonti=1)


def test_soglie():
    assert calcola(_con_totale(30), CAT)["punteggio_totale"] == 30
    assert calcola(_con_totale(30), CAT)["fiducia"] == "media"
    assert calcola(_con_totale(30), CAT)["verdetto"] == "verde"
    assert calcola(_con_totale(31), CAT)["verdetto"] == "giallo"
    assert calcola(_con_totale(61), CAT)["verdetto"] == "rosso"


def test_codice_sconosciuto_errore():
    with pytest.raises(ErroreVerdetto, match="codice_inventato"):
        calcola(v({"tecnica": [s("codice_inventato")]}), CAT)


def test_fuori_catalogo_usa_punti_propri():
    r = calcola(v({"tecnica": [s("nuovo_segnale", fuori_catalogo=True, punti=45)]}), CAT)
    assert r["aree"]["tecnica"]["rischio"] == 45


def test_fuori_catalogo_senza_punti_errore():
    with pytest.raises(ErroreVerdetto):
        calcola(v({"tecnica": [s("nuovo_segnale", fuori_catalogo=True)]}), CAT)


def test_non_modifica_input():
    orig = v({"identita": [s("nome_imita_marchio")]})
    calcola(orig, CAT)
    assert orig["aree"]["identita"]["rischio"] == 0


# Taratura 13/11/2026: spunta ufficiale + almeno 2 fonti → fiducia almeno media
def test_spunta_e_due_fonti_fiducia_media():
    r = calcola(v({"identita": [s("bot_ufficiale_verificato")]}, materiale=False, tecnica=False, fonti=2), CAT)
    assert r["fiducia"] == "media" and r["verdetto"] == "verde"


def test_spunta_con_una_fonte_resta_bassa():
    r = calcola(v({"identita": [s("bot_ufficiale_verificato")]}, materiale=False, tecnica=False, fonti=1), CAT)
    assert r["fiducia"] == "bassa" and r["verdetto"] == "giallo"


def test_spunta_da_segnalazione_non_alza_fiducia():
    r = calcola(v({"identita": [s("bot_ufficiale_verificato", tipo="segnalazione")]},
                  materiale=False, tecnica=False, fonti=3), CAT)
    assert r["fiducia"] == "bassa"


# Taratura 13/11/2026 dal collaudo: "per prelevare devi versare o portare
# altre persone" è lo schema della truffa ad anticipo → linea rossa.
def test_prelievo_condizionato_linea_rossa():
    r = calcola(v({"richieste": [s("prelievo_condizionato")]}, materiale=True, tecnica=False, fonti=2), CAT)
    assert r["verdetto"] == "rosso"
    assert [l["codice"] for l in r["linee_rosse"]] == ["prelievo_condizionato"]


def test_prelievo_condizionato_da_segnalazione_non_linea_rossa():
    r = calcola(v({"richieste": [s("prelievo_condizionato", tipo="segnalazione")]}), CAT)
    assert r["linee_rosse"] == []


# Taratura 13/11/2026: un'area a 80 o più → mai verde (al massimo giallo).
def test_area_piena_mai_verde():
    r = calcola(v({"promesse": [s("promessa_guadagno"), s("bonus_regalo_esca"), s("urgenza_pressione")]},
                  materiale=True, tecnica=True, fonti=2), CAT)
    assert r["aree"]["promesse"]["rischio"] == 90
    assert r["punteggio_totale"] <= 30
    assert r["verdetto"] == "giallo"


def test_area_a_79_resta_verde():
    r = calcola(v({"promesse": [s("x_quasi", fuori_catalogo=True, punti=79)]},
                  materiale=True, tecnica=True, fonti=2), CAT)
    assert r["verdetto"] == "verde"


def test_area_piena_non_porta_al_rosso():
    r = calcola(v({"tecnica": [s("x_pieno", fuori_catalogo=True, punti=100)]},
                  materiale=True, tecnica=True, fonti=2), CAT)
    assert r["verdetto"] == "giallo" and r["linee_rosse"] == []


# --- rischio finale coerente con l'esito (design 14/11/2026, opzione A) ---

def test_rischio_finale_linea_rossa_100():
    r = calcola(v({"richieste": [s("richiesta_seed_o_codici")]}), CAT)
    assert r["verdetto"] == "rosso" and r["punteggio_totale"] < 61
    assert r["rischio_finale"] == 100


def test_rischio_finale_segnalazioni_almeno_61():
    r = calcola(v({"reputazione": [s("segnalazione_truffa", "segnalazione", "https://reddit.com/a"),
                                   s("segnalazione_truffa", "segnalazione", "https://trustpilot.com/b")]}), CAT)
    assert r["verdetto"] == "rosso" and r["rosso_da_segnalazioni"] and not r["linee_rosse"]
    assert r["punteggio_totale"] < 61 and r["rischio_finale"] == 61


def test_rischio_finale_giallo_per_area_piena_almeno_31():
    r = calcola(v({"promesse": [s("promessa_guadagno"), s("referral_piramidale")]}), CAT)
    assert r["verdetto"] == "giallo" and r["punteggio_totale"] <= 30
    assert r["rischio_finale"] == 31


def test_rischio_finale_giallo_per_certezza_bassa_almeno_31():
    r = calcola(v(fonti=0, materiale=False, tecnica=False), CAT)
    assert r["verdetto"] == "giallo" and r["fiducia"] == "bassa" and r["punteggio_totale"] == 0
    assert r["rischio_finale"] == 31
