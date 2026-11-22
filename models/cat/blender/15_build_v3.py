"""v3 mesh: rebuild the cat's body and face from the measured references.

Run headless:
  blender -b models/cat/out/Cat.blend --python models/cat/blender/15_build_v3.py [-- --review]

Keeps the studio (camera, lights, floor, world) and the materials of Cat.blend,
removes the old Cat mesh / CatRig / actions, then builds
  * one metaball-sculpted fur body (Quadriflow quads, tuxedo vertex colours)
  * eyes (rim, iris, slit pupil, catch light), nose leather, mouth line,
    cupped ears, whiskers as separate parts tagged for rigid skinning
and saves blender/cat_v3_mesh.blend. --review renders out/review_v3_*.png.
"""
import bpy
import bmesh
import math
import os
import sys
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cat_spec as S  # noqa: E402

CAT = os.path.dirname(HERE)
OUT = os.path.join(CAT, "out")
REVIEW = "--review" in sys.argv

scene = bpy.context.scene

# ---------------------------------------------------------------- clear the old cat
for name in ("Cat", "CatRig"):
    ob = bpy.data.objects.get(name)
    if ob:
        bpy.data.objects.remove(ob, do_unlink=True)
for a in list(bpy.data.actions):
    bpy.data.actions.remove(a)
for me in list(bpy.data.meshes):
    if me.users == 0:
        bpy.data.meshes.remove(me)

MAT = {m.name: m for m in bpy.data.materials}
MAT["Cat_Fur"].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*S.BLACK, 1)
MAT["Cat_EyeAmber"].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.62, 0.46, 0.05, 1)
MAT["Cat_EyeAmber"].node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.18
MAT["Cat_Pupil"].node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.12
MAT["Cat_Pink"].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.60, 0.25, 0.27, 1)
SLOTS = ["Cat_FurVC", "Cat_Fur", "Cat_Pink", "Cat_EyeAmber", "Cat_Pupil", "Cat_Whisker", "Cat_Mouth"]


def activate(ob):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def apply_mod(ob, mod):
    activate(ob)
    bpy.ops.object.modifier_apply(modifier=mod.name)


def mirror(p):
    return (-p[0], p[1], p[2])


# ---------------------------------------------------------------- metaball sculpt
VIS = 0.574  # visible radius / element radius for one isolated element at stiffness 2


class Sculpt:
    def __init__(self, name):
        self.mb = bpy.data.metaballs.new(name)
        self.mb.resolution = 0.0035
        self.mb.render_resolution = 0.0035
        self.ob = bpy.data.objects.new(name, self.mb)
        scene.collection.objects.link(self.ob)

    def ellipsoid(self, c, half, rot=None, stiff=2.0):
        r = max(half)
        el = self.mb.elements.new(type="ELLIPSOID")
        el.co = c
        el.radius = r / VIS
        el.size_x, el.size_y, el.size_z = (half[0] / r, half[1] / r, half[2] / r)
        el.stiffness = stiff
        if rot is not None:
            el.rotation = Euler([math.radians(a) for a in rot]).to_quaternion()
        return el

    def capsule(self, a, b, r, stiff=2.0):
        a, b = Vector(a), Vector(b)
        el = self.mb.elements.new(type="CAPSULE")
        el.co = (a + b) / 2
        el.radius = r / VIS
        el.size_x = max(1e-4, (b - a).length / 2)
        el.rotation = Vector((1, 0, 0)).rotation_difference((b - a).normalized())
        el.stiffness = stiff
        return el


sc = Sculpt("CatSculpt")
for c, h in S.TORSO + S.WITHERS:
    sc.ellipsoid(c, h)
sc.capsule(*S.NECK)
sc.ellipsoid(*S.THROAT)
sc.ellipsoid(*S.CRANIUM)
sc.ellipsoid(*S.CHEEKS)
for c, h in S.WHISKER_PADS:
    sc.ellipsoid(c, h)
