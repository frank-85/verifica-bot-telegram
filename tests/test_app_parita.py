"""Parità tra il motore Python (punteggio.py, nome.py) e il porting JS in app/."""
import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))

from punteggio import ErroreVerdetto, calcola, carica_catalogo  # noqa: E402

CAT = carica_catalogo()
CATALOGO_LISTA = json.loads((KIT / "segnali.json").read_text(encoding="utf-8"))
AREE = ["identita", "promesse", "richieste", "tecnica", "reputazione", "trasparenza"]
ESEGUI = KIT / "tests" / "js" / "esegui.js"


def trova_node() -> str | None:
    trovato = shutil.which("node")
    if trovato:
        return trovato
    alternativo = Path("C:/nvm4w/nodejs/node.exe")
    return str(alternativo) if alternativo.exists() else None


def node_esegui(payload: dict) -> list:
    node = trova_node()
    if not node:
        pytest.skip("Node.js non trovato")
    dati = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    r = subprocess.run([node, str(ESEGUI)], input=dati, capture_output=True, timeout=60)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    return json.loads(r.stdout.decode("utf-8"))


def s(codice, tipo="diretta", fonte="materiale", **extra):
    d = {"codice": codice, "tipo_prova": tipo, "testo": "x", "fonte": fonte}
    d.update(extra)
    return d


def fc(codice, area_punti, **extra):
    return s(codice, fuori_catalogo=True, punti=area_punti, **extra)


def v(segnali=None, materiale=True, tecnica=True, fonti=1):
    aree = {a: {"rischio": 0, "segnali": []} for a in AREE}
    for area, lista in (segnali or {}).items():
        aree[area]["segnali"] = lista
    return {"versione_schema": 1, "bot": {"username": "ProvaBot"}, "aree": aree,
            "contesto": {"materiale_utente": materiale, "tecnica_completa": tecnica,
                         "fonti_indipendenti": fonti}}


