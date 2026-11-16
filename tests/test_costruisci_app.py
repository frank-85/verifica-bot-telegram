"""Controlli sul file unico generato: privacy, sicurezza, linguaggio, dati incorporati."""
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))

import costruisci_app  # noqa: E402

CSP = ("default-src 'none'; script-src 'unsafe-inline' 'wasm-unsafe-eval' https://cdn.jsdelivr.net blob:; "
       "style-src 'unsafe-inline'; img-src data: blob:; connect-src https://cdn.jsdelivr.net blob: data:; "
       "worker-src blob: https://cdn.jsdelivr.net; font-src 'none'; form-action 'none'; base-uri 'none'")
FRASI_VIETATE = ["è una truffa", "truffatore", "truffatori", "è uno scam", "scammer"]


@pytest.fixture(scope="module")
def generato(tmp_path_factory):
    uscita = tmp_path_factory.mktemp("app") / "VERIFICA_BOT_APP.html"
    percorso = costruisci_app.costruisci(KIT, uscita, numero_test=123)
    return percorso.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def dati(generato):
    m = re.search(r'<script type="application/json" id="dati">(.*?)</script>', generato, re.S)
    assert m, "manca il blocco dati"
    return json.loads(m.group(1).replace("<\\/", "</"))


def _testi_propri() -> str:
    return "\n".join((KIT / "app" / f).read_text(encoding="utf-8")
                     for f in ("modello.html", "questionario.json", "analizzatore.json"))


def test_csp_esatto(generato):
    assert f'<meta http-equiv="Content-Security-Policy" content="{CSP}">' in generato


@pytest.mark.parametrize("vietato", ["localStorage", "sessionStorage", "indexedDB", "document.cookie",
                                     "geolocation", "innerHTML", 'type="email"', 'type="tel"', "outerHTML",
                                     "insertAdjacentHTML", "document.write", "eval("])
def test_nessuna_api_vietata(generato, vietato):
    assert vietato not in generato


def test_nessuna_risorsa_esterna_statica(generato):
    assert not re.search(r'\bsrc="https?:', generato)
    assert not re.search(r"<link\b", generato)


def test_francesco_solo_nella_firma(generato):
    senza_chiavi = generato.replace("materiale_utente", "")
    occorrenze = [m.start() for m in re.finditer(r"Francesco", senza_chiavi)]
    assert len(occorrenze) == 1
    assert "Francesco Guerra" in senza_chiavi


def test_firma_link(generato):
    assert 'href="https://www.linkedin.com/in/frguerra/"' in generato
    assert 'href="https://github.com/frank-85"' in generato


def test_nessuna_email_nella_pagina(generato):
    pulito = generato.replace("@media", "").replace("tesseract.js@5.1.1", "")
    assert not re.search(r"[\w.+-]+@[\w-]+\.[a-z]{2,}\b", pulito)


@pytest.mark.parametrize("frase", FRASI_VIETATE)
def test_linguaggio_prudente(frase):
    assert frase not in _testi_propri().lower()


def test_dati_completi(dati):
    for k in ("catalogo", "marchi", "questionario", "regole", "generato", "numero_test"):
        assert k in dati, k
    assert dati["numero_test"] == 123
    assert len(dati["catalogo"]) == 37


def test_codice_inventato_nel_questionario_blocca(tmp_path):
    kit = tmp_path / "kit"
    shutil.copytree(KIT, kit, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "scaricati"))
    q = json.loads((kit / "app" / "questionario.json").read_text(encoding="utf-8"))
    q["aree"][0]["domande"][0]["codice"] = "codice_inventato"
    (kit / "app" / "questionario.json").write_bytes(json.dumps(q, ensure_ascii=False).encode("utf-8"))
    with pytest.raises(SystemExit, match="codice_inventato"):
        costruisci_app.costruisci(kit, tmp_path / "x.html")


def test_nomi_globali_js_non_si_scontrano():
    visti = {}
    for f in costruisci_app.ORDINE_JS:
        testo = (KIT / "app" / f).read_text(encoding="utf-8")
        for nome in re.findall(r"^(?:var|function|class|let|const)\s+([A-Za-z_$][\w$]*)", testo, re.M):
            assert nome not in visti, f"{nome} definito sia in {visti[nome]} sia in {f}"
            visti[nome] = f


