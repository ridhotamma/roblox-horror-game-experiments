"""Stage 1: stylized low-poly cat (voxel-unioned body, explicit head details).

Cat faces -Y (glTF +Z after export), ground at z = 0.
Reference: domestic cat, ~0.57 m nose-to-tail-base, ~0.30 m shoulder height.
Run with: exec(compile(open(path).read(), "01_build.py", "exec"))
"""
import bpy
import bmesh
import math
import os
from math import cos, sin, pi
from mathutils import Vector

OUT = r"C:\Users\ridho\kerjaan\roblox-horror-game-experiments\models\cat"
RENDER_DIR = os.path.join(OUT, "out")
os.makedirs(RENDER_DIR, exist_ok=True)

bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.fps = 24
scene.render.resolution_x = 900
scene.render.resolution_y = 900
scene.render.image_settings.file_format = 'PNG'
try:
    scene.eevee.taa_render_samples = 48
except Exception:
    pass
try:
    scene.view_settings.look = 'AgX - Medium High Contrast'
except Exception:
    pass


# ---------------------------------------------------------------- materials
def mat(name, color, roughness=0.7, metallic=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return m


M_FUR = mat("Cat_Fur", (0.052, 0.060, 0.072), 0.85)
M_CREAM = mat("Cat_Cream", (0.640, 0.600, 0.540), 0.88)
M_PINK = mat("Cat_Pink", (0.520, 0.240, 0.260), 0.60)
M_EYE = mat("Cat_EyeAmber", (0.700, 0.470, 0.060), 0.20)
M_PUPIL = mat("Cat_Pupil", (0.008, 0.008, 0.010), 0.12)
M_WHITE = mat("Cat_Whisker", (0.780, 0.760, 0.720), 0.55)
M_MOUTH = mat("Cat_Mouth", (0.020, 0.016, 0.016), 0.80)

M_FUR_VC = bpy.data.materials.new("Cat_FurVC")
M_FUR_VC.use_nodes = True
_bsdf = M_FUR_VC.node_tree.nodes.get("Principled BSDF")
_bsdf.inputs["Roughness"].default_value = 0.85
_vc = M_FUR_VC.node_tree.nodes.new("ShaderNodeVertexColor")
_vc.layer_name = "Col"
M_FUR_VC.node_tree.links.new(_vc.outputs["Color"], _bsdf.inputs["Base Color"])


# ---------------------------------------------------------------- helpers
def new_object(name, verts, faces, materials, smooth=True):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.validate(verbose=False)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    for m in materials:
        mesh.materials.append(m)
    for p in mesh.polygons:
        p.use_smooth = smooth
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(ob)
    return ob


def loft_y(name, stations, sides=16, material=M_FUR_VC, smooth=True):
    verts, rings = [], []
    for (y, zc, w, h) in stations:
        ring = []
        for i in range(sides):
            a = 2 * pi * i / sides
            ring.append(len(verts))
            verts.append((w * cos(a), y, zc + h * sin(a)))
        rings.append(ring)
    faces = []
    for s in range(len(rings) - 1):
        for i in range(sides):
            faces.append((rings[s][i], rings[s][(i + 1) % sides],
                          rings[s + 1][(i + 1) % sides], rings[s + 1][i]))
    y0, z0, _, _ = stations[0]
    c0 = len(verts); verts.append((0.0, y0, z0))
    for i in range(sides):
        faces.append((c0, rings[0][(i + 1) % sides], rings[0][i]))
    y1, z1, _, _ = stations[-1]
    c1 = len(verts); verts.append((0.0, y1, z1))
    for i in range(sides):
        faces.append((c1, rings[-1][i], rings[-1][(i + 1) % sides]))
    return new_object(name, verts, faces, [material], smooth)


def tube_along(name, path, sides=8, material=M_FUR_VC, smooth=True):
    pts = [Vector(p[:3]) for p in path]
    radii = [p[3] for p in path]
    verts, rings = [], []
    for i, p in enumerate(pts):
        if i == 0:
            t = (pts[1] - pts[0]).normalized()
        elif i == len(pts) - 1:
            t = (pts[-1] - pts[-2]).normalized()
        else:
            t = (pts[i + 1] - pts[i - 1]).normalized()
        side = Vector((1, 0, 0))
        if abs(t.dot(side)) > 0.95:
            side = Vector((0, 1, 0))
        up = t.cross(side).normalized()
        side = up.cross(t).normalized()
        ring = []
        for k in range(sides):
            a = 2 * pi * k / sides
            ring.append(len(verts))
            verts.append(tuple(p + side * (radii[i] * cos(a)) + up * (radii[i] * sin(a))))
        rings.append(ring)
    faces = []
    for s in range(len(rings) - 1):
        for i in range(sides):
            faces.append((rings[s][i], rings[s][(i + 1) % sides],
                          rings[s + 1][(i + 1) % sides], rings[s + 1][i]))
    c = len(verts); verts.append(tuple(pts[0]))
    for i in range(sides):
        faces.append((c, rings[0][(i + 1) % sides], rings[0][i]))
    c = len(verts); verts.append(tuple(pts[-1]))
    for i in range(sides):
        faces.append((c, rings[-1][i], rings[-1][(i + 1) % sides]))
    return new_object(name, verts, faces, [material], smooth)


def ico(name, loc, scale, material, subdiv=2, rot=(0, 0, 0), smooth=True):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdiv, radius=1.0, location=loc)
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.scale = scale
    ob.rotation_euler = rot
    ob.data.materials.append(material)
    for p in ob.data.polygons:
        p.use_smooth = smooth
    return ob


