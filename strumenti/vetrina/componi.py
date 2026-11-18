"""Compone le immagini del README con l'app vera: ogni telefono è un iframe di index.html portato
in automatico a uno stato (guida_scena.html), dentro una cornice; poi Edge senza finestra fotografa la pagina.

    python -I strumenti/vetrina/componi.py      (richiede Pillow e Microsoft Edge)

Bot d'esempio inventati (@Esempio...): nessun bot reale compare nelle immagini pubbliche."""
import subprocess
import sys
from pathlib import Path

from PIL import Image

V = Path(__file__).resolve().parent
KIT = V.parents[1]
USCITA = KIT / "docs" / "immagini"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
sys.path.insert(0, str(KIT))
import costruisci_icone  # noqa: E402

LOGO = costruisci_icone.svg().replace('viewBox="0 0 1 1"', 'viewBox="0 0 1 1" width="{l}" height="{l}"')

BASE_CSS = """
*{box-sizing:border-box} html,body{margin:0;overflow:hidden}
body{font-family:"Segoe UI",system-ui,-apple-system,Roboto,sans-serif;-webkit-font-smoothing:antialiased}
.telefono{position:absolute;width:286px;height:628px;padding:9px;border-radius:44px;background:#0b1220;
  box-shadow:0 0 0 1.5px #2b3a55 inset,0 26px 56px rgba(2,6,23,.42),0 8px 18px rgba(2,6,23,.22)}
.schermo{width:268px;height:610px;border-radius:35px;overflow:hidden;position:relative}
.stato{height:34px;position:relative}
.stato .tacca{position:absolute;top:9px;left:50%;width:84px;height:22px;margin-left:-42px;border-radius:12px;background:#0b1220}
.stato .ora{position:absolute;left:26px;top:11px;font-size:12px;font-weight:700}
.schermo iframe{border:0;width:390px;height:844px;transform:scale(.6872);transform-origin:0 0;display:block}
.vista{height:576px;overflow:hidden}
"""


def telefono(scena, tema, x, y, z=1):
    fondo, inchiostro = ("#0f172a", "#e2e8f0") if tema == "scuro" else ("#ffffff", "#0f172a")
    return (f'<div class="telefono" style="left:{x}px;top:{y}px;z-index:{z}">'
            f'<div class="schermo" style="background:{fondo}"><div class="stato"><span class="ora" style="color:{inchiostro}">9:41</span>'
            f'<div class="tacca"></div></div><div class="vista"><iframe src="scena.html?s={scena}&t={tema}"></iframe></div></div></div>')


TESTI = {
    "it": {"titolo": "Verifica Bot", "sotto": "Il semaforo di affidabilità per bot e Mini App Telegram.",
           "punti": [("#93c5fd", "Regole trasparenti: nessuna AI decide il verdetto"),
                     ("#93c5fd", "Tutto sul tuo dispositivo: niente account, niente dati inviati"),
                     ("#93c5fd", "Installabile come app, funziona anche offline")],
           "piede": "Open source · licenza MIT · gratis",
           "percorso": "Come funziona, in quattro passi",
           "didascalie": ["Domande semplici, solo su ciò che vedi", "Un riepilogo prima dell'esito",
                          "L'esito, con le ragioni e cosa fare", "Regole e pesi pubblici, da verificare"]},
    "en": {"titolo": "Verifica Bot", "sotto": "A trust traffic light for Telegram bots and Mini Apps.",
           "punti": [("#93c5fd", "Transparent rules: no AI decides the verdict"),
                     ("#93c5fd", "Runs on your device: no account, no data sent"),
                     ("#93c5fd", "Installable as an app, works offline")],
           "piede": "Open source · MIT license · free · app in Italian",
           "percorso": "How it works, in four steps",
           "didascalie": ["Simple questions, only about what you see", "A summary before the result",
                          "The result, with reasons and next steps", "Public rules and weights, open to check"]},
}


def vetrina(lingua):
    t = TESTI[lingua]
    punti = "".join(f'<li><span style="background:{c}"></span>{p}</li>' for c, p in t["punti"])
    return f"""<!doctype html><meta charset="utf-8"><style>{BASE_CSS}
body{{width:1600px;height:900px;background:radial-gradient(1200px 700px at 78% 30%,#1e3a8a 0%,rgba(30,58,138,0) 60%),linear-gradient(135deg,#0b1328 0%,#14213d 60%,#172b57 100%);position:relative;color:#fff}}
.testo{{position:absolute;left:80px;top:178px;width:556px}}
.marchio{{display:flex;align-items:center;gap:22px}}
.marchio svg{{border-radius:20px;box-shadow:0 0 0 1.5px rgba(255,255,255,.18)}}
h1{{font-size:64px;font-weight:800;letter-spacing:-.5px;margin:0}}
p.sotto{{font-size:27px;line-height:1.35;color:#cbd5e1;margin:26px 0 34px}}
ul{{list-style:none;padding:0;margin:0}} li{{display:flex;align-items:flex-start;gap:16px;font-size:21px;line-height:1.35;color:#e2e8f0;margin:0 0 16px}}
li span{{margin-top:8px}}
li span{{flex:none;width:14px;height:14px;border-radius:50%;box-shadow:0 0 0 4px rgba(255,255,255,.07)}}
.piede{{margin-top:34px;font-size:18px;color:#94a3b8;letter-spacing:.2px}}
</style><div class="testo"><div class="marchio">{LOGO.format(l=84)}<h1>{t["titolo"]}</h1></div>
<p class="sotto">{t["sotto"]}</p><ul>{punti}</ul><div class="piede">{t["piede"]}</div></div>
{telefono("verde", "chiaro", 662, 160, 1)}{telefono("giallo", "chiaro", 968, 112, 3)}{telefono("rosso", "scuro", 1274, 160, 2)}"""