def _casi_calcola():
    casi = {}
    for voce in CATALOGO_LISTA:
        if voce["linea_rossa"]:
            casi["rossa_diretta_" + voce["codice"]] = v({voce["area"]: [s(voce["codice"])]})
            casi["rossa_segnalazione_" + voce["codice"]] = v(
                {voce["area"]: [s(voce["codice"], tipo="segnalazione", fonte="https://x.com/a")]})
    # 18/11: somma pesata ÷ 3 → casi di confine ricalcolati
    casi["totale_30"] = v({"richieste": [s("richiesta_dati_personali")],
                           "trasparenza": [s("nessun_sito"), s("nessun_termini_privacy")]})  # 50+40=90
    casi["totale_31"] = v({"reputazione": [fc("x_re", 46)], "trasparenza": [fc("x_tr", 47)]})
    casi["totale_60"] = v({"identita": [fc("x_id", 90)]})
    casi["totale_61"] = v({"identita": [fc("x_id", 90)], "trasparenza": [fc("x_tr", 3)]})
    casi["area_80_totale_basso"] = v({"trasparenza": [fc("x_tr", 80)]}, fonti=2)
    # verde con riserva (18/11/2026): stessi confini in Python e JS
    for nome, punti in (("riserva_0", 0), ("riserva_10", 30), ("riserva_11", 33), ("riserva_area_80", 80)):
        casi[nome] = v({"trasparenza": [fc("x_tr", punti)]} if punti else None, materiale=False, tecnica=False, fonti=0)
        casi[nome]["contesto"]["risposte_complete"] = True
    # tester UX 26/11/2026: risposte contraddittorie → certezza bassa, niente verde con riserva
    casi["contraddizioni_linea_rossa"] = v({"reputazione": [s("etichetta_scam_telegram")]}, fonti=2)
    casi["contraddizioni_linea_rossa"]["contesto"]["risposte_contraddittorie"] = True
    casi["contraddizioni_riserva"] = v(None, materiale=False, tecnica=False, fonti=0)
    casi["contraddizioni_riserva"]["contesto"].update(risposte_complete=True, risposte_contraddittorie=True)
    casi["ufficiale_1_fonte"] = v({"identita": [s("bot_ufficiale_verificato")]},
                                  materiale=False, tecnica=False, fonti=1)
    casi["ufficiale_2_fonti"] = v({"identita": [s("bot_ufficiale_verificato")]},
                                  materiale=False, tecnica=False, fonti=2)
    casi["segnalazioni_stesso_dominio"] = v({"reputazione": [
        s("segnalazione_truffa", tipo="segnalazione", fonte="https://a.example.com/1"),
        s("segnalazione_truffa", tipo="segnalazione", fonte="https://www.b.example.com/2")]})
    casi["segnalazioni_domini_diversi"] = v({"reputazione": [
        s("segnalazione_truffa", tipo="segnalazione", fonte="https://x.com/1"),
        s("segnalazione_truffa", tipo="segnalazione", fonte="y.org/2")]})
    # correzione D: suffissi a due parti (co.uk) contati come siti distinti
    casi["segnalazioni_due_siti_co_uk"] = v({"reputazione": [
        s("segnalazione_truffa", tipo="segnalazione", fonte="https://news.bbc.co.uk/1"),
        s("segnalazione_truffa", tipo="segnalazione", fonte="https://forum.example.co.uk/2")]})
    casi["segnalazioni_stesso_sito_co_uk"] = v({"reputazione": [
        s("segnalazione_truffa", tipo="segnalazione", fonte="https://news.bbc.co.uk/1"),
        s("segnalazione_truffa", tipo="segnalazione", fonte="www.bbc.co.uk/2")]})
    casi["segnalazioni_senza_schema_stesso_sito"] = v({"reputazione": [
        s("segnalazione_truffa", tipo="segnalazione", fonte="reddit.com/r/x/1"),
        s("segnalazione_truffa", tipo="segnalazione", fonte="www.reddit.com/r/y/2?a=1")]})
    # correzione A: imitazione composta
    casi["imitazione_marchio_esca_dominio"] = v({"identita": [s("nome_imita_marchio"), s("nome_parole_esca")],
                                                 "tecnica": [s("dominio_con_marchio"), s("dominio_tld_rischioso")]},
                                                materiale=False, tecnica=False, fonti=0)
    casi["imitazione_marchio_esca"] = v({"identita": [s("nome_imita_marchio"), s("nome_parole_esca")]},
                                        materiale=False, tecnica=False, fonti=0)
    casi["imitazione_solo_marchio"] = v({"identita": [s("nome_imita_marchio")]},
                                        materiale=False, tecnica=False, fonti=0)
    casi["imitazione_con_spunta_diretta"] = v({"identita": [s("nome_imita_marchio"), s("nome_parole_esca"),
                                                            s("bot_ufficiale_verificato")]})
    casi["imitazione_con_spunta_dichiarata"] = v({"identita": [s("nome_imita_marchio"), s("nome_parole_esca"),
                                                               s("bot_ufficiale_verificato", tipo="segnalazione")]})
    casi["imitazione_da_segnalazione"] = v({"identita": [s("nome_imita_marchio", tipo="segnalazione"),
                                                         s("nome_parole_esca", tipo="segnalazione")]})
    casi["fuori_catalogo_limiti"] = v({"promesse": [fc("x_alto", 150)],
                                       "tecnica": [fc("x_basso", -80)]})
    casi["arrotondamento_12_5"] = v({"promesse": [fc("x_mezzo", 12.5)]})
    casi["arrotondamento_13_5"] = v({"promesse": [fc("x_mezzo", 13.5)]})
    casi["vuoto_senza_fonti"] = v(fonti=0, materiale=False, tecnica=False)
    casi["vuoto_fonti_media"] = v(fonti=1, materiale=True, tecnica=False)
    return casi


CASI = _casi_calcola()
CAMPI = ["punteggio_totale", "rischio_finale", "verdetto", "fiducia", "linee_rosse", "rosso_da_segnalazioni",
         "rosso_da_imitazione", "verde_con_riserva"]


def _riassunto(r: dict) -> dict:
    d = {k: r[k] for k in CAMPI}
    d["rischi"] = {a: r["aree"][a]["rischio"] for a in AREE}
    return d


@pytest.fixture(scope="module")
def risultati_js():
    nomi = list(CASI)
    out = node_esegui({"op": "calcola", "catalogo": CATALOGO_LISTA,
                       "casi": [CASI[n] for n in nomi]})
    return dict(zip(nomi, out))


def test_ci_sono_tutte_le_10_linee_rosse():
    assert sum(1 for n in CASI if n.startswith("rossa_diretta_")) == 10


@pytest.mark.parametrize("nome", list(CASI))
def test_parita_calcola(nome, risultati_js):
    atteso = _riassunto(calcola(copy.deepcopy(CASI[nome]), CAT))
    js = risultati_js[nome]
    assert js["ok"], js
    assert _riassunto(js["risultato"]) == atteso


def _non_validi():
    base = v()
    casi = {}
    c = copy.deepcopy(base); c["aree"]["inventata"] = {"segnali": []}; casi["area_sconosciuta"] = c
    casi["tipo_prova_errato"] = v({"identita": [s("nome_imita_marchio", tipo="forse")]})
    casi["codice_inventato"] = v({"identita": [s("codice_inventato")]})
    casi["area_sbagliata"] = v({"promesse": [s("nome_imita_marchio")]})
    c = copy.deepcopy(base); c["contesto"]["fonti_indipendenti"] = "2"; casi["fonti_stringa"] = c
    c = copy.deepcopy(base); c["contesto"]["materiale_utente"] = "true"; casi["materiale_stringa"] = c
    casi["fuori_catalogo_senza_punti"] = v({"promesse": [s("x_nuovo", fuori_catalogo=True)]})
    casi["fuori_catalogo_ma_in_catalogo"] = v({"promesse": [fc("promessa_guadagno", 10)]})
    c = copy.deepcopy(base); del c["aree"]; casi["senza_aree"] = c
    casi["non_oggetto"] = [1, 2]
    return casi