TESTI_OBBLIGATORI = [
    "Nessun segnale di rischio rilevante", "Alcuni segnali di rischio", "Segnali di rischio gravi",
    "Fiducia nel bot", "Certezza della valutazione", "Basata su",
    "Questo strumento aiuta a riconoscere", "nessuno strumento di questo tipo può offrire garanzie assolute",
    "Dove vanno i tuoi dati? Da nessuna parte.",
    "progettato e sviluppato con l'assistenza di strumenti di intelligenza artificiale",
    "I pareri dello strumento sono", "non sono coinvolti",
    "Stampa / salva PDF", "Scarica verdetto.json", "@media print",
]


@pytest.mark.parametrize("testo", TESTI_OBBLIGATORI)
def test_testi_obbligatori(generato, testo):
    piatto = re.sub(r"</?(strong|em)>", "", generato)
    assert testo in piatto


TESSERACT = "https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js"


def test_tesseract_solo_dentro_leggi_screenshot(generato):
    assert generato.count(TESSERACT) == 1
    pos = generato.index(TESSERACT)
    inizio = generato.rfind("function leggiScreenshot", 0, pos)
    assert inizio >= 0 and "\nfunction " not in generato[inizio + 10:pos]


@pytest.mark.parametrize("testo", ["Ho letto", "Hai aperto anche le sezioni prelievo / pagamenti / inviti?",
                                   "il browser scarica una volta la libreria"])
def test_testi_prova_tu(generato, testo):
    assert testo in re.sub(r"</?(strong|em)>", "", generato)


def test_grafico_aree_in_html_non_svg(generato):
    assert 'classe: "barra-area"' in generato
    assert "createElementNS" not in generato


def test_revisione_tesseract_senza_cache(generato):
    assert 'cacheMethod: "none"' in generato


def test_revisione_segnalazioni_non_verificate(generato):
    assert "non verificate dallo strumento" in generato


def test_revisione_report_autovalutazione_disinnesca_sempre(generato):
    assert "sempre: autoval" in generato


def test_app_mostra_rischio_finale(generato, dati):
    # il KPI e le schede dei casi mostrano il rischio finale, non la media
    assert generato.count("function rischioFinale(v)") == 1  # una sola definizione, in aspetto.js
    assert 'rischioFinale(v) + "/100' in generato
    assert 'classe: "valore", testo: v.punteggio_totale' not in generato and '"Rischio " + v.punteggio_totale' not in generato
    assert "Media delle 6 aree" in generato


# ---------- restyling B2 (Task 2): sistema visivo, esito, tema ----------

def _css(generato: str) -> str:
    return re.search(r"<style>(.*?)</style>", generato, re.S).group(1)


def test_b2_tema_scuro_automatico_e_manuale(generato):
    css = _css(generato)
    assert ':root[data-theme="dark"]' in css
    assert re.search(r'@media \(prefers-color-scheme: dark\) \{\s*:root:not\(\[data-theme="light"\]\)', css)


@pytest.mark.parametrize("riga", [
    "#ffffff", "#f8fafc", "#e2e8f0", "#0f172a", "#475569", "#14213d", "#1d4ed8",
    "#15803d", "#a16207", "#b91c1c", "#ecfdf3", "#fef7e0", "#fdeceb", "#166534", "#854d0e", "#991b1b",
    "#111827", "#0b1220", "#1f2937", "#374151", "#94a3b8", "#93c5fd",
    "#4ade80", "#facc15", "#f87171", "#0f2a1c", "#2a2410", "#2d1517",
])
def test_b2_palette_della_spec(generato, riga):
    assert riga in _css(generato)


def test_b2_niente_oro(generato):
    assert "--oro" not in generato
    for vecchio in ("#a87a1f", "#e2b552", "#f3e6c4", "#f6f3ec"):
        assert vecchio not in generato


def test_b2_movimento_ridotto(generato):
    css = _css(generato)
    assert "prefers-reduced-motion" in css
    assert "@keyframes" in css


def test_b2_selettore_tema(generato):
    for chiave, testo in (("auto", "Automatico"), ("chiaro", "Chiaro"), ("scuro", "Scuro")):
        assert re.search(r'<button type="button" data-tema="%s" aria-pressed="(true|false)">%s</button>' % (chiave, testo),
                         generato), testo
    assert generato.count(' aria-pressed="true">') == 1  # un solo pulsante attivo: il predefinito, Automatico
    assert 'data-tema="auto" aria-pressed="true"' in generato
    assert 'removeAttribute("data-theme")' in generato
    assert 'setAttribute("data-theme"' in generato
    assert "temaEffettivo(" in generato.split("function temaEffettivo(")[1]  # usata, non ridefinita
    assert generato.count("function temaEffettivo(") == 1


