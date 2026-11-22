# Builds the StylizedTree in Blender: a tapered low-poly trunk with roots and branches, and a canopy made of
# ALPHA CARDS - ~160 small quads that all show the same hand-drawn leaf-cluster image (textures/leaf_cluster.png),
# scattered over five overlapping canopy blobs with random tilt, roll and mirroring.
#
# The trick that makes the cards read as one soft, fluffy crown instead of a pile of flat planes is NORMAL
# TRANSFER: every card vertex gets a custom normal pointing out of the canopy volume (its blob's ellipsoid normal
# blended with the whole crown's), so the light falls on the crown as if it were a smooth blob.
# Cards are double-sided in geometry (a back face with the same outward normals), so no engine needs a
# double-sided material, and both sides shade the same.
#
# Run in Blender (Text editor or the MCP); re-running rebuilds the StylizedTree collection only.
# Units: metres, Z up (the glTF exporter converts to Y up). Tree is ~6.4 m tall.
import os, math, random
import bpy, bmesh
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else bpy.path.abspath("//")
ROOT = os.path.dirname(HERE)
LEAF_PNG = os.path.join(ROOT, "textures", "leaf_cluster.png")
SEED = 11
COL = "StylizedTree"

# ---------------------------------------------------------------- layout (metres, Z up)
# trunk + branches: control points (x, y, z, radius); smoothed with Catmull-Rom
TRUNK = [(0, 0, -0.15, 0.40), (0.04, 0, 0.35, 0.31), (0.12, 0.05, 1.3, 0.26), (0.06, 0.02, 2.3, 0.23), (0.0, -0.05, 3.1, 0.19),
         (0.12, -0.25, 4.1, 0.12), (0.15, -0.35, 4.9, 0.05)]
BRANCHES = [
    [(0.05, 0.0, 2.45, 0.15), (0.75, 0.2, 3.25, 0.10), (1.35, 0.4, 3.95, 0.05)],
    [(0.02, 0.0, 2.65, 0.14), (-0.65, -0.3, 3.45, 0.09), (-1.25, -0.5, 4.1, 0.045)],
    [(0.03, 0.02, 2.85, 0.12), (-0.2, 0.7, 3.6, 0.08), (-0.3, 1.15, 4.25, 0.04)],
    [(0.05, -0.02, 2.55, 0.12), (0.3, -0.75, 3.3, 0.08), (0.45, -1.25, 3.9, 0.04)],
]
ROOTS = 5                                           # root flares around the base

# canopy blobs: centre, radii  (the crown is their union)
BLOBS = [
    (Vector((0.1, -0.2, 4.95)), Vector((1.85, 1.85, 1.45))),
    (Vector((1.35, 0.4, 4.15)), Vector((1.25, 1.25, 1.05))),
    (Vector((-1.3, -0.5, 4.25)), Vector((1.25, 1.25, 1.05))),
    (Vector((-0.3, 1.2, 4.35)), Vector((1.15, 1.15, 1.0))),
    (Vector((0.45, -1.3, 4.05)), Vector((1.1, 1.1, 0.95))),
]
CROWN = (Vector((0.05, -0.05, 4.55)), Vector((2.7, 2.7, 1.9)))  # whole-crown ellipsoid for the normal blend
CARDS = 160
CARD_SIZE = (1.1, 1.6)                              # edge length range, metres
CROWN_NORMAL_MIX = 0.6                              # 0 = per-blob lumps, 1 = one smooth dome

BARK = (0.40, 0.26, 0.17)                           # linear-ish base colour of the bark
BARK_DARK = (0.16, 0.10, 0.07)


# ---------------------------------------------------------------- helpers
def catmull(pts, per=4):
    """Catmull-Rom through (x,y,z,r) control points, `per` samples per span."""
    P = [Vector(p[:3]) for p in pts]
    R = [p[3] for p in pts]
    out = []
    for i in range(len(P) - 1):
        p0, p1, p2, p3 = P[max(i - 1, 0)], P[i], P[i + 1], P[min(i + 2, len(P) - 1)]
        for s in range(per):
            t = s / per
            t2, t3 = t * t, t * t * t
            p = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            out.append((p, R[i] + (R[i + 1] - R[i]) * t))
    out.append((P[-1], R[-1]))
    return out