sc.ellipsoid(*S.CHIN)
sc.capsule(*S.NOSE_BRIDGE)
for i in range(4):
    sc.capsule(S.TAIL[i], S.TAIL[i + 1], S.TAIL_R[i])

for sx in (1, -1):
    def m(p):
        return (p[0] * sx, p[1], p[2])
    F, H = S.FRONT, S.HIND
    sc.ellipsoid(m(F["scapula"][0]), F["scapula"][1], rot=(-18, 0, 0))
    FR, HR = S.FRONT_R, S.HIND_R
    sc.capsule(m(F["shoulder"]), m(F["elbow"]), FR["upper"])
    mid = [(a + b) / 2 for a, b in zip(F["elbow"], F["wrist"])]
    sc.capsule(m(F["elbow"]), m(mid), FR["fore_top"])
    sc.capsule(m(mid), m(F["wrist"]), FR["fore_low"])
    sc.capsule(m(F["wrist"]), m((F["wrist"][0], F["wrist"][1] - 0.008, 0.021)), FR["wrist"])
    sc.ellipsoid(m(F["paw"][0]), F["paw"][1])

    sc.ellipsoid(m(H["thigh"][0]), H["thigh"][1], rot=(28, 0, 0))
    sc.capsule(m(H["hip"]), m(H["knee"]), HR["femur"])
    mid = [(a + b) / 2 for a, b in zip(H["knee"], H["hock"])]
    sc.capsule(m(H["knee"]), m(mid), HR["shin_top"])
    sc.capsule(m(mid), m(H["hock"]), HR["shin_low"])
    sc.ellipsoid(m(H["calf"][0]), H["calf"][1], rot=(-30, 0, 0))
    sc.ellipsoid(m((H["hock"][0], H["hock"][1] + 0.003, H["hock"][2])), (HR["hock"], HR["hock"] + 0.001, HR["hock"] + 0.001))
    sc.capsule(m(H["hock"]), m((H["hock"][0], 0.150, 0.023)), HR["meta"])
    sc.ellipsoid(m(H["paw"][0]), H["paw"][1])

bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
body_me = bpy.data.meshes.new_from_object(sc.ob.evaluated_get(dg))
body_me.name = "CatBodyMesh"
body = bpy.data.objects.new("CatBody", body_me)
scene.collection.objects.link(body)
bpy.data.objects.remove(sc.ob, do_unlink=True)
print("META", len(body.data.polygons))

mod = body.modifiers.new("Voxel", "REMESH")
mod.mode = "VOXEL"
mod.voxel_size = 0.0028
mod.adaptivity = 0.0
apply_mod(body, mod)


def relax(ob, iterations):
    sm = ob.modifiers.new("Relax", "CORRECTIVE_SMOOTH")
    sm.factor = 0.5
    sm.iterations = iterations
    sm.smooth_type = "LENGTH_WEIGHTED"
    sm.use_only_smooth = True
    apply_mod(ob, sm)


relax(body, 2)
activate(body)
TARGET = 4800
bpy.ops.object.quadriflow_remesh(target_faces=TARGET, use_mesh_symmetry=False, use_preserve_sharp=False,
                                 use_preserve_boundary=False, preserve_attributes=False, smooth_normals=False,
                                 mode="FACES", seed=7)
if len(body.data.polygons) > TARGET * 2:
    raise RuntimeError("Quadriflow did not run (%d faces)" % len(body.data.polygons))
relax(body, 4)
for p in body.data.polygons:
    p.use_smooth = True
print("BODY_QUADS", len(body.data.polygons))

# ---------------------------------------------------------------- tuxedo colours


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def ell(co, c, r):
    return math.sqrt(sum(((co[i] - c[i]) / r[i]) ** 2 for i in range(3)))


def seg_dist(p, a, b):
    a, b, p = Vector(a), Vector(b), Vector(p)
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
    return (p - (a + ab * t)).length