def uvsphere(name, loc, scale, material, segments=14, rings=9, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=1.0, location=loc)
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.scale = scale
    ob.rotation_euler = rot
    ob.data.materials.append(material)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def tag_all(objs, group_name):
    for ob in objs:
        vg = ob.vertex_groups.new(name=group_name)
        vg.add(list(range(len(ob.data.vertices))), 1.0, 'REPLACE')


def apply_modifier(ob, name):
    with bpy.context.temp_override(object=ob, active_object=ob,
                                   selected_objects=[ob], selected_editable_objects=[ob]):
        bpy.ops.object.modifier_apply(modifier=name)


def join_objects(active, objs):
    bpy.ops.object.select_all(action='DESELECT')
    for ob in objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = active
    with bpy.context.temp_override(object=active, active_object=active,
                                   selected_objects=objs, selected_editable_objects=objs):
        bpy.ops.object.join()
    return bpy.context.view_layer.objects.active


# ---------------------------------------------------------------- body + head
STATIONS = [
    (0.205, 0.248, 0.046, 0.048),
    (0.178, 0.249, 0.070, 0.070),
    (0.120, 0.251, 0.081, 0.078),
    (0.045, 0.249, 0.081, 0.078),
    (-0.035, 0.248, 0.084, 0.081),
    (-0.105, 0.253, 0.080, 0.082),
    (-0.155, 0.264, 0.064, 0.069),
    (-0.190, 0.279, 0.054, 0.060),
    (-0.225, 0.296, 0.061, 0.061),
    (-0.260, 0.307, 0.070, 0.063),
    (-0.298, 0.308, 0.068, 0.060),
    (-0.328, 0.302, 0.056, 0.050),
    (-0.350, 0.294, 0.043, 0.039),
    (-0.368, 0.290, 0.028, 0.026),
    (-0.382, 0.290, 0.012, 0.012),
]
body = loft_y("CatBody", STATIONS, sides=16)

TAIL_PATH = [
    (0.000, 0.195, 0.252, 0.034),
    (0.000, 0.252, 0.270, 0.032),
    (0.000, 0.306, 0.298, 0.028),
    (0.000, 0.352, 0.338, 0.024),
    (0.000, 0.388, 0.388, 0.019),
    (0.000, 0.410, 0.443, 0.013),
    (0.000, 0.421, 0.498, 0.007),
]
tail = tube_along("CatTail", TAIL_PATH, sides=8)

FRONT_PATH_L = [
    (0.058, -0.104, 0.268, 0.040),
    (0.058, -0.101, 0.212, 0.034),
    (0.058, -0.094, 0.170, 0.029),
    (0.058, -0.073, 0.130, 0.026),
    (0.058, -0.083, 0.092, 0.022),
    (0.058, -0.095, 0.057, 0.019),
    (0.058, -0.106, 0.040, 0.021),
]
BACK_PATH_L = [
    (0.061, 0.152, 0.278, 0.054),
    (0.061, 0.152, 0.218, 0.048),
    (0.062, 0.176, 0.173, 0.040),
    (0.062, 0.200, 0.134, 0.030),
    (0.062, 0.192, 0.100, 0.024),
    (0.062, 0.176, 0.070, 0.020),
    (0.062, 0.160, 0.046, 0.021),
]

