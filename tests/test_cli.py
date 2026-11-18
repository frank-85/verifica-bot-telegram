import json
import subprocess
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))


def cli(*argomenti):
    r = subprocess.run([sys.executable, "-I", str(KIT / "controlli.py"), *argomenti],
                       capture_output=True, cwd=str(KIT))
    return r.returncode, r.stdout.decode("utf-8"), r.stderr.decode("utf-8")


def test_nome_cli():
    codice, out, _ = cli("nome", "@MetamasksAppWebEsempioBot")
    assert codice == 0
    dati = json.loads(out)
    assert "metamask" in {i["marchio"] for i in dati["imitazioni"]}


def test_nuova_crea_cartella(tmp_path):
    codice, out, _ = cli("--radice", str(tmp_path), "nuova", "@ProvaBot")
    assert codice == 0
    cartella = Path(json.loads(out)["cartella"])
    assert cartella.parent == tmp_path / "verifiche"
    assert cartella.name.endswith("_ProvaBot")
    assert (cartella / "scaricati").is_dir()
    v = json.loads((cartella / "verdetto.json").read_text(encoding="utf-8"))
    assert v["versione_schema"] == 1 and v["bot"]["username"] == "ProvaBot"
    assert set(v["aree"]) == {"identita", "promesse", "richieste", "tecnica", "reputazione",
                              "trasparenza"}


def test_nuova_non_sovrascrive(tmp_path):
    _, out, _ = cli("--radice", str(tmp_path), "nuova", "ProvaBot")
    f = Path(json.loads(out)["cartella"]) / "verdetto.json"
    f.write_bytes(b'{"modificato": true}')
    cli("--radice", str(tmp_path), "nuova", "ProvaBot")
    assert json.loads(f.read_text(encoding="utf-8")) == {"modificato": True}


def test_punteggio_scrive_md(tmp_path):
    _, out, _ = cli("--radice", str(tmp_path), "nuova", "ProvaBot")
    cartella = Path(json.loads(out)["cartella"])
    codice, out, err = cli("punteggio", str(cartella / "verdetto.json"))
    assert codice == 0, err
    dati = json.loads(out)
    assert dati["verdetto"] == "giallo" and dati["fiducia_nel_bot"] == "media"
    assert dati["certezza_valutazione"] == "bassa"
    assert (cartella / "resoconto.md").is_file()
    salvato = json.loads((cartella / "verdetto.json").read_text(encoding="utf-8"))
    assert salvato["verdetto"] == "giallo"


def test_punteggio_json_rotto(tmp_path):
    f = tmp_path / "verdetto.json"
    f.write_bytes(b"{ non json")
    codice, _, err = cli("punteggio", str(f))
    assert codice == 1 and "JSON" in err


def test_punteggio_codice_sconosciuto(tmp_path):
    _, out, _ = cli("--radice", str(tmp_path), "nuova", "ProvaBot")
    f = Path(json.loads(out)["cartella"]) / "verdetto.json"
    v = json.loads(f.read_text(encoding="utf-8"))
    v["aree"]["tecnica"]["segnali"].append({"codice": "codice_inventato", "tipo_prova": "diretta",
                                            "testo": "x", "fonte": "y"})
    f.write_bytes(json.dumps(v).encode("utf-8"))
    codice, _, err = cli("punteggio", str(f))
    assert codice == 1 and "codice_inventato" in err


def test_punteggio_file_mancante(tmp_path):
    codice, _, err = cli("punteggio", str(tmp_path / "manca.json"))
    assert codice == 1 and err


def test_output_utf8():
    codice, out, _ = cli("nome", "@CittàPerchéBot")
    assert codice == 0
    assert json.loads(out)["username"] == "CittàPerchéBot"


def test_file_cli(tmp_path):
    p = tmp_path / "foto.pdf.exe"
    p.write_bytes(b"ciao")
    codice, out, _ = cli("file", str(p))
    assert codice == 0
    assert "file_pericoloso_estensione" in json.loads(out)["segnali"]


def test_pagina_url_locale_non_verificato(tmp_path):
    codice, out, _ = cli("pagina", "http://127.0.0.1/", "--cartella", str(tmp_path))
    assert codice == 0
    dati = json.loads(out)
    assert dati["esito"] == "non_verificato" and "dati" not in dati


# --- M1/M7: messaggi d'errore chiari in italiano, mai traceback, exit 1 ---
import shutil  # noqa: E402


def test_link_invito_errore_chiaro(tmp_path):
    codice, out, err = cli("--radice", str(tmp_path), "nuova", "https://t.me/+AbCdEf123")
    assert codice == 1 and out == ""
    assert "invito" in err and "@username" in err


def test_argomenti_sbagliati_exit_1_in_italiano():
    for argomenti in ((), ("comando_inesistente",), ("nome",)):
        codice, out, err = cli(*argomenti)
        assert codice == 1, argomenti
        assert err.startswith("Errore:") and "Uso:" in err, err
        assert "usage:" not in err and "error:" not in err, err


def test_aiuto_resta_disponibile():
    codice, out, _ = cli("--help")
    assert codice == 0 and "nome" in out


def _kit_senza(tmp_path, nome_file):
    kit = tmp_path / "kit"
    shutil.copytree(KIT, kit, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "verifiche",
                                                            "tests", "app", "*.html"))
    (kit / nome_file).unlink()
    return kit


def _cli_in(kit, *argomenti):
    r = subprocess.run([sys.executable, "-I", str(kit / "controlli.py"), *argomenti],
                       capture_output=True, cwd=str(kit))
    return r.returncode, r.stdout.decode("utf-8"), r.stderr.decode("utf-8")


def test_catalogo_mancante_niente_traceback(tmp_path):
    kit = _kit_senza(tmp_path, "segnali.json")
    v = tmp_path / "verdetto.json"
    v.write_bytes(b"{}")
    codice, _, err = _cli_in(kit, "punteggio", str(v))
    assert codice == 1 and "Traceback" not in err
    assert err.startswith("Errore:") and "segnali.json" in err


def test_marchi_mancanti_niente_traceback(tmp_path):
    kit = _kit_senza(tmp_path, "marchi.txt")
    codice, _, err = _cli_in(kit, "nome", "@ProvaBot")
    assert codice == 1 and "Traceback" not in err
    assert err.startswith("Errore:") and "marchi.txt" in err


def test_catalogo_danneggiato_niente_traceback(tmp_path):
    kit = _kit_senza(tmp_path, "segnali.json")
    (kit / "segnali.json").write_bytes(b"[{rotto")
    v = tmp_path / "verdetto.json"
    v.write_bytes(b"{}")
    codice, _, err = _cli_in(kit, "punteggio", str(v))
    assert codice == 1 and "Traceback" not in err and "segnali.json" in err


def test_punteggio_stampa_rischio_finale(tmp_path):
    _, out, _ = cli("--radice", str(tmp_path), "nuova", "ProvaBot")
    f = Path(json.loads(out)["verdetto_json"])
    dati = json.loads(f.read_text(encoding="utf-8"))
    dati["aree"]["richieste"]["segnali"] = [{"codice": "richiesta_seed_o_codici", "tipo_prova": "diretta",
                                            "testo": "chiede la seed", "fonte": "screenshot"}]
    f.write_bytes(json.dumps(dati).encode("utf-8"))
    codice, out, _ = cli("punteggio", str(f))
    r = json.loads(out)
    assert codice == 0 and r["verdetto"] == "rosso" and r["rischio_finale"] == 100
    assert json.loads(f.read_text(encoding="utf-8"))["rischio_finale"] == 100
