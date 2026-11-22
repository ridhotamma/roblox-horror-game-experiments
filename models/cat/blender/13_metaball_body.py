"""Rebuild the cat's fur body with the dog's metaball -> Quadriflow pipeline.

Metaball ellipsoids/capsules merge the torso, neck, head, legs and tail into one
smooth implicit surface, so there is no leg/torso junction crease. The new body
inherits the tuxedo vertex colours and skin weights from the current retopo body.
Saves a test blend and renders rear / 3-4 / head checks.
"""
import bpy
import bmesh
import math
import os
import json
from mathutils import Vector, Quaternion
from mathutils.bvhtree import BVHTree

OUT = r"C:\Users\ridho\kerjaan\roblox-horror-game-experiments\models\cat"
R = os.path.join(OUT, "out")
bpy.ops.wm.open_mainfile(filepath=os.path.join(R, "Cat.blend"))
scene = bpy.context.scene
cat = bpy.data.objects["Cat"]
arm = bpy.data.objects["CatRig"]
scene.camera = bpy.data.objects["Camera"]
arm.animation_data.action = None
for pb in arm.pose.bones:
    pb.rotation_mode = 'XYZ'
    pb.rotation_euler = (0, 0, 0)
    pb.location = (0, 0, 0)
    pb.scale = (1, 1, 1)
scene.frame_set(1)
bpy.context.view_layer.update()

_win = bpy.context.window_manager.windows[0]
_area = next((a for a in _win.screen.areas if a.type == 'VIEW_3D'), _win.screen.areas[0])
_region = next((r for r in _area.regions if r.type == 'WINDOW'), _area.regions[0])


def ctx(ob, extra=None):
    d = dict(window=_win, screen=_win.screen, area=_area, region=_region,
             object=ob, active_object=ob,
             selected_objects=[ob], selected_editable_objects=[ob])
    if extra:
        d.update(extra)
    return d


def apply_modifier(ob, name):
    with bpy.context.temp_override(**ctx(ob)):
        bpy.ops.object.modifier_apply(modifier=name)


# ---------------------------------------------------------------- separate current fur body
bpy.ops.object.select_all(action='DESELECT')
cat.select_set(True)
bpy.context.view_layer.objects.active = cat
with bpy.context.temp_override(**ctx(cat)):
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(cat.data)
    bm.faces.ensure_lookup_table()
    fur_i = next(i for i, m in enumerate(cat.data.materials) if m and m.name == "Cat_FurVC")
    for f in bm.faces:
        sel = (f.material_index == fur_i)
        f.select = sel
        if sel:
            for vv in f.verts:
                vv.select = True
            for ee in f.edges:
                ee.select = True
    bmesh.update_edit_mesh(cat.data)
    before = set(bpy.data.objects)
    bpy.ops.mesh.separate(type='SELECTED')
    bpy.ops.object.mode_set(mode='OBJECT')
new_objs = set(bpy.data.objects) - before
src = next(o for o in new_objs if o.type == 'MESH')
src.name = "CatOldBody"
cat.name = "CatAccessories"
for m in list(src.modifiers):
    src.modifiers.remove(m)
src.parent = None
bpy.context.view_layer.update()

# ---------------------------------------------------------------- metaball anatomy
VIS = 0.574


class Sculpt:
    def __init__(self, name):
        self.mb = bpy.data.metaballs.new(name)
        self.mb.resolution = 0.004
        self.mb.render_resolution = 0.004
        self.ob = bpy.data.objects.new(name, self.mb)
        bpy.context.collection.objects.link(self.ob)

    def ellipsoid(self, c, half, rot=None, stiff=2.0):
        r = max(half)
        el = self.mb.elements.new(type="ELLIPSOID")
        el.co = c
        el.radius = r / VIS
        el.size_x, el.size_y, el.size_z = (half[0] / r, half[1] / r, half[2] / r)
        el.stiffness = stiff
        if rot:
            el.rotation = rot
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

# torso: rump, waist, ribs, chest, front chest
sc.ellipsoid((0.000, 0.150, 0.250), (0.054, 0.072, 0.064))
sc.ellipsoid((0.000, 0.060, 0.252), (0.058, 0.085, 0.070))
sc.ellipsoid((0.000, -0.030, 0.249), (0.060, 0.080, 0.072))
sc.ellipsoid((0.000, -0.115, 0.255), (0.055, 0.070, 0.073))
sc.ellipsoid((0.000, -0.158, 0.266), (0.045, 0.048, 0.062))

