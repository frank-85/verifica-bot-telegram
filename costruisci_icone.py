"""Genera le icone dell'app installabile (PWA): scudo con semaforo su fondo blu notte.

Un solo disegno, descritto in coordinate da 0 a 1, produce sia l'SVG sia i PNG,
così le due versioni non possono divergere. Richiede Pillow solo per i PNG:
    python -I costruisci_icone.py
"""
from pathlib import Path

KIT = Path(__file__).resolve().parent
CARTELLA = KIT / "icone"

FONDO = "#14213d"      # blu notte della firma dell'app
SCUDO = "#f8fafc"
LUCI = ("#dc2626", "#f59e0b", "#16a34a")  # rosso in alto, ambra, verde in basso (come un semaforo)

# Scudo: punti e curve quadratiche in coordinate 0-1 (q = controllo, p = arrivo).
INIZIO = (0.5, 0.15)
TRATTI = [("q", (0.62, 0.235), (0.77, 0.245)),
          ("l", None, (0.77, 0.50)),
          ("q", (0.75, 0.74), (0.5, 0.87)),
          ("q", (0.25, 0.74), (0.23, 0.50)),
          ("l", None, (0.23, 0.245)),
          ("q", (0.38, 0.235), (0.5, 0.15))]
CENTRI_Y = (0.335, 0.49, 0.645)
RAGGIO = 0.062


def _trasforma(x, y, scala, margine):
    """Riduce il disegno verso il centro (per l'icona 'maskable' con zona sicura)."""
    return margine + x * scala, margine + y * scala


def svg(scala=1.0, margine=0.0, angoli=0.22) -> str:
    t = lambda p: _trasforma(p[0], p[1], scala, margine)
    x0, y0 = t(INIZIO)
    d = [f"M{x0:.4f} {y0:.4f}"]
    for tipo, c, p in TRATTI:
        px, py = t(p)
        if tipo == "l":
            d.append(f"L{px:.4f} {py:.4f}")
        else:
            cx, cy = t(c)
            d.append(f"Q{cx:.4f} {cy:.4f} {px:.4f} {py:.4f}")
    luci = "".join(f'<circle cx="{t((0.5, y))[0]:.4f}" cy="{t((0.5, y))[1]:.4f}" r="{RAGGIO * scala:.4f}" fill="{c}"/>'
                   for y, c in zip(CENTRI_Y, LUCI))
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1">'
            f'<rect width="1" height="1" rx="{angoli}" fill="{FONDO}"/>'
            f'<path d="{" ".join(d)}Z" fill="{SCUDO}"/>{luci}</svg>\n')


def _punti_scudo(lato, scala, margine, passi=48):
    pt = [INIZIO]
    for tipo, c, p in TRATTI:
        a = pt[-1]
        if tipo == "l":
            pt.append(p)
            continue
        for i in range(1, passi + 1):
            s = i / passi
            pt.append(((1 - s) ** 2 * a[0] + 2 * (1 - s) * s * c[0] + s * s * p[0],
                       (1 - s) ** 2 * a[1] + 2 * (1 - s) * s * c[1] + s * s * p[1]))
    return [tuple(v * lato for v in _trasforma(x, y, scala, margine)) for x, y in pt]


def png(lato, percorso, scala=1.0, margine=0.0, angoli=0.22):
    from PIL import Image, ImageDraw
    grande = lato * 8  # disegno sovracampionato, poi ridotto: bordi lisci a ogni misura
    img = Image.new("RGBA", (grande, grande), (0, 0, 0, 0))
    g = ImageDraw.Draw(img)
    g.rounded_rectangle((0, 0, grande - 1, grande - 1), radius=int(angoli * grande), fill=FONDO)
    g.polygon(_punti_scudo(grande, scala, margine), fill=SCUDO)
    for y, colore in zip(CENTRI_Y, LUCI):
        cx, cy = (v * grande for v in _trasforma(0.5, y, scala, margine))
        r = RAGGIO * scala * grande
        g.ellipse((cx - r, cy - r, cx + r, cy + r), fill=colore)
    img.resize((lato, lato), Image.LANCZOS).save(percorso, optimize=True)


def main():
    CARTELLA.mkdir(exist_ok=True)
    (CARTELLA / "icona.svg").write_text(svg(), encoding="utf-8")
    for lato, nome in ((32, "icona-32.png"), (192, "icona-192.png"), (512, "icona-512.png")):
        png(lato, CARTELLA / nome)
    # iPhone arrotonda da sé: fondo pieno, angoli 0
    png(180, CARTELLA / "apple-touch-icon.png", angoli=0)
    # maskable: fondo pieno e disegno nella zona sicura centrale (80%)
    png(512, CARTELLA / "icona-maskable-512.png", scala=0.8, margine=0.1, angoli=0)
    print("icone generate in", CARTELLA)


if __name__ == "__main__":
    main()
