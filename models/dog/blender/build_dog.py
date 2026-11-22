"""Builds the Dog mesh: a metaball sculpt of the anatomy, remeshed to clean quads (Quadriflow), coloured through a
small palette texture (one material, so Roblox gets a single MeshPart), with eyes, nose, ears and a collar placed by
raycasting onto the body surface.

Run headless (from the repo root):
  blender -b --factory-startup --python models/dog/blender/build_dog.py
Then rig_dog.py, animate_dog.py, export_roblox.py (or run_all.py for the whole chain).
"""
import os
import sys
import math
import bpy
import bmesh
from mathutils import Vector, Quaternion
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dog_spec as S  # noqa: E402

ROOT = os.path.dirname(HERE)
TEX = os.path.join(ROOT, "textures")
OUT = os.path.join(ROOT, "out")
os.makedirs(TEX, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

VIS = 0.574  # an isolated metaball's visible radius is 0.574 x its radius (threshold 0.6, stiffness 2)


def reset_scene():
    bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    sc.render.fps = 30
    return sc


# ------------------------------------------------------------------ palette texture + the one material
def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def lerp3(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def coat_colour(u):
    """u in [0, 0.5]: cream -> tan -> dark (sRGB)."""
    t = max(0.0, min(1.0, u / 0.5))
    if t < 0.5:
        return lerp3(S.COAT["cream"], S.COAT["tan"], t / 0.5)
    return lerp3(S.COAT["tan"], S.COAT["dark"], (t - 0.5) / 0.5)


def make_palette():
    w, h = S.PALETTE_W, S.PALETTE_H
    img = bpy.data.images.new("DogPalette", w, h, alpha=False)
    px = []
    for _y in range(h):
        for x in range(w):
            u = (x + 0.5) / w
            if x < 128:
                c = coat_colour(u)
            else:
                idx = (x - 128) // 16
                c = next(col for (i, col) in S.SWATCHES.values() if i == idx)
            px += [c[0], c[1], c[2], 1.0]   # sRGB bytes: the image is stored as sRGB
    img.pixels = px
    path = os.path.join(TEX, "dog_palette.png")
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    img.filepath = path
    return img


def make_material(img):
    m = bpy.data.materials.new("Dog")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.82
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"
    tex.extension = "EXTEND"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return m


# ------------------------------------------------------------------ metaball anatomy
class Sculpt:
    def __init__(self, name):
        self.mb = bpy.data.metaballs.new(name)
        self.mb.resolution = 0.006
        self.mb.render_resolution = 0.006
        self.ob = bpy.data.objects.new(name, self.mb)
        bpy.context.collection.objects.link(self.ob)

    def ellipsoid(self, c, half, rot=None, neg=False, stiff=2.0):
        r = max(half)
        el = self.mb.elements.new(type="ELLIPSOID")
        el.co = c
        el.radius = r / VIS
        el.size_x, el.size_y, el.size_z = (half[0] / r, half[1] / r, half[2] / r)
        el.stiffness = stiff
        el.use_negative = neg
        if rot:
            el.rotation = rot
        return el

    def capsule(self, a, b, r, stiff=2.0):
        a, b = Vector(a), Vector(b)
        el = self.mb.elements.new(type="CAPSULE")
        el.co = (a + b) / 2
        el.radius = r / VIS
        el.size_x = max(1e-4, (b - a).length / 2)  # half the segment length, in absolute units
        el.rotation = Vector((1, 0, 0)).rotation_difference((b - a).normalized())
        el.stiffness = stiff
        return el


def sculpt_body():
    sc = Sculpt("DogSculpt")
    # torso: deep chest, tucked-up waist, rounded rump
    sc.ellipsoid((0, 0.170, 0.430), (0.112, 0.135, 0.138))
    sc.ellipsoid((0, 0.025, 0.455), (0.095, 0.130, 0.105))
    sc.ellipsoid((0, -0.120, 0.470), (0.083, 0.095, 0.080))
    sc.ellipsoid((0, -0.245, 0.470), (0.092, 0.100, 0.095))
    # neck and head
    sc.capsule((0, 0.240, 0.495), (0, 0.385, 0.655), 0.070)
    sc.ellipsoid((0, 0.425, 0.705), (0.073, 0.082, 0.070))
    sc.ellipsoid((0, 0.470, 0.680), (0.058, 0.050, 0.048))      # cheeks
    sc.capsule((0, 0.480, 0.677), (0, 0.585, 0.668), 0.036)    # muzzle bridge
    sc.ellipsoid((0, 0.525, 0.646), (0.034, 0.055, 0.024))      # lower jaw
    # tail: up and back, tapering
    sc.capsule((0, -0.310, 0.520), (0, -0.425, 0.590), 0.030)
    sc.capsule((0, -0.425, 0.590), (0, -0.530, 0.620), 0.025)
    sc.capsule((0, -0.530, 0.620), (0, -0.640, 0.615), 0.017)
    for sx in (1, -1):
        f = {k: Vector((v[0] * sx, v[1], v[2])) for k, v in S.FRONT.items()}
        h = {k: Vector((v[0] * sx, v[1], v[2])) for k, v in S.HIND.items()}
        # front, following the bones: the shoulder blade lies along the chest (withers down and forward to the
        # point of shoulder), the upper arm runs back to the elbow, then a slim forearm, pastern and paw
        sc.capsule(Vector((0.058 * sx, 0.170, 0.515)), f["shoulder"] + Vector((-0.008 * sx, -0.005, 0.0)), 0.034)
        sc.capsule(f["shoulder"], f["elbow"], 0.031)
        sc.ellipsoid(f["elbow"] + Vector((0, -0.012, 0.004)), (0.024, 0.024, 0.026))          # point of elbow
        sc.capsule(f["elbow"], (f["elbow"] + f["wrist"]) / 2, 0.024)
        sc.capsule((f["elbow"] + f["wrist"]) / 2, f["wrist"], 0.020)
        sc.capsule(f["wrist"], f["wrist"] + Vector((0, 0.025, -0.045)), 0.019)
        sc.ellipsoid((0.085 * sx, 0.240, 0.024), (0.030, 0.042, 0.024))
        # hind, a flattened wedge instead of one hanging egg: the haunch blends into the croup, the femur muscles
        # run forward-down to the stifle, the hamstrings make the curved back line from the seat bone down to the
        # gaskin, and the gaskin tapers to a clean hock
        hip_top = h["hip"] + Vector((-0.024 * sx, 0.0, 0.0))
        sc.ellipsoid(Vector((0.064 * sx, -0.245, 0.415)), (0.044, 0.098, 0.078))              # haunch
        sc.capsule(hip_top, h["knee"] + Vector((0, -0.012, 0.012)), 0.039)                    # quadriceps / femur
        sc.capsule(Vector((0.058 * sx, -0.335, 0.440)), Vector((0.086 * sx, -0.228, 0.268)), 0.031)   # hamstrings
        sc.ellipsoid(Vector((0.076 * sx, -0.232, 0.345)), (0.034, 0.058, 0.064),              # fills the thigh
                     rot=Quaternion((1, 0, 0), math.radians(-28)))
        sc.ellipsoid(h["knee"] + Vector((0, 0.006, 0.0)), (0.026, 0.026, 0.028))              # stifle
        sc.capsule(h["knee"], (h["knee"] + h["hock"]) / 2, 0.026)                             # gaskin
        sc.capsule((h["knee"] + h["hock"]) / 2, h["hock"], 0.019)
        sc.ellipsoid(h["hock"] + Vector((0, -0.010, 0.004)), (0.017, 0.018, 0.019))           # point of hock
        sc.capsule(h["hock"], h["ball"], 0.019)
        sc.ellipsoid((0.090 * sx, -0.262, 0.024), (0.031, 0.044, 0.024))
    return sc.ob


def bake_sculpt(sculpt, target_faces=3600):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(sculpt.evaluated_get(dg))
    me.name = "DogBody"
    ob = bpy.data.objects.new("DogBody", me)
    bpy.context.collection.objects.link(ob)
    bpy.data.objects.remove(sculpt)
    for o in list(bpy.context.scene.objects):
        o.select_set(False)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    # metaball polygonisation is noisy; a voxel remesh makes it one clean manifold shell first
    mod = ob.modifiers.new("Voxel", "REMESH")
    mod.mode = "VOXEL"
    mod.voxel_size = 0.006
    mod.adaptivity = 0.0
    bpy.ops.object.modifier_apply(modifier=mod.name)
    raw_faces = len(ob.data.polygons)

    def relax(iterations):
        sm = ob.modifiers.new("Relax", "CORRECTIVE_SMOOTH")
        sm.factor = 0.5
        sm.iterations = iterations
        sm.smooth_type = "LENGTH_WEIGHTED"
        sm.use_only_smooth = True
        bpy.ops.object.modifier_apply(modifier=sm.name)

    relax(2)   # Quadriflow refuses the raw voxel shell (degenerate slivers); one light relax fixes it
    bpy.ops.object.quadriflow_remesh(target_faces=target_faces, use_mesh_symmetry=False, use_preserve_sharp=False,
                                     use_preserve_boundary=False, preserve_attributes=False, smooth_normals=False,
                                     mode="FACES", seed=7)
    if len(ob.data.polygons) > target_faces * 2:
        raise RuntimeError(f"Quadriflow did not run ({len(ob.data.polygons)} faces)")
    relax(4)   # take out quad-flow ripples without shrinking the silhouette much
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob, raw_faces


# ------------------------------------------------------------------ coat pattern -> u on the ramp
def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def window(x, lo, hi, soft):
    return smoothstep(lo - soft, lo + soft, x) * (1 - smoothstep(hi - soft, hi + soft, x))


def coat_u(p):
    x, y, z = p
    ax = abs(x)
    # dark saddle over the back, down onto the tail top, and the crown of the head
    saddle = smoothstep(0.495, 0.545, z) * window(y, -0.33, 0.21, 0.05)
    tail_top = smoothstep(-0.34, -0.40, y) * smoothstep(0.58, 0.625, z)
    crown = window(y, 0.37, 0.47, 0.03) * smoothstep(0.725, 0.765, z) * 0.7
    dark = max(saddle, tail_top, crown)
    # cream: muzzle and throat, chest front, belly, socks, tail tip
    muzzle = smoothstep(0.495, 0.525, y) * (1 - smoothstep(0.69, 0.71, z))
    throat = smoothstep(0.30, 0.36, y) * (1 - smoothstep(0.60, 0.66, z)) * (1 - smoothstep(0.035, 0.065, ax))
    chest = smoothstep(0.24, 0.30, y) * (1 - smoothstep(0.44, 0.52, z)) * (1 - smoothstep(0.05, 0.09, ax)) \
        * (1 - smoothstep(0.13, 0.20, z) * 0)  # (front of the chest, between the legs)
    belly = (1 - smoothstep(0.33, 0.37, z)) * window(y, -0.20, 0.28, 0.04) * (1 - smoothstep(0.05, 0.075, ax))
    socks = 1 - smoothstep(0.075, 0.115, z)
    tip = smoothstep(-0.585, -0.615, y)
    cream = max(muzzle, throat, chest, belly, socks, tip)
    u = 0.25 + 0.24 * dark
    u = u * (1 - cream) + 0.02 * cream
    return max(0.0, min(S.COAT_U_MAX, u))


def set_uvs(ob, u_of_loop):
    me = ob.data
    uv = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    for li, loop in enumerate(me.loops):
        uv.data[li].uv = (u_of_loop(loop), 0.5)


def colour_body(ob):
    me = ob.data
    us = [coat_u(v.co) for v in me.vertices]
    set_uvs(ob, lambda loop: us[loop.vertex_index])


# ------------------------------------------------------------------ helpers for accessories
def bvh_of(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    t = BVHTree.FromBMesh(bm)
    bm.free()
    return t


def hit(bvh, origin, direction):
    d = Vector(direction).normalized()
    loc, nrm, _i, _d = bvh.ray_cast(Vector(origin), d)
    if loc is None:
        raise RuntimeError(f"raycast from {origin} along {tuple(d)} missed the body")
    return loc, nrm


def mesh_object(name, bm, u, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = smooth
    if callable(u):
        set_uvs(ob, u)
    else:
        set_uvs(ob, lambda _l: u)
    return ob


def ellipsoid_bm(center, radii, rot=None, segs=12, rings=8):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=1.0)
    for v in bm.verts:
        co = Vector((v.co.x * radii[0], v.co.y * radii[1], v.co.z * radii[2]))
        if rot:
            co = rot @ co
        v.co = co + Vector(center)
    return bm


def make_eyes(bvh):
    """Eyeball (iris sphere), a round pupil skinned to four pupil bones, a catch light and two eyelid shells
    coloured like the surrounding coat. The eye frames go to the rig step through body["eye_bones"]."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "shared"))
    import face_rig as FR
    parts = []
    eyes = {}
    frames = {}
    for side, sx in (("L", 1), ("R", -1)):
        d = Vector((0.55 * sx, 0.78, 0.22)).normalized()
        p, n = hit(bvh, (0.0, 0.430, 0.712), d)
        r = S.EYE_R
        c = p - d * (r - S.EYE_PROTRUDE)
        # rig_dog rolls every bone so local Z = world X x bone direction: build the eye frame the same way
        X, Z, U, V = FR.frame(d, Vector((1, 0, 0)).cross(d))
        bm = bmesh.new()
        FR.sphere(bm, c, r, 20, 14)
        parts.append(mesh_object(f"Eye_{side}", bm, S.swatch_u("eye")))
        bm = bmesh.new()
        uv = FR.pupil(bm, c, d, U, V, r, S.PUPIL_HALF[0], S.PUPIL_HALF[1], lift=0.0008, rings=3, segs=20)
        bm.verts.index_update()
        weights = [(vv.index, FR.pupil_weights((a, b))) for vv, a, b in uv]
        pup = mesh_object(f"Pupil_{side}", bm, S.swatch_u("nose"))
        for role in ("W1", "W2", "H1", "H2"):
            vg = pup.vertex_groups.new(name=f"Pupil{role}_{side}")
            for vi, w in weights:
                vg.add([vi], w[role], "REPLACE")
        parts.append(pup)
        # catch-light: a flat bead on the upper outer front of the eyeball, under the lids when they close
        sdir = (d + V * 0.42 + U * (0.25 if U.x * sx > 0 else -0.25)).normalized()   # upper outer front
        rot = sdir.to_track_quat("Z", "Y").to_matrix()
        parts.append(mesh_object(f"EyeShine_{side}", ellipsoid_bm(c + sdir * (r + 0.0002), (0.0032, 0.0032, 0.0009),
                                                                  rot=rot, segs=8, rings=5), S.swatch_u("shine")))
        for which, edge, upper in (("Up", S.LID_UP_OPEN, True), ("Low", S.LID_LOW_OPEN, False)):
            bm = bmesh.new()
            FR.lid(bm, c, d, X, V, r * 1.04, r * 1.10, edge, upper)
            lid = mesh_object(f"EyeLid{which}_{side}", bm, 0.25)
            set_uvs(lid, lambda loop, me=lid.data: coat_u(me.vertices[loop.vertex_index].co))
            parts.append(lid)
        eyes[side] = c
        frames[side] = {"centre": list(c), "dir": list(d), "r": r}
    return parts, eyes, frames


def make_nose(bvh):
    p, n = hit(bvh, (0.0, 0.540, 0.676), (0, 1, 0.08))
    c = p + Vector((0, -0.004, 0.006))
    nose = ellipsoid_bm(c, (0.023, 0.017, 0.016), segs=12, rings=8)
    # flatten the underside a little, like a real nose leather
    for v in nose.verts:
        if v.co.z < c.z:
            v.co.z = c.z + (v.co.z - c.z) * 0.6
    ob = mesh_object("Nose", nose, S.swatch_u("nose"))
    # mouth line: a thin dark wedge under the muzzle sides
    return [ob], c


def make_ears(bvh):
    """Each ear: a cupped leaf (convex back, hollow front) that is thick at the root and folds forward at the tip.
    The root is welded to the skull: the lowest rings are projected onto the head surface and sunk into it, so the
    base follows the skull's curve with no gap, and the root is coloured like the coat there. The ear carries its own
    weights (written here as vertex groups): the root rides on Head, the leaf on Ear_L / Ear_R, blended over the
    lowest quarter so the base bends like skin when the ear moves instead of slicing through the head.
    Returns objects plus {side: (base, tip)} for the ear bones."""
    parts, bones = [], {}
    H, W = 0.105, 0.080
    seg = 14
    ts = [-0.30, -0.14, 0.0, 0.07, 0.18, 0.32, 0.47, 0.61, 0.74, 0.86, 0.95]
    for side, sx in (("L", 1), ("R", -1)):
        base, n = hit(bvh, (0.030 * sx, 0.415, 0.705), (0.42 * sx, -0.05, 1.0))
        up = Vector((0.38 * sx, -0.06, 1.0)).normalized()
        fwd = Vector((0, 1, 0))
        across = up.cross(fwd).normalized()
        if across.x * sx < 0:
            across = -across
        fold_axis = up.cross(fwd).normalized()

        def spine(t):
            """Centre line point and direction at height t (fraction of H); below 0 it continues straight down."""
            if t <= 0.55:
                return base + up * (H * t), up
            p = base + up * (H * 0.55)
            d = up
            steps = 8
            dt = (t - 0.55) / steps
            for k in range(steps):
                tm = 0.55 + dt * (k + 0.5)
                d = Quaternion(fold_axis, math.radians(40 * (tm - 0.55) / 0.45)) @ up
                p = p + d * (H * dt)
            return p, d

        bm = bmesh.new()
        rings, ring_t = [], []
        for t in ts:
            p, d = spine(t)
            nrm = across.cross(d).normalized()
            if nrm.y < 0:
                nrm = -nrm
            tt = max(t, 0.0)
            hw = W / 2 * (1 - tt) ** 0.85 + 0.003
            if t <= 0.07:
                hw *= 1.05                               # the root flares a little into the skull
            back = 0.020 * (1 - tt) ** 1.2 + 0.003       # convex back, thick at the root
            cup = 0.011 * (1 - tt) ** 1.1 + 0.0012       # hollow front, behind the rim line
            ring = []
            for k in range(seg):
                th = 2 * math.pi * k / seg
                s = math.sin(th)
                q = p + across * (hw * math.cos(th)) - nrm * (back * s if s >= 0 else cup * (-s))
                if t <= 0.0:
                    # weld: drop this point onto the skull along -up, then sink it into the head
                    loc, nn, _i, _d = bvh.ray_cast(q + up * 0.06, -up, 0.2)
                    if loc is not None:
                        q = loc - up * (0.003 + (-t) * 0.06)
                ring.append(bm.verts.new(q))
            rings.append(ring)
            ring_t.append(t)
        tip_p, tip_d = spine(1.0)
        tip = bm.verts.new(tip_p)
        faces = []
        pink, dark = S.swatch_u("ear_inner"), 0.47
        face_u = {}
        for i in range(len(rings) - 1):
            tm = (ring_t[i] + ring_t[i + 1]) / 2
            for k in range(seg):
                k2 = (k + 1) % seg
                f = bm.faces.new((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]))
                th = 2 * math.pi * (k + 0.5) / seg
                if tm < 0.0:
                    u = coat_u(f.calc_center_median())    # buried root: the head's coat colour
                elif math.sin(th) < -0.35 and 0.12 < tm < 0.84:
                    u = pink                              # inside of the cup
                else:
                    u = dark
                face_u[f] = u
                faces.append(f)
        for k in range(seg):
            f = bm.faces.new((rings[-1][k], rings[-1][(k + 1) % seg], tip))
            face_u[f] = dark
            faces.append(f)
        f = bm.faces.new(list(reversed(rings[0])))
        face_u[f] = coat_u(f.calc_center_median())
        faces.append(f)
        bmesh.ops.recalc_face_normals(bm, faces=faces)
        # per-vertex weights: root on the head, blending into the ear bone over the lowest quarter
        ear_w = {}
        for ring, t in zip(rings, ring_t):
            w = smoothstep(0.0, 0.26, t)
            for v in ring:
                ear_w[v] = w
        ear_w[tip] = 1.0
        bm.verts.index_update()
        weights = [(v.index, ear_w[v]) for v in bm.verts]
        order = list(bm.faces)
        us = [face_u[f] for f in order]
        me = bpy.data.meshes.new(f"Ear_{side}")
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(f"Ear_{side}", me)
        bpy.context.collection.objects.link(ob)
        uv = me.uv_layers.new(name="UVMap")
        for poly in me.polygons:
            poly.use_smooth = True
            for li in poly.loop_indices:
                uv.data[li].uv = (us[poly.index], 0.5)
        g_ear = ob.vertex_groups.new(name=f"Ear_{side}")
        g_head = ob.vertex_groups.new(name="Head")
        for vi, w in weights:
            if w > 1e-4:
                g_ear.add([vi], w, "REPLACE")
            if w < 1 - 1e-4:
                g_head.add([vi], 1 - w, "REPLACE")
        parts.append(ob)
        bones[side] = (tuple(base - up * 0.004), tuple(tip_p))
    return parts, bones


def make_collar(bvh):
    a = Vector(S.SPINE["Neck"][0])
    b = Vector(S.SPINE["Neck"][1])
    axis = (b - a).normalized()
    centre = a + (b - a) * 0.30
    # neck radius around this station
    ref = axis.cross(Vector((1, 0, 0))).normalized()
    radii = []
    for i in range(16):
        d = Quaternion(axis, 2 * math.pi * i / 16) @ ref
        p, _n = hit(bvh, centre, d)
        radii.append((p - centre).length)
    R = sum(radii) / len(radii) + 0.004
    r = 0.011
    bm = bmesh.new()
    seg, ring = 20, 6
    rows = []
    for i in range(seg):
        ang = 2 * math.pi * i / seg
        radial = Quaternion(axis, ang) @ ref
        row = []
        for j in range(ring):
            bj = 2 * math.pi * j / ring
            q = centre + radial * (R + r * math.cos(bj)) + axis * (r * 1.4 * math.sin(bj))
            row.append(bm.verts.new(q))
        rows.append(row)
    for i in range(seg):
        for j in range(ring):
            bm.faces.new((rows[i][j], rows[(i + 1) % seg][j], rows[(i + 1) % seg][(j + 1) % ring],
                          rows[i][(j + 1) % ring]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    collar = mesh_object("Collar", bm, S.swatch_u("collar"))
    # name tag hanging at the front-bottom of the collar
    low = None
    for i in range(32):
        d = Quaternion(axis, 2 * math.pi * i / 32) @ ref
        q = centre + d * (R + r)
        if low is None or q.z - 0.6 * q.y < low.z - 0.6 * low.y:
            low = q
    tag_c = low + Vector((0, 0.012, -0.016))
    tag = bmesh.new()
    bmesh.ops.create_cone(tag, cap_ends=True, segments=10, radius1=0.014, radius2=0.014, depth=0.004)
    rot = Vector((0, 0, 1)).rotation_difference(Vector((0, 1, 0.35)).normalized())
    for v in tag.verts:
        v.co = rot @ v.co + tag_c
    tag_ob = mesh_object("Tag", tag, S.swatch_u("tag"), smooth=False)
    return [collar, tag_ob]


# ------------------------------------------------------------------ previews
def setup_preview(sc):
    try:
        sc.render.engine = "BLENDER_EEVEE"
    except TypeError:
        sc.render.engine = "BLENDER_EEVEE_NEXT"
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    world = bpy.data.worlds.new("Preview")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.42, 0.46, 0.52, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.55
    sc.world = world
    coll = bpy.data.collections.new("Preview")
    sc.collection.children.link(coll)
    sun_d = bpy.data.lights.new("Sun", "SUN")
    sun_d.energy = 3.2
    sun_d.angle = math.radians(6)
    sun = bpy.data.objects.new("Sun", sun_d)
    sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(140))
    coll.objects.link(sun)
    me = bpy.data.meshes.new("Ground")
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=4)
    bm.to_mesh(me)
    bm.free()
    g = bpy.data.objects.new("Ground", me)
    gm = bpy.data.materials.new("Ground")
    gm.use_nodes = True
    gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.20, 0.24, 0.18, 1)
    me.materials.append(gm)
    coll.objects.link(g)
    cd = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cd)
    coll.objects.link(cam)
    sc.camera = cam
    return coll


def render_views(sc, prefix, views=("3q", "side", "front", "top"), res=720):
    cam = sc.camera
    target = Vector((0, -0.02, 0.36))
    setups = {
        "3q": ((1.35, 1.45, 0.75), 50, None),
        "side": ((2.2, -0.02, 0.36), 50, 1.45),
        "front": ((0.0, 2.2, 0.40), 50, 1.0),
        "back": ((0.0, -2.2, 0.40), 50, 1.0),
        "top": ((0.0, -0.02, 2.4), 50, 1.5),
        "head": ((0.55, 0.95, 0.80), 85, None),
    }
    paths = []
    for v in views:
        loc, lens, ortho = setups[v]
        cam.location = loc
        tgt = Vector((0, 0.48, 0.68)) if v == "head" else target
        cam.rotation_euler = (tgt - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        if v == "top":
            cam.rotation_euler = (0, 0, 0)
        cam.data.type = "ORTHO" if ortho else "PERSP"
        if ortho:
            cam.data.ortho_scale = ortho
        cam.data.lens = lens
        sc.render.resolution_x = res
        sc.render.resolution_y = int(res * (0.7 if v in ("side",) else 0.8))
        p = os.path.join(OUT, f"{prefix}-{v}.png")
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        paths.append(p)
    return paths


# ------------------------------------------------------------------ main
def build():
    sc = reset_scene()
    img = make_palette()
    mat = make_material(img)
    body, raw_faces = bake_sculpt(sculpt_body())
    colour_body(body)
    bvh = bvh_of(body)
    eyes, eye_pos, eye_frames = make_eyes(bvh)
    nose, nose_pos = make_nose(bvh)
    ears, ear_bones = make_ears(bvh)
    collar = make_collar(bvh)
    for ob in [body] + eyes + nose + ears + collar:
        ob.data.materials.clear()
        ob.data.materials.append(mat)
    info = {"raw_faces": raw_faces, "body_faces": len(body.data.polygons), "ear_bones": ear_bones,
            "eyes": {k: tuple(round(c, 4) for c in v) for k, v in eye_pos.items()}, "eye_frames": eye_frames}
    return sc, body, {"eyes": eyes, "nose": nose, "ears": ears, "collar": collar}, info


if __name__ == "__main__":
    import json
    sc, body, parts, info = build()
    # stash the accessory objects in a collection so the rig step can find them
    acc = bpy.data.collections.new("DogParts")
    sc.collection.children.link(acc)
    for group in parts.values():
        for ob in group:
            for c in ob.users_collection:
                c.objects.unlink(ob)
            acc.objects.link(ob)
    body["ear_bones"] = {k: [list(a), list(b)] for k, (a, b) in info["ear_bones"].items()}
    body["eye_bones"] = info.pop("eye_frames")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "Dog_mesh.blend"))
    if "--preview" in sys.argv:
        setup_preview(sc)
        render_views(sc, "mesh")
    me = body.data
    me.calc_loop_triangles()
    tris = len(me.loop_triangles) + sum(len(o.data.polygons) * 2 for g in parts.values() for o in g)
    lo = [min(v.co[i] for v in me.vertices) for i in range(3)]
    hi = [max(v.co[i] for v in me.vertices) for i in range(3)]
    print("RESULT", json.dumps({**info, "approx_tris": tris, "lo": [round(x, 3) for x in lo],
                                "hi": [round(x, 3) for x in hi]}))
