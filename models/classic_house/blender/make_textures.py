# Generates seamless 1940s-style textures for ClassicHouse with numpy, inside Blender.
# Run in Blender (Text Editor or the MCP add-on). Writes PNGs to ../textures and returns their tile sizes.
# Every texture tiles seamlessly (all noise is periodic), so it can repeat over any wall size.
import os
import numpy as np
import bpy

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else None
OUT = os.path.join(os.path.dirname(HERE), "textures") if HERE else None


def hexrgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


def vnoise(n, cells, seed):
    """Tileable value noise in [0,1], n x n pixels, `cells` lattice cells per side."""
    rng = np.random.default_rng(seed)
    g = rng.random((cells, cells))
    t = np.arange(n) * cells / n
    i0 = np.floor(t).astype(int)
    f = t - i0
    f = f * f * (3 - 2 * f)
    i1 = (i0 + 1) % cells
    a = g[np.ix_(i0, i0)]; b = g[np.ix_(i0, i1)]; c = g[np.ix_(i1, i0)]; d = g[np.ix_(i1, i1)]
    fy = f[:, None]; fx = f[None, :]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def fbm(n, seed, octaves=(4, 8, 16, 32, 64), weights=(0.4, 0.25, 0.15, 0.12, 0.08)):
    return sum(w * vnoise(n, c, seed + k) for k, (c, w) in enumerate(zip(octaves, weights)))


def grid(n):
    v = (np.arange(n) + 0.5) / n
    return np.meshgrid(v, v)  # x (u, to the right), y (v, upwards in UV space)


def shade(base, k):
    """base colour (3,) times a per-pixel factor k (n,n) -> (n,n,3)."""
    return np.clip(base[None, None, :] * k[:, :, None], 0, 1)


def mix(a, b, t):
    t = t[:, :, None] if np.ndim(t) == 2 else t
    return a * (1 - t) + b * t


def tint_layer(n, col, k):
    return shade(hexrgb(col), k)


# ---------------------------------------------------------------- textures
def siding(n=512):
    # 5 lap boards per metre: each board darkens towards its top edge (shadow of the board above).
    x, y = grid(n)
    board = (y * 5) % 1.0
    k = 0.86 + 0.14 * np.clip(board / 0.85, 0, 1)
    k = np.where(board > 0.94, 0.68, k)
    grain = vnoise(n, 64, 3)[:, :] * 0.04 + fbm(n, 11) * 0.05
    return shade(hexrgb("#ece8dd"), k * (0.96 + grain))


def wallpaper_living(n=512):
    # Sage stripes with a small cream diamond motif (1940s stripe paper).
    x, y = grid(n)
    base = hexrgb("#9fae8f"); dark = hexrgb("#8a9a7c"); cream = hexrgb("#e9e2c8")
    img = np.broadcast_to(base, (n, n, 3)).copy()
    sx = (x * 4) % 1.0
    img[(sx > 0.42) & (sx < 0.58)] = dark
    img[(np.abs(sx - 0.5) < 0.012)] = cream
    # diamonds between stripes, 4 per tile vertically
    cx = (x * 4 + 0.5) % 1.0 - 0.5
    cy = (y * 4) % 1.0 - 0.5
    d = np.abs(cx) * 1.6 + np.abs(cy)
    img[d < 0.11] = cream
    img[(d < 0.05)] = hexrgb("#b8746a")
    return np.clip(img * (0.95 + 0.06 * fbm(n, 21))[:, :, None], 0, 1)


def wallpaper_bedroom(n=512):
    # Dusty rose ground with scattered floral sprigs.
    x, y = grid(n)
    img = shade(hexrgb("#d8b4aa"), 0.96 + 0.06 * fbm(n, 31))
    rng = np.random.default_rng(5)
    for _ in range(14):
        px, py = rng.random(2)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                ddx = x - (px + dx); ddy = y - (py + dy)
                r = np.sqrt(ddx ** 2 + ddy ** 2)
                ang = np.arctan2(ddy, ddx)
                petal = r < 0.03 * (0.75 + 0.25 * np.cos(5 * ang))
                img[petal] = hexrgb("#a8506a")
                img[r < 0.008] = hexrgb("#e8d27a")
                leaf = (np.abs(ddx + 0.035) < 0.012) & (np.abs(ddy + 0.02) < 0.006)
                img[leaf] = hexrgb("#6f8a5e")
    return img


def paint(col, seed, amount=0.05):
    def f(n=256):
        return shade(hexrgb(col), 1 - amount + amount * 2 * fbm(n, seed))
    return f