def white_amount(co):
    x, y, z = co
    ax = abs(x)
    soft = 0.011
    w = 0.0
    # muzzle, whisker pads and chin
    w = max(w, 1 - smoothstep(0.80, 1.18, ell(co, *S.MUZZLE_MASK)))
    # blaze: an inverted V running up the nose bridge between the eyes
    by, bz, slope = S.BLAZE
    if y < by and z < bz + 0.002:
        half = 0.004 + slope * (bz - z)
        w = max(w, 1 - smoothstep(half - soft * 0.5, half + soft * 0.5, ax))
    # chin, throat and chest bib (front and underside only)
    d = seg_dist(co, *S.THROAT_MASK)
    w = max(w, (1 - smoothstep(0.026, 0.044, d)) * smoothstep(0.035, 0.012, ax - 0.0))
    bib = 1 - smoothstep(0.75, 1.25, ell(co, (0, -0.205, 0.235), (0.040, 0.050, 0.070)))
    w = max(w, bib * (1 - smoothstep(-0.215, -0.175, y - 0.0) * smoothstep(0.24, 0.27, z)))
    # belly strip
    belly = 1 - smoothstep(0.85, 1.15, ell(co, (0, -0.030, 0.165), (0.036, 0.150, 0.030)))
    w = max(w, belly)
    # socks: front to the wrist, hind feet to just below the hock
    if y < 0.0:
        w = max(w, 1 - smoothstep(0.052, 0.062, z))
    else:
        w = max(w, 1 - smoothstep(0.040, 0.050, z))
    return min(1.0, w)


col = body.data.color_attributes.new(name="Col", type="FLOAT_COLOR", domain="POINT")
for v in body.data.vertices:
    w = white_amount(v.co)
    col.data[v.index].color = (*[S.BLACK[k] * (1 - w) + S.WHITE[k] * w for k in range(3)], 1.0)
body.data.materials.append(MAT["Cat_FurVC"])

bm_body = bmesh.new()
bm_body.from_mesh(body.data)
bvh = BVHTree.FromBMesh(bm_body)


def surface(origin, direction, max_d=0.3):
    """First hit of a ray against the fur body (world == local, body sits at the origin)."""
    loc, nrm, idx, dist = bvh.ray_cast(Vector(origin), Vector(direction).normalized(), max_d)
    if loc is None:
        raise RuntimeError("ray missed the body from %s" % (origin,))
    return loc, nrm


# ---------------------------------------------------------------- parts helpers
PARTS = []


def part(name, bm, material, bone, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    for s in SLOTS:
        me.materials.append(MAT[s])
    for p in me.polygons:
        p.material_index = SLOTS.index(material) if isinstance(material, str) else material(p)
        p.use_smooth = smooth
    ob["bone"] = bone
    PARTS.append(ob)
    return ob


def sphere_bm(radius, seg=16, rings=10):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=radius)
    return bm


def transform_bm(bm, mat):
    bmesh.ops.transform(bm, matrix=mat, verts=bm.verts)


def look_matrix(direction, up=(0, 0, 1)):
    """Rotation whose local -Y points along `direction` (local Z stays near `up`)."""
    d = Vector(direction).normalized()
    return (-d).to_track_quat("Y", "Z").to_matrix().to_4x4()


# ---------------------------------------------------------------- eyes + face rig parts (shared/face_rig.py)
sys.path.insert(0, os.path.join(os.path.dirname(CAT), "shared"))
import face_rig as FR  # noqa: E402

