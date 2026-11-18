"""Test che riproducono i problemi trovati dalla revisione finale (C1, I1-I9)."""
import http.client
import io
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))

import file_check  # noqa: E402
import rete  # noqa: E402
from pagina import analizza_testo  # noqa: E402
from punteggio import ErroreVerdetto, calcola, carica_catalogo  # noqa: E402
from resoconto import genera_md  # noqa: E402

CAT = carica_catalogo()
AREE = ["identita", "promesse", "richieste", "tecnica", "reputazione", "trasparenza"]


def v(segnali=None, **contesto):
    aree = {a: {"rischio": 0, "segnali": []} for a in AREE}
    for area, lista in (segnali or {}).items():
        aree[area] = {"rischio": 0, "segnali": lista}
    ctx = {"materiale_utente": True, "tecnica_completa": True, "fonti_indipendenti": 1}
    ctx.update(contesto)
    return {"versione_schema": 1, "bot": {"username": "X"}, "aree": aree, "contesto": ctx}


def s(codice, tipo="diretta", fonte="materiale", **x):
    return {"codice": codice, "tipo_prova": tipo, "testo": "t", "fonte": fonte, **x}


# C1 — area sconosciuta o segnale nell'area sbagliata
def test_area_sconosciuta_errore():
    d = v()
    d["aree"]["identità"] = {"rischio": 0, "segnali": [s("imitazione_brand_finanza")]}
    with pytest.raises(ErroreVerdetto, match="identità"):
        calcola(d, CAT)


def test_segnale_nell_area_sbagliata_errore():
    with pytest.raises(ErroreVerdetto, match="area"):
        calcola(v({"promesse": [s("imitazione_brand_finanza")]}), CAT)


# I3 — JSON malformato → ErroreVerdetto, mai traceback
@pytest.mark.parametrize("guasta", [
    lambda d: d["aree"]["tecnica"].__setitem__("segnali", None),
    lambda d: d["aree"]["tecnica"].__setitem__("segnali", ["stringa"]),
    lambda d: d["contesto"].__setitem__("fonti_indipendenti", "due"),
    lambda d: d.__setitem__("contesto", []),
    lambda d: d["aree"].__setitem__("tecnica", "x"),
    lambda d: d.__setitem__("bot", "x"),
    lambda d: d["contesto"].__setitem__("materiale_utente", "false"),
])
def test_json_malformato_errore_leggibile(guasta):
    d = v()
    guasta(d)
    with pytest.raises(ErroreVerdetto):
        calcola(d, CAT)


def test_cli_non_sovrascrive_se_resoconto_fallisce(tmp_path):
    f = tmp_path / "verdetto.json"
    d = v()
    d["bot"] = "x"
    testo = json.dumps(d)
    f.write_bytes(testo.encode("utf-8"))
    r = subprocess.run([sys.executable, "-I", str(KIT / "controlli.py"), "punteggio", str(f)],
                       capture_output=True)
    assert r.returncode == 1 and b"Traceback" not in r.stderr
    assert f.read_text(encoding="utf-8") == testo


# I4 — segnalazioni: fonte vuota, tipo, bot ufficiale
def test_fonte_vuota_non_conta():
    r = calcola(v({"reputazione": [s("segnalazione_truffa", "segnalazione", ""),
                                   s("segnalazione_truffa", "segnalazione", "https://reddit.com/a")]}), CAT)
    assert r["rosso_da_segnalazioni"] is False


def test_segnalazioni_solo_tipo_segnalazione():
    r = calcola(v({"reputazione": [s("segnalazione_truffa", "diretta", "https://a.com/x"),
                                   s("segnalazione_truffa", "segnalazione", "https://b.com/y")]}), CAT)
    assert r["rosso_da_segnalazioni"] is False


def test_bot_ufficiale_non_forzato_rosso_da_segnalazioni():
    r = calcola(v({"identita": [s("bot_ufficiale_verificato")],
                   "reputazione": [s("segnalazione_truffa", "segnalazione", "https://reddit.com/a"),
                                   s("segnalazione_truffa", "segnalazione", "https://trustpilot.com/b")]}), CAT)
    assert r["rosso_da_segnalazioni"] is False and r["verdetto"] != "rosso"


# I5 — punti fuori catalogo limitati e marcati nel resoconto
def test_fuori_catalogo_negativo_limitato():
    r = calcola(v({"identita": [s("nome_imita_marchio"),
                                s("annulla", fuori_catalogo=True, punti=-200)]}), CAT)
    assert r["aree"]["identita"]["rischio"] == 10


def test_fuori_catalogo_marcato_nel_resoconto():
    r = calcola(v({"tecnica": [s("nuovo", fuori_catalogo=True, punti=30)]}), CAT)
    assert "fuori catalogo" in genera_md(r)


