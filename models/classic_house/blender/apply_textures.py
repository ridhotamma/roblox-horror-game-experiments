# Textures the imported ClassicHouse in Blender: world-space box UVs (real-world tile sizes) and
# image materials from make_textures.py. Walls and partitions get one material per face: siding outside,
# living-room / bedroom wallpaper or kitchen paint inside, chosen by the room each face looks into.
import os, re, json, math
import bpy, bmesh
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TEX = os.path.join(ROOT, "textures")

ns = {"__file__": os.path.join(HERE, "make_textures.py"), "__name__": "make_textures"}
exec(open(ns["__file__"], encoding="utf-8").read(), ns)
TILES = {k: v[1] for k, v in ns["TEXTURES"].items()}

ROUGH = {"carpet": 0.98, "rug": 0.95, "shingles": 0.9, "brick": 0.92, "concrete": 0.95, "wood_floor": 0.55,
         "linoleum": 0.45, "siding": 0.8}


def material(tex):
    name = "TXM_" + tex
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    img_node = nt.nodes.new("ShaderNodeTexImage")
    path = os.path.join(TEX, tex + ".png")
    img = bpy.data.images.load(path, check_existing=True)
    img_node.image = img
    img_node.location = (-400, 200)
    nt.links.new(img_node.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = ROUGH.get(tex, 0.75)
    m.diffuse_color = tuple(list(img.pixels[0:3]) + [1.0]) if len(img.pixels) else (1, 1, 1, 1)
    return m


def srgb_to_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hexlin(h):
    h = h.lstrip("#")
    return [srgb_to_lin(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4)]


WOOD_BY_COLOR = {"#7a5233": "wood", "#a07a52": "wood_light", "#4f3322": "wood_dark", "#8a6a45": "wood_oak",
                 "#6b4a36": "wood_backdoor", "#5a3d2c": "wood_backdoor"}
WOOD_LIN = {k: hexlin(k) for k in WOOD_BY_COLOR}

BY_NAME = [
    (r"^(Floor)$", "wood_floor"), (r"^Ceiling$", "plaster_ceiling"), (r"^Rug$", "rug"), (r"^Carpet$", "carpet"),
    (r"^Linoleum$", "linoleum"), (r"^(Roof|PorchRoof)$", "shingles"),
    (r"^(Chimney|FireplaceBody|ChimneyBreast)$", "brick"),
    (r"^(Foundation|Stoop|Step1|Step2|BackStep)$", "concrete"),
    (r"^Sofa(Base|Back|Arm[LR]|Cushion\d)$", "fabric_green"), (r"^Armchair(Base|Back|Arm[LR]|Cushion\d)$", "fabric_rose"),
    (r"^DiningTableCloth$", "linen"), (r"^(KitchenTableCloth|KitchenCurtain)$", "gingham"),
    (r"^Blanket$", "quilt"), (r"^(Mattress|Pillow[AB])$", "linen"),
    (r"^(Curtain(Outer|Inner)[LR]|Valance[LR]|SideCurtain[AB][LR])$", "curtain"), (r"^BedCurtain[AB]$", "curtain_bed"),
]
WALLS = re.compile(r"^(Wall(Front|Back|Left|Right)\d+|Gable[LR]|PartitionMid\d+|PartitionBack\d+)$")
ROOM_SLOTS = ["siding", "wallpaper_living", "wallpaper_bedroom", "paint_kitchen"]


def base_name(o):
    return re.sub(r"\.\d{3}$", "", o.name)


def orig_color(o):
    for s in o.material_slots:
        m = s.material
        if m and m.use_nodes and not m.name.startswith("TXM_"):
            b = m.node_tree.nodes.get("Principled BSDF")
            if b:
                return list(b.inputs["Base Color"].default_value)[:3]
    return None


def wood_for(o):
    c = orig_color(o)
    if c is None:
        return None
    best, bd = None, 1e9
    for h, lin in WOOD_LIN.items():
        d = sum((a - b) ** 2 for a, b in zip(c, lin))
        if d < bd:
            best, bd = h, d
    return WOOD_BY_COLOR[best] if bd < 2e-4 else None


def room_slot(center_b, normal_b):
    # Blender world -> model space (x, y up, z front): (bx, bz, -by)
    p = Vector((center_b.x + normal_b.x * 0.12, center_b.z + normal_b.z * 0.12, -(center_b.y + normal_b.y * 0.12)))
    if abs(p.x) > 4.951 or abs(p.z) > 3.851 or p.y > 3.4:
        return 0                                   # outside / gable / reveal: siding
    if p.z > -0.8:
        return 1                                   # living room
    return 2 if p.x < 0 else 3                     # bedroom / kitchen


def box_uv(o, bm, tile, fit=None, tile_for=None):
    uv = bm.loops.layers.uv.verify()
    mw = o.matrix_world
    nmat = mw.to_3x3().inverted().transposed()
    for f in bm.faces:
        n = (nmat @ f.normal).normalized()
        ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
        t = tile_for(f) if tile_for else tile
        for loop in f.loops:
            w = mw @ loop.vert.co
            if fit:
                (x0, y0, sx, sy) = fit
                loop[uv].uv = ((w.x - x0) / sx, (w.y - y0) / sy)
                continue
            if az >= ax and az >= ay:
                # floors / roofs: courses run parallel to the eave, i.e. across the slope direction
                u, v = (w.y, w.x) if ax > ay else (w.x, w.y)
            elif ax >= ay:
                u, v = w.y, w.z
            else:
                u, v = w.x, w.z
            loop[uv].uv = (u / t, v / t)


def apply(collection_name="ClassicHouse"):
    col = bpy.data.collections[collection_name]
    report = {}
    for o in col.all_objects:
        if o.type != "MESH":
            continue
        name = base_name(o)
        tex = None
        if WALLS.match(name):
            tex = "@rooms"
        else:
            for pat, t in BY_NAME:
                if re.match(pat, name):
                    tex = t
                    break
            if tex is None:
                tex = wood_for(o)
        if tex is None:
            continue
        o["orig_material"] = o.material_slots[0].material.name if o.material_slots and o.material_slots[0].material else ""
        me = o.data
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        mw = o.matrix_world
        nmat = mw.to_3x3().inverted().transposed()
        if tex == "@rooms":
            me.materials.clear()
            for t in ROOM_SLOTS:
                me.materials.append(material(t))
            for f in bm.faces:
                f.material_index = room_slot(mw @ f.calc_center_median(), (nmat @ f.normal).normalized())
            box_uv(o, bm, 1.0, tile_for=lambda f: TILES[ROOM_SLOTS[f.material_index]])
            report[name] = "rooms"
        else:
            me.materials.clear()
            me.materials.append(material(tex))
            for f in bm.faces:
                f.material_index = 0
            fit = None
            if TILES.get(tex) is None:
                ws = [mw @ v.co for v in bm.verts]
                x0, x1 = min(w.x for w in ws), max(w.x for w in ws)
                y0, y1 = min(w.y for w in ws), max(w.y for w in ws)
                fit = (x0, y0, x1 - x0, y1 - y0)
            box_uv(o, bm, TILES.get(tex) or 1.0, fit)
            report[name] = tex
        bm.to_mesh(me)
        bm.free()
        me.update()
    return report


if __name__ == "__main__":
    os.makedirs(TEX, exist_ok=True)
    made = ns["make_all"](TEX)
    rep = apply()
    from collections import Counter
    print("textures:", len(made), "| textured objects:", len(rep), dict(Counter(rep.values())))