for sx, side in ((1, "L"), (-1, "R")):
    yaw = math.radians(S.EYE_YAW) * sx
    pitch = math.radians(S.EYE_PITCH)
    d = Vector((math.sin(yaw) * math.cos(pitch), -math.cos(yaw) * math.cos(pitch), math.sin(pitch)))
    c0 = Vector((S.EYE_CENTRE[0] * sx, S.EYE_CENTRE[1], S.EYE_CENTRE[2]))
    hit, _ = surface(c0 + d * 0.08, -d)
    r = S.EYE_RADIUS
    centre = hit - d * (r - S.EYE_PROTRUDE)
    X, Z, U, V = FR.frame(d, (0, 0, 1))
    # iris: a whole sphere, so lids and pupil can turn about its centre
    bm = bmesh.new()
    FR.sphere(bm, centre, r, 24, 16)
    eye = part(f"Eye_{side}", bm, "Cat_EyeAmber", "Head")
    eye["eye"] = {"centre": list(centre), "dir": list(d), "up": list(Z), "r": r}
    # slit pupil on the iris, skinned to the four pupil bones
    bm = bmesh.new()
    uv = FR.pupil(bm, centre, d, U, V, r, S.PUPIL_HALF[0], S.PUPIL_HALF[1], lift=0.0008)
    bm.verts.index_update()
    weights = [(vv.index, FR.pupil_weights((a, b))) for vv, a, b in uv]
    pup = part(f"Pupil_{side}", bm, "Cat_Pupil", "__custom__")
    for role in ("W1", "W2", "H1", "H2"):
        vg = pup.vertex_groups.new(name=f"Pupil{role}.{side}")
        for vi, w in weights:
            vg.add([vi], w[role], "REPLACE")
    # catch light: a flat bead on the upper outer front of the eyeball (stays put while the pupil changes)
    sdir = (d + V * 0.42 + U * (0.26 * sx)).normalized()
    bm = sphere_bm(1.0, 8, 6)
    transform_bm(bm, Matrix.Translation(centre + sdir * (r + 0.0002)) @ look_matrix(sdir)
                 @ Matrix.Diagonal((0.0023, 0.0007, 0.0023, 1)))
    part(f"EyeShine_{side}", bm, "Cat_Whisker", "Head")
    # eyelids: black fur shells that slide over the eyeball
    for which, edge, upper in (("Up", S.LID_UP_OPEN, True), ("Low", S.LID_LOW_OPEN, False)):
        bm = bmesh.new()
        FR.lid(bm, centre, d, X, V, r * 1.035, r * 1.09, edge, upper)
        part(f"EyeLid{which}_{side}", bm, "Cat_Fur", f"EyeLid{which}.{side}")

# ---------------------------------------------------------------- nose leather (rounded triangle)
tip, tip_n = surface((0, -0.45, 0.352), (0, 1, 0))
bm = bmesh.new()
nose_pts = [(-0.0075, 0.0, 0.0035), (0.0075, 0.0, 0.0035), (0.0, 0.0, -0.0055)]
top = [bm.verts.new(p) for p in nose_pts]
back = [bm.verts.new((p[0] * 0.8, 0.006, p[2] * 0.8)) for p in nose_pts]
front_c = bm.verts.new((0, -0.0025, 0.0005))
for i in range(3):
    j = (i + 1) % 3
    bm.faces.new((top[i], top[j], front_c))
    bm.faces.new((top[j], top[i], back[i], back[j]))
bm.faces.new(list(reversed(back)))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
transform_bm(bm, Matrix.Translation(tip + Vector((0, -0.0008, 0.0012))) @ Euler((math.radians(-18), 0, 0)).to_matrix().to_4x4())
part("Nose", bm, "Cat_Pink", "Head", smooth=False)