NON_VALIDI = _non_validi()


@pytest.mark.parametrize("nome", list(NON_VALIDI))
def test_parita_errori(nome):
    with pytest.raises(ErroreVerdetto):
        calcola(copy.deepcopy(NON_VALIDI[nome]), CAT)
    out = node_esegui({"op": "calcola", "catalogo": CATALOGO_LISTA, "casi": [NON_VALIDI[nome]]})
    assert out[0]["ok"] is False and out[0]["errore"] is True
    assert "tipo" not in out[0], out[0]  # deve essere un ErroreVerdetto, non un crash


NOMI = ["MetamasksAppWebEsempioBot", "wallet", "ESEMPIO_MINER_ROBOT", "@binance_support",
        "https://t.me/MetaMaskHelpBot?start=x", "rnetamask_bot", "c0inbase", "okx_airdrop",
        "PosteItalianeBot", "tonkeeperr", "telegram", "BotFather", "freegiftclaim", "ton", "x",
        "TON_wallet_official", "Bybit_Support_Help", "  @PayPal_Rewards  ",
        # M5: marchi corti attaccati a parole esca, marchio generico "wallet"
        "OKXofficialbot", "freetonbot", "0KXsupport", "TonnoFrescoBot", "MyWalletTrackerBot",
        "WalletOfficialBot", "Wa11etHelpBot", "WalIetSupportBot", "wallet2024bot", "OfficialWallet",
        # M1: formati di link Telegram
        "https://t.me/s/MetamasksAppWebEsempioBot", "tg://resolve?domain=MetamasksAppWebEsempioBot&start=ref123",
        "TG://RESOLVE?DOMAIN=wallet", "https://web.telegram.org/k/#@MetamasksAppWebEsempioBot",
        "https://web.telegram.org/a/#wallet", "https://web.telegram.org/a/#-1001234567890",
        "https://t.me/+AbCdEf123", "t.me/joinchat/AbCdEf", "tg://user?id=12345", "https://t.me/s/"]


@pytest.mark.parametrize("username", NOMI)
def test_parita_nome(username):
    from nome import analizza_nome
    marchi = (KIT / "marchi.txt").read_text(encoding="utf-8")
    out = node_esegui({"op": "nome", "marchi": marchi, "casi": [username]})
    assert out[0]["ok"], out[0]
    assert out[0]["risultato"] == analizza_nome(username)


def _input_q(**extra):
    q = json.loads((KIT / "app" / "questionario.json").read_text(encoding="utf-8"))
    # risposte sicure: "No" alle domande sul rischio, "Sì" a quelle in positivo (segnale_se = "no")
    risposte = {d["codice"]: "si" if d.get("segnale_se") == "no" else "no"
                for a in q["pagine"] for d in a["domande"]}
    risposte.update(extra.pop("si", {}))
    base = {"username": "ProvaBot", "nomeVisualizzato": "", "risposte": risposte, "sezioniViste": True,
            "testi": [], "linkMiniApp": "", "linkSegnalazioni": [], "linkPositivi": []}
    base.update(extra)
    return base


CASI_Q = {
    "solo_no": _input_q(),
    "no_testo_innocuo": _input_q(username="wallet", testi=[{"origine": "incollato", "testo": "Benvenuto"}]),
    "si_seed": _input_q(si={"richiesta_seed_o_codici": "si"}),
    "contrasto_prelievo": _input_q(testi=[{"origine": "screenshot", "testo": "deposit to withdraw"}]),
    "segnalazioni": _input_q(linkSegnalazioni=["https://x.com/a", "https://y.org/b"]),
    "nome_marchio_link": _input_q(username="MetamasksAppWebEsempioBot", linkMiniApp="https://binance-wallet-app.com/x",
                                  testi=[{"origine": "incollato", "testo": "Guaranteed 3% daily profit"}]),
    # correzione A: i quattro casi della revisione
    "a_b1nance_support_link": _input_q(username="B1nance_Support_bot", sezioniViste=False,
                                      linkMiniApp="https://binance-airdrop-claim.xyz/app"),
    "a_b1nance_support": _input_q(username="B1nance_Support_bot", sezioniViste=False),
    "a_b1nancebot": _input_q(username="B1nanceBot", sezioniViste=False),
    "a_binance_p2p_alerts": _input_q(username="BinanceP2PEsempioBot", sezioniViste=False),
    "a_wallet_testo": _input_q(username="wallet", sezioniViste=False, testi=[{"origine": "incollato",
                               "testo": "Welcome to Wallet. Buy, sell and store crypto. Terms of service apply."}]),
}
CAMPI_CALCOLATI = ["pesi", "punteggio_totale", "rischio_finale", "linee_rosse", "fiducia", "verdetto", "rosso_da_segnalazioni",
                   "rosso_da_imitazione", "verde_con_riserva"]