fur_parts = [body, tail]
for side, sx in (("L", 1), ("R", -1)):
    fp = [(x * sx, y, z, r) for (x, y, z, r) in FRONT_PATH_L]
    bp = [(x * sx, y, z, r) for (x, y, z, r) in BACK_PATH_L]
    fur_parts.append(tube_along(f"FrontLeg_{side}", fp, sides=8))
    fur_parts.append(tube_along(f"BackLeg_{side}", bp, sides=8))
    fur_parts.append(ico(f"FrontPaw_{side}", (0.058 * sx, -0.120, 0.026),
                         (0.032, 0.048, 0.026), M_FUR_VC, subdiv=2, smooth=True))
    fur_parts.append(ico(f"BackPaw_{side}", (0.060 * sx, 0.124, 0.026),
                         (0.033, 0.050, 0.026), M_FUR_VC, subdiv=2, smooth=True))
    for t, dx in enumerate((-0.021, 0.0, 0.021)):
        fur_parts.append(ico(f"FrontToe_{side}{t}", (0.058 * sx + dx, -0.157, 0.018),
                             (0.011, 0.015, 0.017), M_FUR_VC, subdiv=2, smooth=True))
        fur_parts.append(ico(f"BackToe_{side}{t}", (0.060 * sx + dx, 0.081, 0.018),
                             (0.012, 0.016, 0.017), M_FUR_VC, subdiv=2, smooth=True))

# ---------------------------------------------------------------- voxel union -> one body
fur = join_objects(body, fur_parts)
fur.name = "CatFur"
try:
    fur.data.remesh_voxel_size = 0.0036
    fur.data.remesh_voxel_adaptivity = 0.0
    fur.data.use_remesh_preserve_volume = True
    with bpy.context.temp_override(object=fur, active_object=fur,
                                   selected_objects=[fur], selected_editable_objects=[fur]):
        bpy.ops.object.voxel_remesh()
    print("VOXEL_REMESH done")
except Exception as e:
    print("VOXEL_OP_SKIPPED", repr(e))
    rm = fur.modifiers.new("Remesh", 'REMESH')
    rm.mode = 'VOXEL'
    rm.voxel_size = 0.0036
    rm.use_smooth_shade = True
    apply_modifier(fur, "Remesh")

fur.data.calc_loop_triangles()
tris_after_remesh = len(fur.data.loop_triangles)
print("TRIS_AFTER_REMESH", tris_after_remesh)

# soften voxel stairs
sm = fur.modifiers.new("Smooth", 'SMOOTH')
sm.factor = 0.45
sm.iterations = 2
apply_modifier(fur, "Smooth")

# decimate to a game budget
fur.data.calc_loop_triangles()
tris = len(fur.data.loop_triangles)
dec = fur.modifiers.new("Decimate", 'DECIMATE')
dec.ratio = min(1.0, 4500.0 / max(1, tris))
apply_modifier(fur, "Decimate")
for p in fur.data.polygons:
    p.use_smooth = True
print("TRIS_AFTER_DECIMATE", len(fur.data.loop_triangles))

# ---------------------------------------------------------------- tuxedo vertex colours
def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def ellipsoid_mask(co, center, radii, soft=0.18):
    d = math.sqrt(sum(((co[i] - center[i]) / radii[i]) ** 2 for i in range(3)))
    return 1.0 - smoothstep(1.0 - soft, 1.0 + soft, d)


FUR_LIN = (0.050, 0.058, 0.070)
CREAM_LIN = (0.620, 0.585, 0.530)
me = fur.data
attr = me.color_attributes.new(name="Col", type='FLOAT_COLOR', domain='POINT')
for i, v in enumerate(me.vertices):
    co = v.co
    belly = ellipsoid_mask(co, (0.0, 0.005, 0.162), (0.083, 0.235, 0.058), 0.30)
    chest = ellipsoid_mask(co, (0.0, -0.168, 0.242), (0.063, 0.105, 0.100), 0.30)
    muzzle = ellipsoid_mask(co, (0.0, -0.360, 0.292), (0.062, 0.070, 0.052), 0.30)
    socks = 1.0 - smoothstep(0.032, 0.060, co.z)
    tip = smoothstep(0.400, 0.418, co.y)
    cream = min(1.0, max(belly, chest, muzzle, socks, tip) * 1.05)
    col = tuple(FUR_LIN[k] * (1 - cream) + CREAM_LIN[k] * cream for k in range(3))
    attr.data[i].color = (*col, 1.0)