def tube(bm, samples, sides, col_layer, tip=True, wobble=0.0, rnd=None):
    """Tapered tube along samples [(point, radius)], parallel-transport frames, closed at both ends."""
    rings, prev_n = [], None
    for i, (p, r) in enumerate(samples):
        a = samples[max(i - 1, 0)][0]
        b = samples[min(i + 1, len(samples) - 1)][0]
        t = (b - a).normalized()
        if prev_n is None:
            n = t.cross(Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))).normalized()
        else:
            n = (prev_n - t * prev_n.dot(t)).normalized()
        prev_n = n
        bi = t.cross(n)
        ring = []
        for k in range(sides):
            ang = 2 * math.pi * k / sides
            rr = r * (1 + (rnd.uniform(-wobble, wobble) if rnd else 0))
            ring.append(bm.verts.new(p + (n * math.cos(ang) + bi * math.sin(ang)) * rr))
        rings.append(ring)
    faces = []
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(sides):
            faces.append(bm.faces.new((r0[k], r0[(k + 1) % sides], r1[(k + 1) % sides], r1[k])))
    faces.append(bm.faces.new(list(reversed(rings[0]))))
    if tip:
        end = samples[-1][0] + (samples[-1][0] - samples[-2][0]).normalized() * samples[-1][1] * 1.5
        v = bm.verts.new(end)
        for k in range(sides):
            faces.append(bm.faces.new((rings[-1][k], rings[-1][(k + 1) % sides], v)))
    else:
        faces.append(bm.faces.new(rings[-1]))
    return faces


def ellipsoid_normal(p, c, r):
    d = p - c
    return Vector((d.x / (r.x * r.x), d.y / (r.y * r.y), d.z / (r.z * r.z))).normalized()


def inside(p, c, r):
    d = p - c
    return (d.x / r.x) ** 2 + (d.y / r.y) ** 2 + (d.z / r.z) ** 2


def lin(c):  # sRGB hex-ish tuple helper for vertex colours (they are stored linear)
    return tuple(x ** 2.2 for x in c) + (1.0,)