@pytest.mark.parametrize("nome", list(CASI_Q))
def test_parita_questionario(nome):
    payload = {"op": "assembla", "catalogo": CATALOGO_LISTA,
               "questionario": json.loads((KIT / "app" / "questionario.json").read_text(encoding="utf-8")),
               "regole": json.loads((KIT / "app" / "analizzatore.json").read_text(encoding="utf-8")),
               "marchi": (KIT / "marchi.txt").read_text(encoding="utf-8"), "casi": [CASI_Q[nome]]}
    out = node_esegui(payload)
    assert out[0]["ok"], out[0]
    js = out[0]["risultato"]["verdetto"]
    grezzo = copy.deepcopy(js)
    for k in CAMPI_CALCOLATI:
        grezzo.pop(k, None)
    for a in grezzo["aree"].values():
        a.pop("rischio", None)
    py = calcola(grezzo, CAT)
    assert {k: py[k] for k in CAMPI} == {k: js[k] for k in CAMPI}


def test_a_esiti_attesi_dal_questionario():
    payload = {"op": "assembla", "catalogo": CATALOGO_LISTA,
               "questionario": json.loads((KIT / "app" / "questionario.json").read_text(encoding="utf-8")),
               "regole": json.loads((KIT / "app" / "analizzatore.json").read_text(encoding="utf-8")),
               "marchi": (KIT / "marchi.txt").read_text(encoding="utf-8")}
    nomi = [n for n in CASI_Q if n.startswith("a_")]
    out = node_esegui({**payload, "casi": [CASI_Q[n] for n in nomi]})
    esiti = {n: (o["risultato"]["verdetto"]["verdetto"], o["risultato"]["verdetto"]["rosso_da_imitazione"])
             for n, o in zip(nomi, out)}
    assert esiti == {"a_b1nance_support_link": ("rosso", True), "a_b1nance_support": ("rosso", True),
                     "a_b1nancebot": ("giallo", False), "a_binance_p2p_alerts": ("giallo", False),
                     "a_wallet_testo": ("giallo", False)}  # sezioni non confermate → mai verde


def test_d_segnalazioni_co_uk_esiti_attesi(risultati_js):
    assert risultati_js["segnalazioni_due_siti_co_uk"]["risultato"]["verdetto"] == "rosso"
    assert risultati_js["segnalazioni_stesso_sito_co_uk"]["risultato"]["rosso_da_segnalazioni"] is False
    assert risultati_js["segnalazioni_senza_schema_stesso_sito"]["risultato"]["rosso_da_segnalazioni"] is False


HOST_DOMINIO = ["a.b.example.com", "news.bbc.co.uk", "forum.example.co.uk", "www.example.com.br",
                "foo.edu.au", "corsi.foo.edu.au", "x.ac.jp", "y.gov.it", "localhost", "192.168.1.10",
                "999.1.1.1", "1.2.3", "::1", "[2001:db8::1]", "Example.COM.", "..a..b.org", "", "it"]


def test_d_parita_dominio_base():
    from rete import dominio_registrabile
    out = node_esegui({"op": "dominio", "casi": HOST_DOMINIO})
    assert [o["risultato"] for o in out] == [dominio_registrabile(h) for h in HOST_DOMINIO]


@pytest.mark.parametrize("nome", list(CASI))
def test_rischio_finale_nella_zona_del_colore(nome):
    r = calcola(copy.deepcopy(CASI[nome]), CAT)
    zona = {"verde": range(0, 31), "giallo": range(31, 61), "rosso": range(61, 101)}[r["verdetto"]]
    assert r["rischio_finale"] in zona, (nome, r["verdetto"], r["rischio_finale"])


@pytest.mark.parametrize("nome,colore", [("totale_30", "verde"), ("totale_31", "giallo"),
                                         ("totale_60", "giallo"), ("totale_61", "rosso")])
def test_rischio_finale_uguale_media_senza_regole(nome, colore):
    r = calcola(copy.deepcopy(CASI[nome]), CAT)
    assert r["verdetto"] == colore and not r["linee_rosse"] and not r["rosso_da_segnalazioni"]
    assert r["rischio_finale"] == r["punteggio_totale"]
