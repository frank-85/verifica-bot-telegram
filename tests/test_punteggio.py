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
    "tecnica": ["dominio_giovane", "dominio_con_marchio", "dominio_tld_rischioso", "pagina_seed_phrase", "pagina_clickfix",
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
    assert len(attesi) == 38
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
    # taratura 18/11/2026: somma pesata ÷ 3 (non più media), promesse ×2
    r = calcola(v({"identita": [s("nome_imita_marchio")]}), CAT)
    assert r["punteggio_totale"] == 40  # 60 × 2 ÷ 3
    assert r["pesi"] == {"identita": 2, "promesse": 2, "richieste": 2, "tecnica": 2,
                         "reputazione": 1, "trasparenza": 1}


def test_totale_somma_aree_senza_diluire():
    # le aree vuote non abbassano il punteggio: 50×2 (deposito) + 20×1 (nessun sito) = 120 ÷ 3 = 40
    r = calcola(v({"richieste": [s("richiesta_deposito")], "trasparenza": [s("nessun_sito")]}), CAT)
    assert r["punteggio_totale"] == 40 and r["verdetto"] == "giallo"


def test_totale_con_tetto_100():
    r = calcola(v({"promesse": [s("promessa_guadagno")], "richieste": [s("richiesta_deposito"),
                   s("richiesta_wallet_connect")], "tecnica": [s("dominio_giovane")]}), CAT)
    assert r["punteggio_totale"] == 100  # (80 + 180 + 60) ÷ 3 = 107 → 100


# Gli 8 bot di esempio con cui Francesco ha scelto la formula (18/11/2026)
ESEMPI = [
    ({"trasparenza": ["gestore_dichiarato_verificabile"]}, 0, "verde"),
    ({"trasparenza": ["nessun_sito", "nessun_termini_privacy", "gestore_non_dichiarato"],
      "reputazione": ["nessuna_storia_online"]}, 27, "verde"),
    ({"promesse": ["promessa_guadagno", "referral_piramidale", "bonus_regalo_esca", "urgenza_pressione"],
      "reputazione": ["nessuna_storia_online"]}, 73, "rosso"),
    ({"promesse": ["promessa_guadagno"], "richieste": ["richiesta_deposito", "richiesta_wallet_connect"],
      "tecnica": ["dominio_giovane"]}, 100, "rosso"),
    ({"richieste": ["richiesta_dati_personali", "richiesta_numero_contatti"],
      "trasparenza": ["nessun_sito", "gestore_non_dichiarato"]}, 43, "giallo"),
    ({"tecnica": ["pagina_offuscata", "pagina_invio_dati_esterno", "pagina_script_esterni",
                  "dominio_giovane", "dominio_tld_rischioso"]}, 63, "rosso"),
    ({"promesse": ["promessa_guadagno"], "reputazione": ["segnalazione_truffa", "nessuna_storia_online"]},
     45, "giallo"),
    ({"richieste": ["richiesta_deposito"], "trasparenza": ["nessun_sito"]}, 40, "giallo"),
]


@pytest.mark.parametrize("segnali,totale,colore", ESEMPI)
def test_esempi_scelta_formula(segnali, totale, colore):
    r = calcola(v({a: [s(c) for c in lista] for a, lista in segnali.items()}), CAT)
    assert (r["punteggio_totale"], r["verdetto"]) == (totale, colore)


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


def test_d_due_siti_co_uk_diversi_danno_rosso():
    r = calcola(v({"reputazione": [
        s("segnalazione_truffa", tipo="segnalazione", fonte="https://news.bbc.co.uk/a"),
        s("segnalazione_truffa", tipo="segnalazione", fonte="https://forum.example.co.uk/b"),
    ]}), CAT)
    assert r["rosso_da_segnalazioni"] is True
    assert r["verdetto"] == "rosso"


def test_d_due_sottodomini_stesso_sito_co_uk_no():
    r = calcola(v({"reputazione": [
        s("segnalazione_truffa", tipo="segnalazione", fonte="https://news.bbc.co.uk/a"),
        s("segnalazione_truffa", tipo="segnalazione", fonte="https://www.bbc.co.uk/b"),
    ]}), CAT)
    assert r["rosso_da_segnalazioni"] is False


def test_d_fonti_senza_schema_stesso_sito_percorsi_diversi_no():
    r = calcola(v({"reputazione": [
        s("segnalazione_truffa", tipo="segnalazione", fonte="reddit.com/r/x/1"),
        s("segnalazione_truffa", tipo="segnalazione", fonte="www.reddit.com/r/y/2?a=1"),
    ]}), CAT)
    assert r["rosso_da_segnalazioni"] is False


# --- correzione A (17/11/2026): imitazione composta → rosso, rischio almeno 61 ---
def _nome(username, link=False, ufficiale=None):
    """Segnali come li produce il controllo del nome (e del link) per un username."""
    from nome import analizza_nome
    n = analizza_nome(username)
    ident = []
    if n["imitazioni"] and not n["ufficiale"]:
        ident.append(s("nome_imita_marchio", fonte="controllo del nome"))
    if n["parole_esca"]:
        ident.append(s("nome_parole_esca", fonte="controllo del nome"))
    if ufficiale:
        ident.append(s("bot_ufficiale_verificato", tipo=ufficiale))
    seg = {"identita": ident}
    if link:
        seg["tecnica"] = [s("dominio_con_marchio", fonte="controllo del link"),
                          s("dominio_tld_rischioso", fonte="controllo del link")]
    return v(seg, materiale=False, tecnica=False, fonti=0)


def test_a_marchio_esca_e_dominio_rosso():
    r = calcola(_nome("B1nance_Support_bot", link=True), CAT)
    assert r["rosso_da_imitazione"] is True and r["verdetto"] == "rosso"
    # 18/11: con la somma ÷ 3 il clone completo è già oltre 61 da solo (identità 80, tecnica 45)
    assert r["rischio_finale"] == r["punteggio_totale"] == 83
    assert r["linee_rosse"] == [] and r["fiducia"] == "bassa"  # non è una linea rossa: certezza invariata


def test_a_marchio_ed_esca_senza_link_rosso():
    r = calcola(_nome("B1nance_Support_bot"), CAT)
    assert r["rosso_da_imitazione"] is True and r["verdetto"] == "rosso" and r["rischio_finale"] == 61


def test_a_marchio_e_dominio_senza_esca_rosso():
    r = calcola(v({"identita": [s("nome_imita_marchio")], "tecnica": [s("dominio_con_marchio")]}), CAT)
    assert r["rosso_da_imitazione"] is True and r["verdetto"] == "rosso"


@pytest.mark.parametrize("username", ["B1nanceBot", "BinanceP2PEsempioBot", "wallet"])
def test_a_regola_non_attiva(username):
    prima = calcola(_nome(username), CAT)
    assert prima["rosso_da_imitazione"] is False
    # giallo come prima; dal 18/11 il numero è la somma ÷ 3 (marchio imitato 60 × 2 ÷ 3 = 40)
    assert prima["verdetto"] == "giallo" and prima["rischio_finale"] == max(31, prima["punteggio_totale"])


def test_a_spunta_verificata_diretta_disattiva_la_regola():
    r = calcola(_nome("B1nance_Support_bot", link=True, ufficiale="diretta"), CAT)
    assert r["rosso_da_imitazione"] is False and r["verdetto"] != "rosso"


def test_a_spunta_solo_dichiarata_non_disattiva_la_regola():
    r = calcola(_nome("B1nance_Support_bot", link=True, ufficiale="segnalazione"), CAT)
    assert r["rosso_da_imitazione"] is True and r["verdetto"] == "rosso"


def test_a_segnali_da_segnalazione_non_attivano_la_regola():
    r = calcola(v({"identita": [s("nome_imita_marchio", tipo="segnalazione"),
                                s("nome_parole_esca", tipo="segnalazione")]}), CAT)
    assert r["rosso_da_imitazione"] is False


def test_a_linea_rossa_resta_a_100():
    r = calcola(v({"identita": [s("nome_imita_marchio"), s("nome_parole_esca")],
                   "richieste": [s("richiesta_seed_o_codici")]}), CAT)
    assert r["rischio_finale"] == 100 and r["fiducia"] == "alta"


def test_a_tld_rischioso_pesa_5_nella_tecnica():
    assert CAT["dominio_tld_rischioso"]["punti"] == 5 and CAT["dominio_tld_rischioso"]["area"] == "tecnica"
    assert not CAT["dominio_tld_rischioso"]["linea_rossa"]
    r = calcola(v({"tecnica": [s("dominio_tld_rischioso")]}), CAT)
    assert r["aree"]["tecnica"]["rischio"] == 5


def test_verde_con_fiducia_bassa_diventa_giallo():
    r = calcola(v(fonti=0), CAT)
    assert r["fiducia"] == "bassa"
    assert r["verdetto"] == "giallo"


def _con_totale(totale):
    # rischio diviso fra le due aree a peso 1: (a + b) ÷ 3 = totale voluto (sotto 80 per area fino a 53)
    a = 3 * totale // 2
    segnali = {"reputazione": [s("x_rep", fuori_catalogo=True, punti=a)],
               "trasparenza": [s("x_tra", fuori_catalogo=True, punti=3 * totale - a)]}
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
# Dal 18/11 la regola serve per le aree a peso 1: 90 ÷ 3 = 30 sarebbe verde.
def test_area_piena_mai_verde():
    r = calcola(v({"trasparenza": [s("x_pieno", fuori_catalogo=True, punti=90)]},
                  materiale=True, tecnica=True, fonti=2), CAT)
    assert r["aree"]["trasparenza"]["rischio"] == 90
    assert r["punteggio_totale"] <= 30
    assert r["verdetto"] == "giallo"


def test_area_a_79_resta_verde():
    r = calcola(v({"trasparenza": [s("x_quasi", fuori_catalogo=True, punti=79)]},
                  materiale=True, tecnica=True, fonti=2), CAT)
    assert r["verdetto"] == "verde"


def test_area_piena_non_porta_al_rosso():
    # area a peso 1: 100 ÷ 3 = 33 → giallo (un'area a peso 2 piena vale 67 → rosso dal 18/11)
    r = calcola(v({"trasparenza": [s("x_pieno", fuori_catalogo=True, punti=100)]},
                  materiale=True, tecnica=True, fonti=2), CAT)
    assert r["verdetto"] == "giallo" and r["linee_rosse"] == []


# --- rischio finale coerente con l'esito (design 14/11/2026, opzione A) ---

def test_rischio_finale_linea_rossa_100():
    r = calcola(v({"richieste": [s("richiesta_seed_o_codici")]}), CAT)
    assert r["verdetto"] == "rosso" and r["punteggio_totale"] == 67  # 100 × 2 ÷ 3
    assert r["rischio_finale"] == 100


def test_rischio_finale_segnalazioni_almeno_61():
    r = calcola(v({"reputazione": [s("segnalazione_truffa", "segnalazione", "https://reddit.com/a"),
                                   s("segnalazione_truffa", "segnalazione", "https://trustpilot.com/b")]}), CAT)
    assert r["verdetto"] == "rosso" and r["rosso_da_segnalazioni"] and not r["linee_rosse"]
    assert r["punteggio_totale"] < 61 and r["rischio_finale"] == 61


def test_rischio_finale_giallo_per_area_piena_almeno_31():
    r = calcola(v({"trasparenza": [s("x_pieno", fuori_catalogo=True, punti=80)]}), CAT)
    assert r["verdetto"] == "giallo" and r["punteggio_totale"] <= 30
    assert r["rischio_finale"] == 31


def test_rischio_finale_giallo_per_certezza_bassa_almeno_31():
    r = calcola(v(fonti=0, materiale=False, tecnica=False), CAT)
    assert r["verdetto"] == "giallo" and r["fiducia"] == "bassa" and r["punteggio_totale"] == 0
    assert r["rischio_finale"] == 31


# --- verde con riserva (18/11/2026): regola del motore, attivata da contesto.risposte_complete ---

def _riserva(segnali=None, complete=True, materiale=False, fonti=0):
    d = v(segnali, materiale=materiale, tecnica=False, fonti=fonti)
    d["contesto"]["risposte_complete"] = complete
    return d


def test_riserva_risposte_complete_senza_prove_verde_piu_20():
    r = calcola(_riserva(), CAT)
    assert (r["verdetto"], r["fiducia"], r["verde_con_riserva"]) == ("verde", "bassa", True)
    assert (r["punteggio_totale"], r["rischio_finale"]) == (0, 20)


def test_riserva_senza_flag_resta_giallo():
    r = calcola(_riserva(complete=False), CAT)
    assert (r["verdetto"], r["verde_con_riserva"], r["rischio_finale"]) == ("giallo", False, 31)
    d = v(materiale=False, tecnica=False, fonti=0)  # flag assente = false: la skill non cambia comportamento
    assert calcola(d, CAT)["verdetto"] == "giallo"


def test_riserva_piccoli_segnali_oltre_30_giallo():
    r = calcola(_riserva({"trasparenza": [s("nessun_sito"), s("nessun_termini_privacy")]}), CAT)
    assert r["punteggio_totale"] == 13 and r["verdetto"] == "giallo" and not r["verde_con_riserva"]


def test_riserva_area_piena_giallo():
    r = calcola(_riserva({"trasparenza": [s("x_pieno", fuori_catalogo=True, punti=80)]}), CAT)
    assert r["verdetto"] == "giallo" and not r["verde_con_riserva"]


def test_riserva_non_tocca_il_verde_con_prove():
    r = calcola(_riserva(materiale=True, fonti=1), CAT)
    assert (r["verdetto"], r["fiducia"], r["verde_con_riserva"], r["rischio_finale"]) == ("verde", "media", False, 0)


def test_riserva_non_salva_dalle_linee_rosse():
    r = calcola(_riserva({"richieste": [s("richiesta_seed_o_codici")]}), CAT)
    assert r["verdetto"] == "rosso" and not r["verde_con_riserva"]


def test_riserva_flag_deve_essere_booleano():
    with pytest.raises(ErroreVerdetto, match="risposte_complete"):
        calcola(_riserva(complete="si"), CAT)