# ---------------------------------------------------------------- ears
def make_ear(side, sx):
    A = Vector((-0.038, -0.022, 0.0))
    B = Vector(( 0.038, -0.022, 0.0))
    C = Vector(( 0.000,  0.028, 0.0))
    D = Vector(( 0.000, -0.002, 0.080))
    v = [tuple(A), tuple(B), tuple(C), tuple(D)]
    f = [(0, 1, 3), (1, 2, 3), (2, 0, 3), (0, 2, 1)]
    ob = new_object(f"Ear_{side}", v, f, [M_FUR], smooth=False)
    n = (B - A).cross(D - A).normalized()

    def inset(t, u):
        return A.lerp(B, t).lerp(D, u) + n * 0.0018

    a, b, c = inset(0.17, 0.07), inset(0.83, 0.07), inset(0.50, 0.80)
    off = n * 0.0014
    iv = [tuple(a), tuple(b), tuple(c), tuple(a + off), tuple(b + off), tuple(c + off)]
    inf = [(0, 1, 2), (5, 4, 3), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)]
    inner = new_object(f"EarInner_{side}", iv, inf, [M_PINK], smooth=False)
    ob = join_objects(ob, [inner, ob])
    ob.location = (0.034 * sx, -0.258, 0.331)
    ob.rotation_euler = (math.radians(-5), math.radians(8 * sx), 0)
    return ob


ear_l = make_ear("L", 1)
ear_r = make_ear("R", -1)

# ---------------------------------------------------------------- eyes / nose / mouth / whiskers
eyes = []
for side, sx in (("L", 1), ("R", -1)):
    eye = uvsphere(f"Eye_{side}", (0.038 * sx, -0.338, 0.318),
                   (0.0165, 0.0105, 0.0175), M_EYE, segments=14, rings=9,
                   rot=(0, 0, math.radians(20 * sx)))
    pupil = ico(f"Pupil_{side}", (0.0422 * sx, -0.3465, 0.318),
                (0.0042, 0.0028, 0.0112), M_PUPIL, subdiv=2,
                rot=(0, 0, math.radians(20 * sx)))
    hi = ico(f"EyeHi_{side}", (0.0452 * sx, -0.3475, 0.3245),
             (0.0021, 0.0015, 0.0021), M_WHITE, subdiv=1)
    eyes += [eye, pupil, hi]

nv = [(-0.0105, -0.385, 0.298), (0.0105, -0.385, 0.298), (0.0, -0.385, 0.285),
      (-0.0105, -0.378, 0.298), (0.0105, -0.378, 0.298), (0.0, -0.378, 0.285)]
nf = [(0, 1, 2), (5, 4, 3), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)]
nose = new_object("Nose", nv, nf, [M_PINK], smooth=False)

mouth_objs = []
MOUTH_LINES = [
    ((0.000, -0.3828, 0.2845), (0.000, -0.3808, 0.2803)),
    ((0.000, -0.3808, 0.2803), (0.0115, -0.3748, 0.2826)),
    ((0.000, -0.3808, 0.2803), (-0.0115, -0.3748, 0.2826)),
]
for i, (a, b) in enumerate(MOUTH_LINES):
    p1, p2 = Vector(a), Vector(b)
    mid, d = (p1 + p2) / 2, p2 - p1
    bpy.ops.mesh.primitive_cylinder_add(vertices=3, radius=0.0008, depth=d.length, location=mid)
    ob = bpy.context.view_layer.objects.active
    ob.name = f"Mouth{i}"
    ob.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    ob.data.materials.append(M_MOUTH)
    mouth_objs.append(ob)