# ---------------------------------------------------------------- thin tubes (mouth line, whiskers)
def tube(path, radii, sides=5):
    bm = bmesh.new()
    rings = []
    path = [Vector(p) for p in path]
    for i, p in enumerate(path):
        t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        a = t.orthogonal().normalized()
        b = t.cross(a)
        ring = []
        for k in range(sides):
            ang = 2 * math.pi * k / sides
            ring.append(bm.verts.new(p + (a * math.cos(ang) + b * math.sin(ang)) * radii[i]))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(sides):
            k2 = (k + 1) % sides
            bm.faces.new((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def on_skin(x, z, lift=0.0007):
    loc, n = surface((x, -0.45, z), (0, 1, 0))
    return loc + n * lift


# mouth: philtrum down from the nose, then two arcs (an inverted "Y")
mouth = []
phil = [on_skin(0.0, tip.z - 0.007), on_skin(0.0, tip.z - 0.012), on_skin(0.0, tip.z - 0.0165)]
mouth.append(tube(phil, [0.0008] * 3))
for sx in (1, -1):
    arc = [on_skin(0.0, tip.z - 0.0165)] + [on_skin(sx * 0.004 * k, tip.z - 0.0165 - 0.0024 * math.sin(k * 0.55)) for k in (1, 2, 3, 4)]
    arc[-1] = on_skin(sx * 0.0165, tip.z - 0.0135)
    mouth.append(tube(arc, [0.0008, 0.0008, 0.0008, 0.0007, 0.0005]))
bm = bmesh.new()
tmp = bpy.data.meshes.new("tmp")
for t in mouth:
    t.to_mesh(tmp)
    bm.from_mesh(tmp)
    t.free()
bpy.data.meshes.remove(tmp)
part("Mouth", bm, "Cat_Mouth", "Head")

# whiskers: four per side from the whisker pads, fanning out and drooping slightly
bm = bmesh.new()
tmp = bpy.data.meshes.new("tmp")
for sx in (1, -1):
    for k, (dz, spread, droop) in enumerate(((0.006, 8, 4), (0.002, 0, 9), (-0.002, -8, 14), (-0.006, -14, 19))):
        root = on_skin(sx * 0.016, tip.z - 0.006 + dz, lift=-0.001)
        yaw = math.radians(58 + spread * 0.4) * sx
        pitch = math.radians(spread * 0.6)
        dirv = Vector((math.sin(yaw), -math.cos(yaw) * 0.55, math.sin(pitch))).normalized()
        L = 0.068 - k * 0.004
        pts = []
        for i in range(5):
            t = i / 4
            p = root + dirv * (L * t)
            p.z -= math.radians(droop) * L * t * t * 0.9
            pts.append(p)
        tb = tube(pts, [0.0009, 0.0008, 0.0007, 0.0005, 0.0003], sides=4)
        tb.to_mesh(tmp)
        bm.from_mesh(tmp)
        tb.free()
bpy.data.meshes.remove(tmp)
part("Whiskers", bm, "Cat_Whisker", "Head", smooth=False)


# ---------------------------------------------------------------- ears: cupped crescent shells
def ear_bm(sx):
    w, dep, h = S.EAR_SIZE
    seg = 14
    ts = [-0.30, 0.0, 0.22, 0.44, 0.64, 0.82, 0.94]
    bm = bmesh.new()
    rings = []
    for t in ts:
        tt = max(t, 0.0)
        wt = w * (1 - tt) * (1 + 0.22 * math.sin(math.pi * tt))
        dt = dep * (1 - tt) ** 0.8
        # lean the outer edge forward a little (the ear's leading edge is straighter)
        ring = []
        for k in range(seg):
            th = 2 * math.pi * k / seg
            x = wt * math.cos(th)
            s = math.sin(th)
            if s >= 0:          # back of the ear: convex
                y = dt * s + 0.0015
            else:               # front: hollow cup, still behind the rim line
                y = dt * 0.45 * (-s) * min(1.0, (1 - tt) * 3)
            ring.append(bm.verts.new((x, y, h * t)))
        rings.append(ring)
    tipv = bm.verts.new((0.0, 0.002, h))
    pink_faces = []
    for i in range(len(rings) - 1):
        for k in range(seg):
            k2 = (k + 1) % seg
            f = bm.faces.new((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]))
            th = 2 * math.pi * (k + 0.5) / seg
            if math.sin(th) < -0.45 and 1 <= i <= len(rings) - 3:
                pink_faces.append(f)
    for k in range(seg):
        bm.faces.new((rings[-1][k], rings[-1][(k + 1) % seg], tipv))
    bm.faces.new(list(reversed(rings[0])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    pink = set(f.index for f in pink_faces) if False else None
    for f in bm.faces:
        f.material_index = SLOTS.index("Cat_Fur")
    for f in pink_faces:
        f.material_index = SLOTS.index("Cat_Pink")
    return bm


for sx, side in ((1, "L"), (-1, "R")):
    bx, by, bz = S.EAR_BASE
    hit, n = surface((bx * sx, by, 0.6), (0, 0, -1))
    base = hit - Vector((0, 0, 0.004))
    R = (Euler((0, 0, math.radians(S.EAR_YAW) * sx)).to_matrix()
         @ Euler((0, math.radians(S.EAR_TILT) * sx, 0)).to_matrix()
         @ Euler((math.radians(S.EAR_PITCH), 0, 0)).to_matrix()).to_4x4()
    bm = ear_bm(sx)
    transform_bm(bm, Matrix.Translation(base) @ R)
    me = bpy.data.meshes.new(f"Ear_{side}")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(f"Ear_{side}", me)
    scene.collection.objects.link(ob)
    for s in SLOTS:
        me.materials.append(MAT[s])
    for p in me.polygons:
        p.use_smooth = True
    ob["bone"] = f"Ear.{side}"
    ob["ear_base"] = list(base)
    ob["ear_tip"] = list(Matrix.Translation(base) @ R @ Vector((0, 0, S.EAR_SIZE[2])))
    PARTS.append(ob)

bm_body.free()

# body gets the same material slot list so joins keep indices
body.data.materials.clear()
for s in SLOTS:
    body.data.materials.append(MAT[s])
for p in body.data.polygons:
    p.material_index = 0
for ob in PARTS:
    c = ob.data.color_attributes.new(name="Col", type="FLOAT_COLOR", domain="POINT")
    for d in c.data:
        d.color = (1, 1, 1, 1)

body.name = "Cat"
body.data.name = "Cat"
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "cat_v3_mesh.blend"))
tris = sum(len(p.vertices) - 2 for p in body.data.polygons) + sum(len(p.vertices) - 2 for o in PARTS for p in o.data.polygons)
print("RESULT", {"body_quads": len(body.data.polygons), "parts": [o.name for o in PARTS], "tris": tris})

# ---------------------------------------------------------------- review renders
if REVIEW:
    cam = scene.camera
    scene.render.image_settings.file_format = "PNG"
    try:
        scene.eevee.taa_render_samples = 24
    except Exception:
        pass

    def shot(name, loc, target, ortho=None, res=(900, 700), lens=70):
        scene.render.resolution_x, scene.render.resolution_y = res
        cam.location = loc
        cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        cam.data.type = "ORTHO" if ortho else "PERSP"
        if ortho:
            cam.data.ortho_scale = ortho
        else:
            cam.data.lens = lens
        scene.render.filepath = os.path.join(OUT, f"review_v3_{name}.png")
        bpy.ops.render.render(write_still=True)

    shot("side", (1.9, 0.02, 0.25), (0, 0.02, 0.25), ortho=0.86, res=(1000, 760))
    shot("3q", (1.25, -1.55, 0.72), (0, 0.0, 0.22), res=(1000, 820))
    shot("front", (0.0, -1.6, 0.36), (0, 0, 0.24), ortho=0.56, res=(760, 760))
    shot("head", (0.30, -0.78, 0.46), (0, -0.28, 0.36), ortho=0.26, res=(800, 800))
    shot("rear3q", (0.9, 1.25, 0.6), (0, 0.05, 0.2), res=(1000, 820))
    print("REVIEW_DONE")
