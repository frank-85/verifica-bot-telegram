"""App installabile (PWA, 18/11/2026): scheda dell'app, icone, gestore offline, privacy."""
import json
import re
import struct
import sys
from pathlib import Path

import pytest

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))

import costruisci_app  # noqa: E402
import costruisci_icone  # noqa: E402


@pytest.fixture(scope="module")
def generato(tmp_path_factory):
    uscita = tmp_path_factory.mktemp("app") / "index.html"
    return costruisci_app.costruisci(KIT, uscita, numero_test=1).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def manifest():
    return json.loads((KIT / "manifest.webmanifest").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sw():
    return (KIT / "sw.js").read_text(encoding="utf-8")


def _misure_png(percorso: Path) -> tuple[int, int]:
    dati = percorso.read_bytes()
    assert dati[:8] == b"\x89PNG\r\n\x1a\n", percorso
    return struct.unpack(">II", dati[16:24])


def test_manifest_campi_essenziali(manifest):
    assert manifest["name"] == "Verifica Bot" and manifest["short_name"] == "Verifica Bot"
    assert manifest["lang"] == "it" and manifest["display"] == "standalone"
    assert manifest["start_url"] == "./" and manifest["scope"] == "./"
    assert re.fullmatch(r"#[0-9a-f]{6}", manifest["theme_color"]) and re.fullmatch(r"#[0-9a-f]{6}", manifest["background_color"])
    assert manifest["id"] == "./"


def test_manifest_icone_esistono_con_le_misure_dichiarate(manifest):
    scopi = set()
    for icona in manifest["icons"]:
        percorso = KIT / icona["src"]
        assert percorso.exists(), icona["src"]
        if icona["type"] == "image/png":
            lato = int(icona["sizes"].split("x")[0])
            assert _misure_png(percorso) == (lato, lato), icona["src"]
        scopi.add(icona.get("purpose", "any"))
    assert {"any", "maskable"} <= scopi
    lati = {i["sizes"] for i in manifest["icons"] if i["type"] == "image/png"}
    assert {"192x192", "512x512"} <= lati  # minimi richiesti da Chrome per l'installazione


def test_icone_rigenerabili_e_coerenti():
    # l'SVG pubblicato è esattamente quello prodotto dal disegno unico
    assert (KIT / "icone" / "icona.svg").read_text(encoding="utf-8") == costruisci_icone.svg()
    assert _misure_png(KIT / "icone" / "apple-touch-icon.png") == (180, 180)
    assert _misure_png(KIT / "icone" / "icona-32.png") == (32, 32)


def test_logo_nella_testata_uguale_all_icona(generato):
    forma = re.search(r'<path d="([^"]+)"', costruisci_icone.svg()).group(1)
    testata = generato[generato.index('<header class="testata">'):generato.index("</header>")]
    assert forma in testata and 'aria-hidden="true"' in testata


def test_head_collega_manifest_e_icone(generato):
    testa = generato[:generato.index("</head>")]
    for riga in ('<link rel="manifest" href="manifest.webmanifest">',
                 '<link rel="icon" href="icone/icona.svg" type="image/svg+xml">',
                 '<link rel="apple-touch-icon" href="icone/apple-touch-icon.png">',
                 '<meta name="theme-color" content="#14213d">'):
        assert riga in testa, riga


def test_csp_apre_solo_lo_stesso_sito(generato):
    csp = re.search(r'Content-Security-Policy" content="([^"]+)"', generato).group(1)
    regole = dict((r.split(" ", 1) + [""])[:2] for r in (x.strip() for x in csp.split(";")))
    assert regole["default-src"] == "'none'"
    assert regole["manifest-src"] == "'self'"
    assert regole["worker-src"].split()[0] == "'self'"
    assert regole["img-src"].split()[0] == "'self'"
    assert "'self'" not in regole["connect-src"] and "'self'" not in regole["script-src"]


def test_registrazione_solo_su_https(generato):
    assert 'location.protocol === "https:"' in generato
    assert 'navigator.serviceWorker.register("sw.js")' in generato


def test_sw_salva_solo_file_dello_stesso_sito(sw):
    assert "url.origin !== self.location.origin" in sw  # la libreria esterna passa senza essere salvata
    assert 'req.method !== "GET"' in sw
    assert "res.ok" in sw and 'res.type === "basic"' in sw
    for vietato in ("indexedDB", "localStorage", "postMessage", "importScripts", "cdn.jsdelivr"):
        assert vietato not in sw, vietato


def test_sw_precarica_file_esistenti(sw):
    elenco = re.search(r"const FILE = \[(.*?)\];", sw, re.S).group(1)
    for f in re.findall(r'"\./([^"]*)"', elenco):
        assert f == "" or (KIT / f).exists(), f


def test_sw_salvataggio_protetto_e_timeout_sulle_pagine(sw):
    assert "event.waitUntil(" in sw[sw.index('addEventListener("fetch"'):]  # il salvataggio non viene interrotto
    assert "ATTESA_RETE_MS = 4000" in sw and "setTimeout" in sw  # rete lenta: dopo 4 s la copia salvata


def test_sw_offline_ricade_sulla_pagina(sw):
    assert 'req.mode === "navigate"' in sw and 'caches.match("./index.html")' in sw
    assert "caches.delete" in sw  # le versioni vecchie vengono rimosse


def test_privacy_dichiara_la_copia_del_solo_codice(generato):
    piatto = re.sub(r"</?(strong|em)>", "", generato)
    # revisione 18/11: la copia nasce alla prima visita dal sito, non solo installando l'app
    assert "quando apri la pagina dal sito, il browser conserva una copia del solo codice dell'app" in piatto
    assert "non vengono mai conservati" in piatto and "cancellando i dati del sito" in piatto
    assert "disinstallando l'app" not in piatto


def test_garanzia_tecnica_aggiornata(generato):
    assert "diverso da quello della libreria di lettura." not in generato
    assert "oltre alla pagina stessa" in generato


def test_pulsante_installa_solo_quando_il_browser_lo_offre(generato):
    assert 'id="installa"' in generato and "hidden" in generato[generato.index('id="installa"') - 80:generato.index('id="installa"') + 80]
    assert '"beforeinstallprompt"' in generato and '"appinstalled"' in generato


def test_come_funziona_spiega_l_installazione(generato):
    assert "Installala sul telefono" in generato and "Aggiungi alla schermata Home" in generato


def test_gitignore_pubblica_icone_e_immagini():
    righe = (KIT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "!icone/*.png" in righe and "!docs/immagini/*.png" in righe
    assert righe.index("!icone/*.png") > righe.index("*.png")  # l'eccezione deve venire dopo la regola


# --- conferma dopo l'installazione (18/11/2026): niente dubbi su "l'ho installata davvero?" ---

def _blocco_installa(generato):
    return generato[generato.index("var appAperta"):generato.index('window.addEventListener("appinstalled"')]


def test_installata_mostra_la_conferma(generato):
    assert "Fatto: Verifica Bot è tra le app del dispositivo." in generato
    assert "puoi aprirla dalla sua icona" in generato
    assert 'aria-live="polite"' in generato[generato.index('id="installa"') - 80:generato.index('id="installa"') + 120]
    blocco = _blocco_installa(generato)
    assert 'scelta.outcome === "accepted"' in blocco and "installata()" in blocco


def test_dentro_l_app_installata_nessun_invito(generato):
    assert '"(display-mode: standalone)"' in generato and "navigator.standalone === true" in generato
    blocco = _blocco_installa(generato)
    assert "if (appAperta) return;" in blocco