def test_b2_tre_forme_distinte(generato):
    forme = re.findall(r'<svg class="forma t-(verde|giallo|rosso)" data-forma="(cerchio|triangolo|ottagono)"', generato)
    assert sorted(forme) == [("giallo", "triangolo"), ("rosso", "ottagono"), ("verde", "cerchio")]
    assert "<circle" in generato and generato.count('class="forma-simbolo"') >= 3


def test_b2_barra_del_rischio(generato):
    assert 'classe: "barra-rischio", role: "img"' in generato
    assert '"aria-label": "Rischio " + n + " su 100, zona "' in generato
    assert '"left:" + posizioneIndicatore(n) + "%"' in generato
    assert "var n = rischioFinale(v);" in generato
    assert "zonaRischio(n)" in generato
    for etichetta in ("basso", "medio", "alto"):
        assert 'testo: "%s"' % etichetta in generato


def test_b2_esito_note_e_ordine(generato):
    for testo in ("Verde · non è una garanzia", '"Giallo · "', '"Rosso · "', "notaProssimita(v)", "motivoRegola(v)",
                  "Rischio complessivo", "Media delle 6 aree: "):
        assert testo in generato, testo
    for funzione in ("rischioFinale", "zonaRischio", "posizioneIndicatore", "notaProssimita", "motivoRegola"):
        assert generato.count("function %s(" % funzione) == 1, funzione
    corpo = generato[generato.index("function mostraReport("):generato.index("window.mostraReport")]
    ordine = ['classe: "esito t-"', "barraRischio(v)", 'classe: "chips"', "notaRegola(v)", '"Cosa fare"',
              '"Rischio per area"', '"Non verificato"', '"Fonti"', '"Stampa / salva PDF"', 'modello("t-premessa")']
    posizioni = [corpo.index(x) for x in ordine]
    assert posizioni == sorted(posizioni), list(zip(ordine, posizioni))
    assert 'el("details", { classe: "card dettaglio-aree"' in corpo


# ---------- restyling B2 (Task 3): percorso a passi e scheda Come funziona ----------

def _blocchi_media(css: str, condizione: str) -> str:
    """Contenuto di tutti i blocchi @media con quella condizione (parentesi bilanciate)."""
    trovati, intestazione = [], "@media %s {" % condizione
    inizio = css.find(intestazione)
    while inizio >= 0:
        i, livello = inizio + len(intestazione), 1
        while livello and i < len(css):
            livello += {"{": 1, "}": -1}.get(css[i], 0)
            i += 1
        trovati.append(css[inizio + len(intestazione):i - 1])
        inizio = css.find(intestazione, i)
    return "\n".join(trovati)


def test_b2_barra_azioni_fissa_su_schermi_stretti(generato):
    css = _css(generato)
    stretto = _blocchi_media(css, "(max-width: 640px)")
    assert re.search(r"\.azioni-fisse \{[^}]*position: fixed", stretto)
    assert "env(safe-area-inset-bottom)" in stretto
    assert re.search(r"body\.con-barra \{[^}]*padding-bottom", stretto)  # il contenuto non finisce sotto la barra
    fuori = css.replace(stretto, "")
    assert "position: fixed" not in fuori  # su PC la barra resta sotto il contenuto
    assert 'classe: "azioni azioni-fisse"' in generato
    assert '"con-barra"' in generato


def test_b2_avanzamento_con_nome_del_passo(generato):
    assert 'classe: "passo-nome"' in generato
    assert "nomePasso(p)" in generato and generato.count("function nomePasso(") == 1
    corpo = generato[generato.index("function nomePasso("):generato.index("function passoPremessa(")]
    for nome in ('"Identificazione del bot"', '"Materiale del bot"', '"Controlli finali"', ".titolo"):
        assert nome in corpo, nome
    assert '"Passo " + p + " di " + ULTIMO' in generato


