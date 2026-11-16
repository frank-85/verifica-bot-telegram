import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import file_check  # noqa: E402
from file_check import analizza_file  # noqa: E402

NESSUN_DEFENDER = Path("Z:/non/esiste/MpCmdRun.exe")


def crea(tmp_path, nome, dati=b"ciao"):
    p = tmp_path / nome
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(dati)
    return p


def test_hash_noto(tmp_path):
    r = analizza_file(crea(tmp_path, "a.txt"), NESSUN_DEFENDER)
    assert r["sha256"] == "b133a0c0e9bee3be20163d2ad31d6248db292aa6dcb1ee087a2aa50e0fc75ae2"
    assert r["virustotal"].endswith(r["sha256"])
    assert r["segnali"] == []


def test_doppia_estensione(tmp_path):
    r = analizza_file(crea(tmp_path, "fattura.pdf.exe"), NESSUN_DEFENDER)
    assert r["doppia_estensione"] is True and r["pericolosa"] is True
    assert r["segnali"] == ["file_pericoloso_estensione"]


def test_zip_con_exe(tmp_path):
    p = tmp_path / "pacchetto.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("leggimi.txt", "x")
        z.writestr("setup.exe", "MZ")
    r = analizza_file(p, NESSUN_DEFENDER)
    assert r["archivio_con_eseguibili"] is True
    assert "file_pericoloso_estensione" in r["segnali"]


def test_zip_pulito(tmp_path):
    p = tmp_path / "foto.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("a.jpg", "x")
    r = analizza_file(p, NESSUN_DEFENDER)
    assert r["archivio_con_eseguibili"] is False and r["segnali"] == []


def test_defender_assente(tmp_path):
    r = analizza_file(crea(tmp_path, "a.txt"), NESSUN_DEFENDER)
    assert r["defender"] == "non_disponibile" and len(r["sha256"]) == 64


def _defender_finto(monkeypatch, tmp_path, codice):
    exe = crea(tmp_path, "MpCmdRun.exe", b"")
    visti = []

    def run(cmd, **kw):
        visti.append(cmd)
        return subprocess.CompletedProcess(cmd, codice, "", "")
    monkeypatch.setattr(file_check.subprocess, "run", run)
    return exe, visti


def test_defender_minaccia(tmp_path, monkeypatch):
    exe, visti = _defender_finto(monkeypatch, tmp_path, 2)
    r = analizza_file(crea(tmp_path, "doc.pdf"), exe)
    assert r["defender"] == "minaccia"
    assert "file_malevolo_defender" in r["segnali"]
    assert "-DisableRemediation" in visti[0]


def test_defender_pulito(tmp_path, monkeypatch):
    exe, _ = _defender_finto(monkeypatch, tmp_path, 0)
    assert analizza_file(crea(tmp_path, "doc.pdf"), exe)["defender"] == "pulito"


def test_percorso_con_spazi_e_accenti(tmp_path):
    r = analizza_file(crea(tmp_path, "cartella prova/perché.txt"), NESSUN_DEFENDER)
    assert r["estensione"] == ".txt" and len(r["sha256"]) == 64


def test_rar_non_analizzato(tmp_path):
    r = analizza_file(crea(tmp_path, "x.rar"), NESSUN_DEFENDER)
    assert "nota" in r