# neck and head
sc.capsule((0.000, -0.165, 0.272), (0.000, -0.220, 0.298), 0.046)
sc.ellipsoid((0.000, -0.274, 0.318), (0.078, 0.086, 0.073))
sc.ellipsoid((0.000, -0.307, 0.305), (0.068, 0.056, 0.056))
sc.capsule((0.000, -0.325, 0.298), (0.000, -0.372, 0.291), 0.025)
sc.ellipsoid((0.000, -0.380, 0.291), (0.027, 0.021, 0.021))
sc.ellipsoid((0.000, -0.345, 0.281), (0.034, 0.042, 0.022))

# tail, tapering up and back
sc.capsule((0.000, 0.200, 0.255), (0.000, 0.290, 0.295), 0.022)
sc.capsule((0.000, 0.290, 0.295), (0.000, 0.360, 0.348), 0.021)
sc.capsule((0.000, 0.360, 0.348), (0.000, 0.405, 0.420), 0.016)
sc.capsule((0.000, 0.405, 0.420), (0.000, 0.423, 0.500), 0.009)

for sx in (1, -1):
    # front: shoulder mass, upper arm, forearm, pastern, paw
    sc.ellipsoid((0.062 * sx, -0.100, 0.215), (0.022, 0.036, 0.044))
    sc.capsule((0.058 * sx, -0.100, 0.208), (0.058 * sx, -0.073, 0.130), 0.025)
    sc.capsule((0.058 * sx, -0.073, 0.130), (0.058 * sx, -0.095, 0.057), 0.020)
    sc.capsule((0.058 * sx, -0.095, 0.057), (0.058 * sx, -0.112, 0.038), 0.018)
    sc.ellipsoid((0.058 * sx, -0.124, 0.026), (0.031, 0.046, 0.025))
    # hind: thigh mass, thigh, shin, foot, paw
    sc.ellipsoid((0.058 * sx, 0.162, 0.190), (0.014, 0.032, 0.040))
    sc.capsule((0.061 * sx, 0.160, 0.218), (0.062 * sx, 0.200, 0.134), 0.020)
    sc.capsule((0.062 * sx, 0.200, 0.134), (0.062 * sx, 0.176, 0.070), 0.019)
    sc.capsule((0.062 * sx, 0.176, 0.070), (0.060 * sx, 0.140, 0.032), 0.018)
    sc.ellipsoid((0.060 * sx, 0.122, 0.026), (0.032, 0.047, 0.025))

bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
meta_me = bpy.data.meshes.new_from_object(sc.ob.evaluated_get(dg))
meta_me.name = "CatMetaBodyMesh"
body = bpy.data.objects.new("CatMetaBody", meta_me)
bpy.context.collection.objects.link(body)
bpy.data.objects.remove(sc.ob, do_unlink=True)
print("META_BAKED", len(body.data.vertices), len(body.data.polygons))

# ---------------------------------------------------------------- remesh + retopo
mod = body.modifiers.new("Voxel", 'REMESH')
mod.mode = 'VOXEL'
mod.voxel_size = 0.003
mod.adaptivity = 0.0
apply_modifier(body, "Voxel")
print("AFTER_VOXEL", len(body.data.polygons))


def relax(iterations):
    sm = body.modifiers.new("Relax", 'CORRECTIVE_SMOOTH')
    sm.factor = 0.5
    sm.iterations = iterations
    sm.smooth_type = 'LENGTH_WEIGHTED'
    sm.use_only_smooth = True
    apply_modifier(body, "Relax")


relax(2)
with bpy.context.temp_override(**ctx(body)):
    bpy.ops.object.quadriflow_remesh(target_faces=3000, use_mesh_symmetry=False,
                                     use_preserve_sharp=False, use_preserve_boundary=False,
                                     preserve_attributes=False, smooth_normals=False,
                                     mode='FACES', seed=7)
print("AFTER_QUAD", len(body.data.polygons))
if len(body.data.polygons) > 6500:
    raise RuntimeError("Quadriflow failed: %d faces" % len(body.data.polygons))
relax(4)
for p in body.data.polygons:
    p.use_smooth = True
fur_material = next(m for m in cat.data.materials if m and m.name == "Cat_FurVC")
body.data.materials.clear()
body.data.materials.append(fur_material)
for p in body.data.polygons:
    p.material_index = 0