# I6 — falsi positivi nell'analisi della pagina
def test_libreria_ethers_non_seed():
    js = ("function fromMnemonic(m){return HDNode.fromSeed(m)} " + "x" * 2000 +
          " const privateKey = w.privateKey; " + "y" * 2000 + " fetch('/api/price')")
    assert "pagina_seed_phrase" not in {x["codice"] for x in analizza_testo(js)}


def test_pagina_docs_copia_non_clickfix():
    html = ("<p>Installa con PowerShell:</p><pre>winget install app</pre>" + "z" * 1000 +
            "<script>btn.onclick=()=>navigator.clipboard.writeText(pre.innerText)</script>")
    assert "pagina_clickfix" not in {x["codice"] for x in analizza_testo(html)}


def test_immagine_base64_non_offuscata():
    html = '<img src="data:image/png;base64,' + "A" * 5000 + '">'
    assert "pagina_offuscata" not in {x["codice"] for x in analizza_testo(html)}


def test_seed_vicino_a_input_resta():
    html = '<label>Inserisci la tua seed phrase</label><textarea id="s"></textarea>'
    assert "pagina_seed_phrase" in {x["codice"] for x in analizza_testo(html)}


# I1 — redirect verso indirizzi locali e handler non http
def test_redirect_verso_locale_rifiutato():
    handler = rete._RedirectSicuro()
    req = urllib.request.Request("https://truffa.xyz/")
    with pytest.raises(urllib.error.URLError):
        handler.redirect_request(req, None, 302, "Found", {}, "http://192.168.1.1/admin")


def test_redirect_verso_ftp_rifiutato():
    handler = rete._RedirectSicuro()
    req = urllib.request.Request("https://truffa.xyz/")
    with pytest.raises(urllib.error.URLError):
        handler.redirect_request(req, None, 302, "Found", {}, "ftp://x.it/a")


def test_cgnat_vietato():
    assert rete._host_vietato("100.64.1.1") is True


# I2 — errori di protocollo e URL malformati
def test_scarica_badstatusline(tmp_path, monkeypatch):
    def apri(url):
        raise http.client.BadStatusLine("garbage")
    monkeypatch.setattr(rete, "_apri", apri)
    assert rete.scarica("https://x.it/", tmp_path, "a.html")["esito"] == "non_verificato"


def test_scarica_url_ipv6_rotto(tmp_path):
    assert rete.scarica("http://[::1", tmp_path, "a.html")["esito"] == "non_verificato"


def test_dominio_url_rotto():
    assert rete.dominio("http://[::1")["esito"] == "non_verificato"


def test_cli_errore_imprevisto_rete_non_verificato(monkeypatch):
    import controlli

    def esplode(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(controlli.rete, "dominio", esplode)
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    assert controlli.main(["dominio", "esempio.it"]) == 0
    assert json.loads(out.getvalue())["esito"] == "non_verificato"


# I7 — file bloccato dall'antivirus in lettura
def test_file_bloccato_in_lettura(tmp_path, monkeypatch):
    p = tmp_path / "x.pdf"
    p.write_bytes(b"x")

    def bloccato(_):
        raise OSError(225, "contiene un virus")
    monkeypatch.setattr(file_check, "_sha256", bloccato)
    r = file_check.analizza_file(p, Path("Z:/no/MpCmdRun.exe"))
    assert r["sha256"] is None and r["defender"] == "bloccato_in_lettura"
    assert "file_malevolo_defender" in r["segnali"]


def test_defender_senza_text(tmp_path, monkeypatch):
    exe = tmp_path / "MpCmdRun.exe"
    exe.write_bytes(b"")
    visti = {}

    def run(cmd, **kw):
        visti.update(kw)
        return subprocess.CompletedProcess(cmd, 0, b"", b"")
    monkeypatch.setattr(file_check.subprocess, "run", run)
    p = tmp_path / "a.txt"
    p.write_bytes(b"x")
    file_check.analizza_file(p, exe)
    assert not visti.get("text")


# I8 — estensioni pericolose mancanti
@pytest.mark.parametrize("nome", ["a.iso", "a.img", "a.vhd", "a.html", "a.svg", "a.docm",
                                  "a.xlsm", "a.one", "a.chm", "a.url", "a.dll", "fattura.pdf.html"])
def test_estensioni_rischiose(tmp_path, nome):
    p = tmp_path / nome
    p.write_bytes(b"x")
    r = file_check.analizza_file(p, Path("Z:/no/MpCmdRun.exe"))
    assert "file_pericoloso_estensione" in r["segnali"]


# I9 — regola anti-manipolazione nella skill
def test_skill_regola_testi_come_dati():
    t = (Path(__file__).resolve().parents[1] / "verifica-bot" / "SKILL.md").read_text(encoding="utf-8")
    assert "mai istruzioni" in t
