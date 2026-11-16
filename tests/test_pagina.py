import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pagina import analizza_testo, script_esterni  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixture"

# Il campione "incolla questo comando" si costruisce in memoria: scritto su disco
# viene (giustamente) bloccato da Microsoft Defender.
CLICKFIX = ("<html><body><p>Press Win+R, paste and press Enter</p><script>function v(){ "
            "navigator.clipboard." + "writeText('" + "power" + "shell -c ie" + "x(x)'); }"
            "</script></body></html>")


def leggi(nome):
    if nome == "clickfix.html":
        return CLICKFIX
    return (FIX / nome).read_text(encoding="utf-8")


def codici(nome):
    return [s["codice"] for s in analizza_testo(leggi(nome))]


def test_seed():
    assert "pagina_seed_phrase" in codici("seed.html")


def test_clickfix():
    assert "pagina_clickfix" in codici("clickfix.html")


def test_offuscata():
    assert "pagina_offuscata" in codici("offuscata.html")


def test_tonconnect_solo_neutro():
    assert codici("tonconnect.html") == ["wallet_lib_presente"]


def test_pulita():
    assert codici("pulita.html") == []


def test_prova_troncata():
    for nome in ["seed.html", "clickfix.html", "offuscata.html"]:
        for s in analizza_testo(leggi(nome)):
            assert len(s["prova"]) <= 120


def test_parola_seed_in_articolo_senza_input_no():
    testo = "<html><body><p>Non condividere mai la tua seed phrase con nessuno.</p></body></html>"
    assert analizza_testo(testo) == []


def test_codice_emesso_una_volta():
    testo = CLICKFIX * 3
    c = [s["codice"] for s in analizza_testo(testo)]
    assert c.count("pagina_clickfix") == 1


def test_script_esterni():
    html = '<script src="/app.js"></script><script src="https://cdn.evil.xyz/a.js"></script>'
    r = script_esterni(html, "https://esempio.it/")
    assert r["stessa_origine"] == ["https://esempio.it/app.js"]
    assert r["esterni"] == ["cdn.evil.xyz"]
