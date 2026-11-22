"""Tile the per-frame review renders from 04_strips.py into 4x2 contact sheets with labels."""
import glob
import os
import re
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out")
SRC = os.path.join(OUT, "strip_src")
try:
    font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 22)
except Exception:
    font = ImageFont.load_default()

clips = {}
for path in glob.glob(os.path.join(SRC, "*.png")):
    m = re.match(r"(.+)_(\d{3})\.png$", os.path.basename(path))
    clips.setdefault(m.group(1), []).append((int(m.group(2)), path))

for name, items in sorted(clips.items()):
    items.sort()
    ims = [Image.open(p).convert("RGB") for _, p in items]
    w, h = ims[0].size
    sheet = Image.new("RGB", (w * 4, h * 2), (18, 18, 20))
    d = ImageDraw.Draw(sheet)
    for i, (im, (f, _)) in enumerate(zip(ims, items)):
        x, y = (i % 4) * w, (i // 4) * h
        sheet.paste(im, (x, y))
        label = f"{name}  f{f}"
        d.rectangle([x + 6, y + 6, x + 6 + 11 * len(label), y + 34], fill=(12, 12, 14))
        d.text((x + 10, y + 8), label, font=font, fill=(230, 230, 230))
    path = os.path.join(OUT, f"strip_{name}.png")
    sheet.save(path)
    print("SHEET", path, sheet.size)