def wood_floor(n=1024):
    # 10 oak planks per tile (0.12 m wide at a 1.2 m tile), staggered end joints, grain along the plank.
    x, y = grid(n)
    planks = 10
    idx = np.floor(x * planks).astype(int)
    rng = np.random.default_rng(7)
    offs = rng.random(planks)
    tone = 0.85 + 0.25 * rng.random(planks)
    along = (y + offs[idx]) % 1.0
    seg = np.floor(along * 2).astype(int)  # two boards along each plank row
    tone2 = tone[idx] * (0.93 + 0.12 * ((idx * 7 + seg * 3) % 5) / 4)
    grain = 0.5 + 0.5 * np.sin((x * planks * 6 + vnoise(n, 16, 9) * 3.0) * 2 * np.pi)
    k = tone2 * (0.85 + 0.15 * grain) * (0.92 + 0.12 * fbm(n, 13))
    k = np.where(((x * planks) % 1.0) < 0.02, 0.45, k)          # gaps between planks
    k = np.where((along * 2) % 1.0 < 0.006, 0.5, k)               # end joints
    return shade(hexrgb("#8a6440"), k)


def shingles(n=512):
    # 5 courses per metre, tabs a third of a metre wide, offset half a tab per course.
    x, y = grid(n)
    course = np.floor(y * 5).astype(int)
    cy = (y * 5) % 1.0
    tx = (x * 3 + 0.5 * (course % 2)) % 1.0
    tab = np.floor(x * 3 + 0.5 * (course % 2)).astype(int)
    rng = np.random.default_rng(17)
    tone = 0.8 + 0.3 * rng.random((5, 4))
    k = tone[course % 5, tab % 4] * (0.85 + 0.25 * cy)
    k = np.where(cy < 0.06, 0.45, k)                  # shadow under the course above
    k = np.where(tx < 0.012, 0.5, k)                   # gaps between tabs
    k = k * (0.88 + 0.24 * vnoise(n, 128, 19))        # granules
    return shade(hexrgb("#4d555b"), k)


def brick(n=512):
    # 0.6 m tile: 8 courses of 0.065 m brick + 0.01 m mortar, three 0.2 m bricks per course.
    x, y = grid(n)
    row = np.floor(y * 8).astype(int)
    ry = (y * 8) % 1.0
    bx = (x * 3 + 0.5 * (row % 2)) % 1.0
    bi = np.floor(x * 3 + 0.5 * (row % 2)).astype(int)
    rng = np.random.default_rng(23)
    tone = 0.78 + 0.35 * rng.random((8, 4))
    k = tone[row % 8, bi % 4] * (0.9 + 0.15 * fbm(n, 29))
    img = shade(hexrgb("#9a4a38"), k)
    mortar = (ry < 0.13) | (bx < 0.025)
    img[mortar] = hexrgb("#b9b1a3") * (0.9 + 0.1 * vnoise(n, 64, 31))[mortar][:, None]
    return img


def concrete(n=256):
    return shade(hexrgb("#a9aca6"), 0.85 + 0.25 * fbm(n, 41))


def carpet(n=256):
    return shade(hexrgb("#5f7276"), 0.82 + 0.3 * vnoise(n, 128, 43) * 0.5 + 0.15 * fbm(n, 44))


def linoleum(n=512):
    x, y = grid(n)
    chk = (np.floor(x * 2) + np.floor(y * 2)) % 2
    a = hexrgb("#e7e0cc"); b = hexrgb("#2c2c30")
    img = mix(np.broadcast_to(a, (n, n, 3)), np.broadcast_to(b, (n, n, 3)), chk)
    return np.clip(img * (0.94 + 0.1 * fbm(n, 47))[:, :, None], 0, 1)


def rug(n=1024):
    # Persian-style rug mapped once over the rug: red field, navy border, cream lines, central medallion.
    x, y = grid(n)
    red = hexrgb("#8e2f27"); navy = hexrgb("#24304d"); cream = hexrgb("#e6d6b0"); gold = hexrgb("#c49a46")
    img = np.broadcast_to(red, (n, n, 3)).copy()
    e = np.minimum(np.minimum(x, 1 - x), np.minimum(y, 1 - y))
    img[e < 0.12] = navy
    img[(e > 0.045) & (e < 0.055)] = cream
    img[(e > 0.12) & (e < 0.135)] = gold
    # small repeating motifs in the border and field
    m = (np.abs(((x * 14) % 1) - 0.5) + np.abs(((y * 10) % 1) - 0.5)) < 0.18
    img[m & (e < 0.11) & (e > 0.065)] = gold
    f = (np.abs(((x * 8) % 1) - 0.5) + np.abs(((y * 6) % 1) - 0.5)) < 0.12
    img[f & (e > 0.16)] = hexrgb("#a8473b")
    d = np.abs(x - 0.5) * 1.35 + np.abs(y - 0.5)
    img[(d < 0.27) & (e > 0.16)] = navy
    img[(d < 0.2)] = hexrgb("#b5523f")
    img[(d < 0.12)] = cream
    img[(d < 0.05)] = navy
    return np.clip(img * (0.9 + 0.15 * vnoise(n, 256, 51))[:, :, None], 0, 1)