whisker_objs = []
W_LINES = [
    ((0.027, -0.368, 0.302), (0.118, -0.393, 0.320)),
    ((0.028, -0.368, 0.294), (0.126, -0.372, 0.297)),
    ((0.025, -0.364, 0.286), (0.108, -0.350, 0.270)),
]
for side, sx in (("L", 1), ("R", -1)):
    for i, (a, b) in enumerate(W_LINES):
        p1 = Vector((a[0] * sx, a[1], a[2]))
        p2 = Vector((b[0] * sx, b[1], b[2]))
        mid, d = (p1 + p2) / 2, p2 - p1
        bpy.ops.mesh.primitive_cylinder_add(vertices=3, radius=0.0009, depth=d.length, location=mid)
        ob = bpy.context.view_layer.objects.active
        ob.name = f"Whisker_{side}{i}"
        ob.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
        ob.data.materials.append(M_WHITE)
        whisker_objs.append(ob)

tag_all([ear_l], "TAG_Ear_L")
tag_all([ear_r], "TAG_Ear_R")
tag_all(eyes + [nose] + whisker_objs + mouth_objs, "TAG_Head")

all_parts = [fur, ear_l, ear_r] + eyes + [nose] + whisker_objs + mouth_objs
cat = join_objects(fur, all_parts)
cat.name = "Cat"
bpy.ops.object.select_all(action='DESELECT')

# accessory islands use their own materials -> neutral white vertex colour
# (COLOR_0 multiplies base colour in glTF/Roblox; black would tint them black)
_me = cat.data
_fur_i = _me.materials.find("Cat_FurVC")
_col = _me.color_attributes.get("Col")
if _col:
    _white = set()
    for _p in _me.polygons:
        if _p.material_index != _fur_i:
            for _vi in _p.vertices:
                if _vi not in _white:
                    _col.data[_vi].color = (1.0, 1.0, 1.0, 1.0)
                    _white.add(_vi)
    print("WHITE_ACCESSORY_VERTS", len(_white))

# ---------------------------------------------------------------- studio
def add_area(name, loc, energy, size, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = energy
    ld.shape = 'DISK'
    ld.size = size
    ld.color = color
    ob = bpy.data.objects.new(name, ld)
    bpy.context.collection.objects.link(ob)
    ob.location = loc
    d = Vector((0, 0, 0.24)) - Vector(loc)
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return ob


world = bpy.data.worlds.new("StudioWorld")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.026, 0.028, 0.032, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 1.0
scene.world = world

bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 0, 0))
floor = bpy.context.view_layer.objects.active
floor.name = "StudioFloor"
floor.data.materials.append(mat("StudioFloor", (0.040, 0.044, 0.050), 0.9))

add_area("Key", (1.30, -1.50, 1.35), 55, 1.5, (1.0, 0.95, 0.88))
add_area("Fill", (-1.60, -0.90, 0.95), 30, 1.8, (0.78, 0.86, 1.0))
add_area("Rim", (0.10, 1.55, 1.20), 45, 1.2, (1.0, 0.98, 0.94))

cam_data = bpy.data.cameras.new("Camera")
cam_data.lens = 70
cam = bpy.data.objects.new("Camera", cam_data)
bpy.context.collection.objects.link(cam)
scene.camera = cam


def render(path, loc, target, ortho=None, res=(900, 900)):
    scene.render.resolution_x, scene.render.resolution_y = res
    cam.location = loc
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    if ortho:
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = ortho
    else:
        cam.data.type = 'PERSP'
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("RENDERED", path)


render(os.path.join(RENDER_DIR, "cat_stage1_3q.png"), (0.94, -1.10, 0.52), (0.0, 0.02, 0.22))
render(os.path.join(RENDER_DIR, "cat_stage1_side.png"), (1.8, 0.02, 0.25), (0, 0.02, 0.25), ortho=0.92, res=(1100, 850))
render(os.path.join(RENDER_DIR, "cat_stage1_front.png"), (0, -1.8, 0.28), (0, 0.02, 0.26), ortho=0.46, res=(760, 1000))
render(os.path.join(RENDER_DIR, "cat_stage1_head.png"), (0.30, -0.62, 0.40), (0.0, -0.28, 0.32), ortho=0.30, res=(900, 900))

me = cat.data
me.calc_loop_triangles()
blend_path = os.path.join(OUT, "blender", "cat_stage1.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print("STAGE1_DONE", {
    "verts": len(me.vertices),
    "tris": len(me.loop_triangles),
    "materials": [m.name if m else None for m in me.materials],
    "dims": [round(v, 4) for v in cat.dimensions],
    "blend": blend_path,
})
