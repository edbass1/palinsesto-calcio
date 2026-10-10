#!/usr/bin/env python3
"""Genera le icone della web app (richiede Pillow; serve solo una volta, le PNG sono già nel repository)."""
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "static"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def icona(n):
    s = 4 * n  # disegno in grande e riduco (antialias)
    im = Image.new("RGB", (s, s), "black")
    d = ImageDraw.Draw(im)
    # pallone
    cx, cy, r = s / 2, s * 0.40, s * 0.27
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill="white")
    def pent(x, y, rr, rot=-90):
        return [(x + rr * math.cos(math.radians(rot + 72 * k)), y + rr * math.sin(math.radians(rot + 72 * k))) for k in range(5)]
    d.polygon(pent(cx, cy, r * 0.36), fill="black")
    for k in range(5):
        a = math.radians(-90 + 72 * k)
        x, y = cx + r * 0.86 * math.cos(a), cy + r * 0.86 * math.sin(a)
        d.polygon(pent(x, y, r * 0.22, -90 + 72 * k + 36), fill="black")
        d.line([(cx + r * 0.36 * math.cos(a), cy + r * 0.36 * math.sin(a)), (x, y)], fill="black", width=max(2, s // 90))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline="black", width=max(2, s // 120))
    # scritta TV
    f = ImageFont.truetype(FONT, int(s * 0.24))
    d.text((cx, s * 0.84), "TV", font=f, fill="#ffd400", anchor="mm")
    return im.resize((n, n), Image.LANCZOS)

OUT.mkdir(exist_ok=True)
icona(192).save(OUT / "icon-192.png")
icona(512).save(OUT / "icon-512.png")
icona(180).save(OUT / "apple-touch-icon.png")
print("icone create in", OUT)