def fabric(col, seed, floral=False):
    def f(n=512):
        x, y = grid(n)
        weave = 0.92 + 0.08 * (np.sin(x * n * np.pi / 2) * np.sin(y * n * np.pi / 2))
        img = shade(hexrgb(col), weave * (0.9 + 0.15 * fbm(n, seed)))
        if floral:
            cx = (x * 3) % 1.0 - 0.5; cy = (y * 3 + 0.5 * np.floor(x * 3)) % 1.0 - 0.5
            r = np.sqrt(cx ** 2 + cy ** 2); a = np.arctan2(cy, cx)
            img[r < 0.16 * (0.7 + 0.3 * np.cos(6 * a))] = hexrgb("#e3c6a8")
            img[r < 0.05] = hexrgb("#6d2f2a")
            leaf = (np.abs(cx - 0.25) < 0.08) & (np.abs(cy + 0.2) < 0.03)
            img[leaf] = hexrgb("#55704a")
        return img
    return f


def woodgrain(col, seed):
    def f(n=512):
        x, y = grid(n)
        warp = vnoise(n, 8, seed) * 2.0 + vnoise(n, 32, seed + 1) * 0.3
        rings = 0.5 + 0.5 * np.sin((y * 18 + warp) * 2 * np.pi)
        k = 0.86 + 0.14 * rings ** 3
        k *= 0.92 + 0.12 * vnoise(n, 128, seed + 2)
        return shade(hexrgb(col), k)
    return f


def gingham(n=256):
    x, y = grid(n)
    a = ((x * 4) % 1) < 0.5; b = ((y * 4) % 1) < 0.5
    white = hexrgb("#f4efe6"); red = hexrgb("#c8423a"); pink = hexrgb("#e09590")
    img = np.broadcast_to(white, (n, n, 3)).copy()
    img[a ^ b] = pink
    img[a & b] = red
    return img


def quilt(n=512):
    x, y = grid(n)
    cols = [hexrgb(c) for c in ("#7c8fa8", "#a8b8c8", "#e8e0cc", "#5e6f8a", "#b39c7a")]
    i = (np.floor(x * 4) + 2 * np.floor(y * 4)).astype(int)
    img = np.zeros((n, n, 3))
    for k, c in enumerate(cols):
        img[i % 5 == k] = c
    seam = (((x * 4) % 1) < 0.02) | (((y * 4) % 1) < 0.02)
    img[seam] *= 0.7
    return np.clip(img * (0.93 + 0.1 * fbm(n, 61))[:, :, None], 0, 1)


def curtain(col, seed):
    def f(n=256):
        x, y = grid(n)
        folds = 0.85 + 0.15 * np.sin(x * 2 * np.pi * 6)
        return shade(hexrgb(col), folds * (0.93 + 0.1 * fbm(n, seed)))
    return f


# name -> (generator, tile size in metres; None = stretched once over the part)
TEXTURES = {
    "siding": (siding, 1.0),
    "wallpaper_living": (wallpaper_living, 0.6),
    "wallpaper_bedroom": (wallpaper_bedroom, 0.6),
    "paint_kitchen": (paint("#eadfb4", 71, 0.04), 1.0),
    "plaster_ceiling": (paint("#ebe6da", 73, 0.03), 1.0),
    "wood_floor": (wood_floor, 1.2),
    "shingles": (shingles, 1.0),
    "brick": (brick, 0.6),
    "concrete": (concrete, 1.0),
    "carpet": (carpet, 0.5),
    "linoleum": (linoleum, 0.6),
    "rug": (rug, None),
    "fabric_green": (fabric("#5f7a55", 81), 0.25),
    "fabric_rose": (fabric("#a0584f", 83, floral=True), 0.35),
    "wood": (woodgrain("#7a5233", 91), 0.6),
    "wood_light": (woodgrain("#a07a52", 93), 0.6),
    "wood_dark": (woodgrain("#4f3322", 95), 0.6),
    "wood_oak": (woodgrain("#8a6a45", 97), 0.6),
    "wood_backdoor": (woodgrain("#6b4a36", 99), 0.6),
    "gingham": (gingham, 0.12),
    "quilt": (quilt, 0.6),
    "linen": (fabric("#f0ece2", 101), 0.3),
    "curtain": (curtain("#c7a46a", 103), 0.5),
    "curtain_bed": (curtain("#c9a0a0", 105), 0.5),
}


def save_png(name, arr, out_dir):
    n = arr.shape[0]
    img = bpy.data.images.get("TX_" + name)
    if img:
        bpy.data.images.remove(img)
    img = bpy.data.images.new("TX_" + name, n, n, alpha=False)
    rgba = np.ones((n, n, 4), dtype=np.float32)
    rgba[:, :, :3] = arr
    img.pixels.foreach_set(rgba.ravel())
    path = os.path.join(out_dir, name + ".png")
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    return path


def make_all(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    done = {}
    for name, (gen, tile) in TEXTURES.items():
        done[name] = (save_png(name, gen(), out_dir), tile)
    return done


if __name__ == "__main__" and OUT:
    print(make_all(OUT))