def percorso(lingua):
    t = TESTI[lingua]
    scene = [("domande", "chiaro"), ("pronto", "chiaro"), ("rosso", "chiaro"), ("come", "scuro")]
    passo, x0 = 376, 93
    tel = "".join(telefono(s, tm, x0 + i * passo, 122) for i, (s, tm) in enumerate(scene))
    did = "".join(f'<div class="did" style="left:{x0 + i * passo}px"><b>{i + 1}</b>{d}</div>'
                  for i, d in enumerate(t["didascalie"]))
    return f"""<!doctype html><meta charset="utf-8"><style>{BASE_CSS}
body{{width:1600px;height:900px;background:linear-gradient(180deg,#f8fafc 0%,#eef2f7 100%);position:relative;color:#0f172a}}
h2{{position:absolute;left:0;right:0;top:44px;text-align:center;font-size:40px;font-weight:800;margin:0;letter-spacing:-.3px}}
.did{{position:absolute;top:772px;width:286px;text-align:center;font-size:19px;line-height:1.35;color:#334155}}
.did b{{display:block;margin:0 auto 8px;width:34px;height:34px;line-height:34px;border-radius:50%;background:#14213d;color:#fff;font-size:17px}}
</style><h2>{t["percorso"]}</h2>{tel}{did}"""


def social():
    t = TESTI["it"]
    return f"""<!doctype html><meta charset="utf-8"><style>{BASE_CSS}
body{{width:1280px;height:640px;background:radial-gradient(900px 600px at 80% 20%,#1e3a8a 0%,rgba(30,58,138,0) 60%),linear-gradient(135deg,#0b1328 0%,#14213d 60%,#172b57 100%);position:relative;color:#fff}}
.testo{{position:absolute;left:72px;top:160px;width:560px}}
.marchio{{display:flex;align-items:center;gap:20px}} .marchio svg{{border-radius:18px}}
h1{{font-size:60px;font-weight:800;margin:0}} p{{font-size:28px;line-height:1.35;color:#cbd5e1;margin:26px 0 0}}
.piede{{margin-top:30px;font-size:20px;color:#94a3b8}}
</style><div class="testo"><div class="marchio">{LOGO.format(l=76)}<h1>{t["titolo"]}</h1></div>
<p>{t["sotto"]}</p><div class="piede">Regole trasparenti · Tutto sul tuo dispositivo · Open source</div></div>
{telefono("verde", "chiaro", 668, 84, 1)}{telefono("rosso", "scuro", 966, 50, 2)}"""


def foto(nome, html, larghezza, altezza, finale):
    pagina = V / f"{nome}.html"
    pagina.write_text(html, encoding="utf-8")
    grezza = V / f"{nome}_2x.png"
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={V / 'profilo'}",
                    "--force-device-scale-factor=2", "--virtual-time-budget=12000",
                    f"--window-size={larghezza},{altezza}", f"--screenshot={grezza}", pagina.as_uri()],
                   check=True, capture_output=True)
    img = Image.open(grezza).convert("RGB")
    assert img.size == (larghezza * 2, altezza * 2), img.size
    if finale[0] != img.size[0]:
        img = img.resize(finale, Image.LANCZOS)
    USCITA.mkdir(parents=True, exist_ok=True)
    img.save(USCITA / f"{nome}.png", optimize=True)
    print(nome, img.size, (USCITA / f"{nome}.png").stat().st_size // 1024, "KB")


def scena():
    """index.html + guida che porta l'app nello stato chiesto da ?s=...&t=..."""
    app = (KIT / "index.html").read_text(encoding="utf-8")
    guida = (V / "guida_scena.html").read_text(encoding="utf-8")
    i = app.rindex("</body>")
    (V / "scena.html").write_text(app[:i] + guida + app[i:], encoding="utf-8")


if __name__ == "__main__":
    scena()
    foto("vetrina", vetrina("it"), 1600, 900, (2000, 1125))
    foto("vetrina-en", vetrina("en"), 1600, 900, (2000, 1125))
    foto("percorso", percorso("it"), 1600, 900, (2000, 1125))
    foto("percorso-en", percorso("en"), 1600, 900, (2000, 1125))
    foto("anteprima-social", social(), 1280, 640, (1280, 640))