# ---------------------------------------------------------------- transfer colours + weights
orig_me = src.data
orig_me.calc_loop_triangles()
bvh = BVHTree.FromPolygons([v.co.copy() for v in orig_me.vertices],
                           [list(p.vertices) for p in orig_me.polygons],
                           all_triangles=False)
group_names = [g.name for g in src.vertex_groups]
new_groups = {name: body.vertex_groups.new(name=name) for name in group_names}
col = body.data.color_attributes.new(name="Col", type='FLOAT_COLOR', domain='POINT')
orig_col = orig_me.color_attributes.get("Col")

def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def ellipsoid_mask(co, center, radii, soft=0.18):
    d = math.sqrt(sum(((co[i] - center[i]) / radii[i]) ** 2 for i in range(3)))
    return 1.0 - smoothstep(1.0 - soft, 1.0 + soft, d)


FUR_LIN = (0.050, 0.058, 0.070)
CREAM_LIN = (0.620, 0.585, 0.530)

unweighted = 0
for vi, v in enumerate(body.data.vertices):
    loc, nrm, poly_i, dist = bvh.find_nearest(v.co)
    if loc is None:
        j = min(range(len(orig_me.vertices)), key=lambda k: (orig_me.vertices[k].co - v.co).length)
        loc = orig_me.vertices[j].co
        vids = [j]
    else:
        vids = list(orig_me.polygons[poly_i].vertices)
    ws = []
    for j in vids:
        d = max(1e-6, (orig_me.vertices[j].co - loc).length)
        ws.append(1.0 / (d * d))
    s = sum(ws)
    ws = [w / s for w in ws]
    acc = {}
    for j, w in zip(vids, ws):
        for g in orig_me.vertices[j].groups:
            if g.weight > 1e-4:
                acc[g.group] = acc.get(g.group, 0.0) + g.weight * w
    tot = sum(acc.values())
    if tot <= 1e-6:
        unweighted += 1
    else:
        for gi, w in acc.items():
            nw = w / tot
            if nw > 0.002:
                new_groups[group_names[gi]].add([vi], nw, 'REPLACE')
    co = v.co
    belly = ellipsoid_mask(co, (0.0, 0.005, 0.162), (0.083, 0.235, 0.058), 0.30)
    chest = ellipsoid_mask(co, (0.0, -0.168, 0.242), (0.063, 0.105, 0.100), 0.30)
    muzzle = ellipsoid_mask(co, (0.0, -0.360, 0.292), (0.062, 0.070, 0.052), 0.30)
    socks = 1.0 - smoothstep(0.032, 0.060, co.z)
    tip = smoothstep(0.400, 0.418, co.y)
    cream = min(1.0, max(belly, chest, muzzle, socks, tip) * 1.05)
    col_lin = tuple(FUR_LIN[k] * (1 - cream) + CREAM_LIN[k] * cream for k in range(3))
    col.data[vi].color = (*col_lin, 1.0)
print("TRANSFER", {"verts": len(body.data.vertices), "unweighted": unweighted})

# ---------------------------------------------------------------- join, 4 influences
cat.name = "Cat"
bpy.ops.object.select_all(action='DESELECT')
body.select_set(True)
cat.select_set(True)
bpy.context.view_layer.objects.active = cat
with bpy.context.temp_override(object=cat, active_object=cat,
                               selected_objects=[body, cat], selected_editable_objects=[body, cat]):
    bpy.ops.object.join()
cat = bpy.context.view_layer.objects.active
cat.name = "Cat"
cat.data.validate(verbose=False)
bpy.data.objects.remove(src, do_unlink=True)

me = cat.data

# fit the head details to the larger metaball head
mats = {m.name: i for i, m in enumerate(me.materials)}
eye_mats = {mats.get("Cat_EyeAmber"), mats.get("Cat_Pupil")}
pink = mats.get("Cat_Pink")
fur = mats.get("Cat_Fur")
white = mats.get("Cat_Whisker")
mouth = mats.get("Cat_Mouth")
eye_verts = set()
for p in me.polygons:
    if p.material_index in eye_mats:
        eye_verts.update(p.vertices)
for p in me.polygons:
    if p.material_index == white:
        for vi in p.vertices:
            co = me.vertices[vi].co
            if (co - Vector((0.045, -0.35, 0.32))).length < 0.02 or (co - Vector((-0.045, -0.35, 0.32))).length < 0.02:
                eye_verts.add(vi)