def test_b2_risposte_radio_dentro_etichette_pulsante(generato):
    corpo = generato[generato.index("function scelta("):generato.index("function nomePasso(")]
    assert 'el("input", { type: "radio", name: nome, value: o[0] })' in corpo
    assert 'el("label", { classe: "pillola" }, r, ' in corpo
    assert 'role: "radiogroup"' in corpo
    for testo in ('["si", "Sì"]', '["no", "No"]', '["nonso", "Non so"]'):
        assert testo in generato, testo
    css = _css(generato)
    assert re.search(r"\.pillola span \{[^}]*min-height: 4[4-9]px", css)
    assert ".pillola input:checked + span" in css
    assert ".pillola input:focus-visible + span" in css
    regola = re.search(r"\.pillola input \{([^}]*)\}", css).group(1)
    assert "display: none" not in regola and "visibility: hidden" not in regola  # nascosto alla vista, non alla tastiera


def test_b2_avviso_screenshot_rete_mobile(generato):
    corpo = generato[generato.index("function passoMateriale("):generato.index("function passoArea(")]
    assert re.search(r'"[^"]*rete mobile[^"]*incolla il testo[^"]*"', corpo)
    assert corpo.index("rete mobile") < corpo.index("corpo.appendChild(file)")  # l'avviso precede la scelta dei file


def test_b2_stati_degli_screenshot(generato):
    corpo = generato[generato.index("function elencoScreenshot("):generato.index("function passoMateriale(")]
    for stato in ('"lettura in corso"', '"letto"', '"errore"'):
        assert stato in corpo, stato
    assert 'classe: "rotella"' in corpo  # indicatore animato della lettura
    assert "nessun testo riconosciuto" in corpo and " caratteri" in corpo
    css = _css(generato)
    movimento = _blocchi_media(css, "(prefers-reduced-motion: no-preference)")
    assert re.search(r"\.rotella \{[^}]*animation", movimento)  # gira solo se il movimento è gradito


def test_b2_leggi_screenshot_invariata(generato):
    inizio = generato.index("function leggiScreenshot(file) {")
    corpo = generato[inizio:generato.index("/* ---------- Prova tu: percorso a passi", inizio)]
    assert "120000" in corpo and 'recognize(file, "ita+eng", { cacheMethod: "none" })' in corpo
    assert "Impossibile scaricare la libreria di lettura (verifica la connessione a internet)." in corpo
    assert "La lettura richiede più tempo del previsto." in corpo


def test_b2_passo_zero_benefici_e_avvertenze_visibili(generato):
    corpo = generato[generato.index("function passoPremessa("):generato.index("function passoBot(")]
    assert "Verifica l'affidabilità di un bot o di una Mini App Telegram" in corpo
    assert 'classe: "benefici"' in corpo and corpo.count('beneficio("') == 3
    assert 'el("div", { classe: "avvertenze" }, modello("t-premessa"))' in corpo  # per intero, non ripiegate
    assert 'el("summary", { testo: "Privacy e dati in breve" }), modello("t-privacy")' in corpo
    assert corpo.index('classe: "benefici"') < corpo.index('modello("t-premessa")') < corpo.index("Privacy e dati in breve")


def test_b2_tabelle_come_funziona_scorrono_solo_dentro(generato):
    css = _css(generato)
    assert re.search(r"\.tabella-scroll \{[^}]*overflow-x: auto", css)
    corpo = generato[generato.index("function mostraCome("):generato.index("/* ---------- Prova tu: lettura screenshot")]
    assert corpo.count("el(\"table\"") == corpo.count("tabellaScorrevole(") == 2
    assert 'el("ol", { classe: "passi" }' in corpo


def test_b2_nota_linea_rossa_senza_descrizione_ripetuta(generato):
    # la descrizione della linea rossa sta nel riquadro "Linee rosse": la nota non la ripete
    assert 'testo: "Linea rossa: " + (CAT[' not in generato
    assert "Prevale una linea rossa" in generato


def test_b2_barre_aree_neutre_tranne_area_piena(generato):
    # i colori del semaforo restano all'esito: le barre delle aree sono neutre, rosse solo da 80 in su
    assert '"var(--verde)"' not in generato and 'r > SOGLIE.verde ? "var(--ambra)"' not in generato
    assert 'r >= SOGLIE.areaPiena ? "var(--rosso)" : "var(--secondario)"' in generato
    assert "impedisce l'esito verde" in generato


def test_nessun_caso_reale_incorporato(generato, dati):
    # versione pubblica: nessuna verifica gia' svolta su bot reali dentro la pagina
    assert "verdetti" not in dati
    assert "Casi reali" not in generato and 'data-scheda="casi"' not in generato
