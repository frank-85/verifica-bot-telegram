"""Controllo di un file ricevuto da un bot: impronta, estensione, archivi, Defender.

Il file non viene mai aperto né estratto: si leggono solo i byte per l'impronta
e, per gli zip, l'elenco dei nomi interni.
"""
import hashlib
import subprocess
import zipfile
from pathlib import Path

DEFENDER = Path(r"C:\Program Files\Windows Defender\MpCmdRun.exe")
PERICOLOSE = {".exe", ".scr", ".bat", ".cmd", ".ps1", ".js", ".jse", ".vbs", ".vbe", ".wsf", ".hta",
              ".msi", ".apk", ".lnk", ".jar", ".com", ".pif", ".reg",
              # immagini disco che contengono eseguibili
              ".iso", ".img", ".vhd", ".vhdx",
              # pagine che possono "contrabbandare" file o fingere un login
              ".html", ".htm", ".svg", ".xhtml", ".shtml",
              # documenti con macro (le macro qui NON sono bloccate in automatico)
              ".docm", ".xlsm", ".pptm", ".dotm", ".xltm",
              # altri formati usati negli attacchi
              ".one", ".chm", ".url", ".cpl", ".dll", ".msix", ".appx", ".msp", ".scf", ".xll"}
ESCA = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".jpg", ".jpeg", ".png", ".mp4", ".txt", ".zip"}
ALTRI_ARCHIVI = {".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".cab"}


def _sha256(percorso: Path) -> str:
    h = hashlib.sha256()
    with open(percorso, "rb") as f:
        for blocco in iter(lambda: f.read(1 << 20), b""):
            h.update(blocco)
    return h.hexdigest()


def _defender(percorso: Path, exe: Path) -> str:
    if not exe.is_file():
        return "non_disponibile"
    try:
        r = subprocess.run([str(exe), "-Scan", "-ScanType", "3", "-File", str(percorso),
                            "-DisableRemediation"], capture_output=True, timeout=300)
    except (OSError, subprocess.SubprocessError):
        return "non_disponibile"
    return {0: "pulito", 2: "minaccia"}.get(r.returncode, "non_disponibile")


def analizza_file(percorso: Path, defender: Path | None = None) -> dict:
    percorso = Path(percorso)
    suffissi = [s.lower() for s in percorso.suffixes]
    est = suffissi[-1] if suffissi else ""
    pericolosa = est in PERICOLOSE
    doppia = len(suffissi) >= 2 and suffissi[-2] in ESCA and pericolosa
    try:
        impronta = _sha256(percorso)
    except OSError:
        impronta = None  # lettura negata: di solito è l'antivirus che blocca il file
    out = {"file": percorso.name, "sha256": impronta, "estensione": est,
           "pericolosa": pericolosa, "doppia_estensione": doppia,
           "archivio_con_eseguibili": False}
    if est == ".zip":
        try:
            with zipfile.ZipFile(percorso) as z:
                interni = [Path(n).suffix.lower() for n in z.namelist()]
            out["archivio_con_eseguibili"] = any(s in PERICOLOSE for s in interni)
        except (zipfile.BadZipFile, OSError):
            out["nota"] = "zip illeggibile o danneggiato: contenuto non analizzato"
    elif est in ALTRI_ARCHIVI:
        out["nota"] = f"archivio {est}: contenuto interno non analizzato (solo zip)"
    if impronta is None:
        out["defender"] = "bloccato_in_lettura"
        out["virustotal"] = None
        out["nota"] = "Windows ha negato la lettura del file: di solito significa che l'antivirus lo ha bloccato"
    else:
        out["defender"] = _defender(percorso, Path(defender) if defender else DEFENDER)
        out["virustotal"] = f"https://www.virustotal.com/gui/file/{impronta}"
    segnali = []
    if pericolosa or doppia or out["archivio_con_eseguibili"]:
        segnali.append("file_pericoloso_estensione")
    if out["defender"] in ("minaccia", "bloccato_in_lettura"):
        segnali.append("file_malevolo_defender")
    out["segnali"] = segnali
    return out
