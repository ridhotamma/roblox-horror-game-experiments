"""Tile the per-frame review renders into 4x2 contact sheets with labels."""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = r"C:\Users\ridho\kerjaan\roblox-horror-game-experiments\models\cat\out"
SRC = os.path.join(OUT, "strip_src")
clips = {
    "Idle": [1, 13, 25, 37, 49, 61, 73, 85],
    "Walk": [1, 4, 7, 10, 13, 16, 19, 22],
    "Run": [1, 3, 5, 7, 9, 11, 13, 15],
    "Jump": [1, 7, 10, 14, 18, 22, 27, 31],
}
try:
    font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 22)
except Exception:
    font = ImageFont.load_default()

for name, frames in clips.items():
    ims = [Image.open(os.path.join(SRC, f"{name}_{f:03d}.png")).convert("RGB") for f in frames]
    w, h = ims[0].size
    sheet = Image.new("RGB", (w * 4, h * 2), (18, 18, 20))
    d = ImageDraw.Draw(sheet)
    for i, (im, f) in enumerate(zip(ims, frames)):
        x = (i % 4) * w
        y = (i // 4) * h
        sheet.paste(im, (x, y))
        label = f"{name}  f{f}"
        d.rectangle([x + 6, y + 6, x + 6 + 10 * len(label), y + 34], fill=(12, 12, 14))
        d.text((x + 10, y + 8), label, font=font, fill=(230, 230, 230))
    path = os.path.join(OUT, f"strip_{name}.png")
    sheet.save(path)
    print("SHEET", path, sheet.size)