# ---------------------------------------------------------------- materials
def bark_material():
    m = bpy.data.materials.get("Bark") or bpy.data.materials.new("Bark")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (300, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (0, 0)
    vc = nt.nodes.new("ShaderNodeVertexColor"); vc.layer_name = "Col"; vc.location = (-300, 0)
    nt.links.new(vc.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Roughness"].default_value = 0.95
    m.diffuse_color = BARK + (1,)
    return m


def leaf_material():
    m = bpy.data.materials.get("LeafCards") or bpy.data.materials.new("LeafCards")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (400, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (100, 0)
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.location = (-400, 0)
    tex.image = bpy.data.images.load(LEAF_PNG, check_existing=True)
    tex.image.alpha_mode = "STRAIGHT"
    # Math:Round on alpha = alpha CLIP at 0.5; the glTF exporter recognises it and writes alphaMode MASK
    rnd = nt.nodes.new("ShaderNodeMath"); rnd.operation = "ROUND"; rnd.location = (-120, -200)
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(tex.outputs["Alpha"], rnd.inputs[0])
    nt.links.new(rnd.outputs[0], bsdf.inputs["Alpha"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Roughness"].default_value = 0.9
    m.surface_render_method = "DITHERED"
    m.use_backface_culling = True           # each card has a real back face, so culling stops z-fighting
    m.diffuse_color = (0.25, 0.5, 0.18, 1)
    return m


# ---------------------------------------------------------------- build
def new_mesh(name):
    """A fresh mesh that keeps its plain name (glTF mesh / Roblox MeshPart names): drops the previous build's."""
    for m in [m for m in bpy.data.meshes if m.name == name or m.name.startswith(name + ".")]:
        if m.users == 0:
            bpy.data.meshes.remove(m)
    return bpy.data.meshes.new(name)


def build():
    rnd = random.Random(SEED)
    coll = bpy.data.collections.get(COL)
    if coll:
        for o in list(coll.objects):
            bpy.data.objects.remove(o, do_unlink=True)
    else:
        coll = bpy.data.collections.new(COL)
        bpy.context.scene.collection.children.link(coll)

    root = bpy.data.objects.new(COL, None)
    root.empty_display_type = "PLAIN_AXES"
    coll.objects.link(root)

    # ---- trunk, roots, branches (one mesh) -------------------------------------------------------
    bm = bmesh.new()
    col = bm.loops.layers.color.new("Col")
    tube(bm, catmull(TRUNK, 4), 9, col, tip=True, wobble=0.04, rnd=rnd)
    for b in BRANCHES:
        tube(bm, catmull(b, 4), 7, col, tip=True, wobble=0.03, rnd=rnd)
    for i in range(ROOTS):
        a = 2 * math.pi * (i + rnd.uniform(-0.2, 0.2)) / ROOTS
        d = Vector((math.cos(a), math.sin(a), 0))
        pts = [(0.05 * d.x, 0.05 * d.y, 0.55, 0.15), (0.45 * d.x, 0.45 * d.y, 0.12, 0.11),
               (0.85 * d.x, 0.85 * d.y, -0.04, 0.05)]
        tube(bm, catmull(pts, 3), 6, col, tip=True)
    # vertex colours: darker at the root line and inside the crown's shade, light in the middle of the trunk
    for f in bm.faces:
        f.smooth = True
        for l in f.loops:
            z = l.vert.co.z
            t = min(1, max(0, z / 0.5)) * (1 - min(1, max(0, (z - 2.6) / 1.4)) * 0.7)
            c = tuple(BARK_DARK[k] + (BARK[k] - BARK_DARK[k]) * t for k in range(3))
            l[col] = c + (1.0,)
    me = new_mesh("Trunk")
    bm.to_mesh(me); bm.free()
    trunk = bpy.data.objects.new("Trunk", me)
    trunk.data.materials.append(bark_material())
    trunk.parent = root
    coll.objects.link(trunk)

    # ---- leaf cards ------------------------------------------------------------------------------
    areas = [r.x * r.y + r.y * r.z + r.x * r.z for _, r in BLOBS]
    total = sum(areas)
    verts, faces, uvs, normals = [], [], [], []
    for (c, r), area in zip(BLOBS, areas):
        n_cards = round(CARDS * area / total)
        made, tries = 0, 0
        while made < n_cards and tries < n_cards * 40:
            tries += 1
            d = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized()
            if d.z < -0.55 and rnd.random() < 0.6:           # fewer cards on the underside
                continue
            p = c + Vector((d.x * r.x, d.y * r.y, d.z * r.z)) * rnd.uniform(0.68, 0.98)
            # skip cards buried deep inside another blob (never seen)
            if any(inside(p, c2, r2) < 0.55 for c2, r2 in BLOBS if c2 is not c):
                continue
            # orientation: face out of the blob, tilted at random, rolled at random
            nrm = (ellipsoid_normal(p, c, r) + Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))) * 0.35).normalized()
            u = nrm.cross(Vector((0, 0, 1)) if abs(nrm.z) < 0.95 else Vector((1, 0, 0))).normalized()
            v = nrm.cross(u)
            roll = rnd.uniform(0, 2 * math.pi)
            u, v = u * math.cos(roll) + v * math.sin(roll), -u * math.sin(roll) + v * math.cos(roll)
            s = rnd.uniform(*CARD_SIZE) * 0.5
            corners = [p - u * s - v * s, p + u * s - v * s, p + u * s + v * s, p - u * s + v * s]
            flip = rnd.random() < 0.5                         # mirror the image on half the cards
            quv = [(1, 0), (0, 0), (0, 1), (1, 1)] if flip else [(0, 0), (1, 0), (1, 1), (0, 1)]
            # normal transfer: blob ellipsoid normal blended with the whole crown's
            cn = [(ellipsoid_normal(q, c, r) * (1 - CROWN_NORMAL_MIX) + ellipsoid_normal(q, *CROWN) * CROWN_NORMAL_MIX).normalized()
                  for q in corners]
            # front face (winding faces along nrm) and back face (reversed) with the same outward normals; the back
            # face gets its own copy of the corners (Blender drops a second face on the same four vertices)
            for poly in ((0, 1, 2, 3), (3, 2, 1, 0)):
                base = len(verts)
                verts.extend(corners)
                faces.append(tuple(base + i for i in poly))
                uvs.extend(quv[i] for i in poly)
                normals.extend(cn[i] for i in poly)
            made += 1

    me = new_mesh("Leaves")
    me.from_pydata([tuple(v) for v in verts], [], faces)
    uv = me.uv_layers.new(name="UVMap")
    for i, l in enumerate(me.loops):
        uv.data[i].uv = uvs[i]
    for p in me.polygons:
        p.use_smooth = True
    me.normals_split_custom_set([tuple(n) for n in normals])
    me.validate(clean_customdata=False)
    leaves = bpy.data.objects.new("Leaves", me)
    leaves.data.materials.append(leaf_material())
    leaves.parent = root
    coll.objects.link(leaves)

    return {"trunk_tris": sum(len(p.vertices) - 2 for p in trunk.data.polygons),
            "cards": len(faces) // 2, "leaf_tris": len(faces) * 2}


result = build()
print(result)