for vi in eye_verts:
    co = me.vertices[vi].co
    co.x += 0.002 if co.x > 0 else -0.002
    co.y -= 0.015
    co.z += 0.004
for vi in eye_verts:
    co = me.vertices[vi].co
    center = Vector((0.040 if co.x > 0 else -0.040, -0.353, 0.322))
    co = center + (co - center) * 1.12
    me.vertices[vi].co = co

for p in me.polygons:
    if p.material_index in (pink, mouth):
        for vi in p.vertices:
            co = me.vertices[vi].co
            if co.z < 0.32 and co.y < -0.35:
                co.y -= 0.005
for p in me.polygons:
    if p.material_index in (pink, fur):
        for vi in p.vertices:
            co = me.vertices[vi].co
            if co.z > 0.33 and co.y < -0.20:
                co.z += 0.012
                co.x *= 1.05
print("HEAD_FIT", len(eye_verts))

for v in me.vertices:
    vi = v.index
    gs = [(g.group, g.weight) for g in v.groups if g.weight > 1e-4]
    if not gs:
        continue
    gs.sort(key=lambda x: -x[1])
    keep = gs[:4]
    total = sum(w for _, w in keep)
    for vg in cat.vertex_groups:
        vg.remove([vi])
    for gi, w in keep:
        cat.vertex_groups[gi].add([vi], w / total, 'REPLACE')

# ---------------------------------------------------------------- ground contact for new paws
arm.animation_data.action = None
for pb in arm.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.location = (0, 0, 0)
scene.frame_set(1)
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()


def min_z():
    ob = cat.evaluated_get(dg)
    m = ob.to_mesh()
    z = min(v.co.z for v in m.vertices)
    ob.to_mesh_clear()
    return z


def adjust(name, f0, f1, frames=None, mode="both"):
    arm.animation_data.action = bpy.data.actions[name]
    root = arm.pose.bones["Root"]
    n = 0
    for f in range(f0, f1 + 1):
        if frames is not None and f not in frames:
            continue
        scene.frame_set(f)
        mz = min_z()
        if mode == "up" and mz >= -0.0002:
            continue
        if abs(mz) > 0.0002:
            root.location.z = root.location.z - mz
            root.keyframe_insert("location", frame=f, group="Root")
            n += 1
    print("GROUND", name, n)


adjust("Idle", 1, 97)
adjust("Walk", 1, 25)
adjust("Run", 1, 17, mode="up")
adjust("Jump", 1, 40, frames=set(range(1, 13)) | set(range(29, 41)))

arm.animation_data.action = bpy.data.actions["Idle"]
scene.frame_start = 1
scene.frame_end = 97
scene.frame_set(1)
bpy.context.view_layer.update()
me.calc_loop_triangles()
print("FINAL", {"verts": len(me.vertices), "tris": len(me.loop_triangles),
                "groups": len(cat.vertex_groups), "faces": len(me.polygons)})
test_blend = os.path.join(OUT, "blender", "cat_metaball_test.blend")
bpy.ops.wm.save_as_mainfile(filepath=test_blend)
print("SAVED", test_blend)

# ---------------------------------------------------------------- renders
scene.render.image_settings.file_format = 'PNG'
try:
    scene.eevee.taa_render_samples = 28
except Exception:
    pass


def shot(path, loc, target, ortho=None, res=(700, 900), action=None, frame=1):
    if action is not None:
        arm.animation_data.action = action
    scene.frame_set(frame)
    cam = scene.camera
    scene.render.resolution_x, scene.render.resolution_y = res
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.type = 'ORTHO' if ortho else 'PERSP'
    if ortho:
        cam.data.ortho_scale = ortho
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("RENDERED", path)


shot(os.path.join(R, "meta_rear_high.png"), (0.0, 1.05, 0.56), (0.0, 0.08, 0.23))
shot(os.path.join(R, "meta_rear_3q.png"), (0.62, 0.98, 0.46), (0.0, 0.05, 0.22), res=(900, 800))
shot(os.path.join(R, "meta_3q.png"), (0.94, -1.10, 0.52), (0.0, 0.02, 0.22), res=(900, 800))
shot(os.path.join(R, "meta_head.png"), (0.32, -0.64, 0.42), (0.0, -0.27, 0.32), ortho=0.34, res=(800, 800))
print("META_TEST_DONE")
