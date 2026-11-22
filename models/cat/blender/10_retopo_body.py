"""Retopologise the cat's fur body to clean, smooth quads (dog pipeline).

Separates the fur material island from the head details, then:
  voxel remesh -> corrective smooth -> Quadriflow -> relax -> smooth shading
and transfers the tuxedo vertex colours and skin weights back from the original
surface with nearest-surface interpolation. Saves a test blend and renders a rear
view (the problem angle), a 3/4 view and a walk frame.

Run through Blender MCP or:
  blender -b models/cat/out/Cat.blend --python models/cat/blender/10_retopo_body.py
"""
import bpy
import bmesh
import os
import math
import json
from mathutils import Vector
from mathutils.bvhtree import BVHTree

OUT = r"C:\Users\ridho\kerjaan\roblox-horror-game-experiments\models\cat"
BLEND = os.path.join(OUT, "out", "Cat.blend")
R = os.path.join(OUT, "out")

bpy.ops.wm.open_mainfile(filepath=BLEND)
scene = bpy.context.scene
cat = bpy.data.objects["Cat"]
arm = bpy.data.objects["CatRig"]
scene.camera = bpy.data.objects["Camera"]

# rest pose for the base mesh
arm.animation_data.action = None
for pb in arm.pose.bones:
    pb.rotation_mode = 'XYZ'
    pb.rotation_euler = (0, 0, 0)
    pb.location = (0, 0, 0)
    pb.scale = (1, 1, 1)
scene.frame_set(1)
bpy.context.view_layer.update()

print("START", {"cat_verts": len(cat.data.vertices), "cat_faces": len(cat.data.polygons),
                "cat_matrix": [round(v, 4) for row in cat.matrix_world for v in row]})

# ---------------------------------------------------------------- temp context
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


# ---------------------------------------------------------------- separate fur body
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
print("SEPARATED", [o.name for o in new_objs])
src = next(o for o in new_objs if o.type == 'MESH')
src.name = "CatFurBodySrc"
src.data.name = "CatFurBodySrcMesh"
cat.name = "CatAccessories"

# copy of the original surface for colour/weight transfer
orig = src.copy()
orig.data = src.data.copy()
orig.name = "CatBodyOrig"
bpy.context.collection.objects.link(orig)
for m in list(orig.modifiers):
    orig.modifiers.remove(m)
orig.parent = None

for m in list(src.modifiers):
    src.modifiers.remove(m)
src.parent = None
bpy.context.view_layer.update()

print("SRC", {"verts": len(src.data.vertices), "faces": len(src.data.polygons),
              "matrix": [round(v, 4) for row in src.matrix_world for v in row],
              "groups": len(src.vertex_groups),
              "colors": [(a.name, a.data_type, a.domain) for a in src.data.color_attributes]})

# ---------------------------------------------------------------- remesh + quadriflow
mod = src.modifiers.new("Voxel", 'REMESH')
mod.mode = 'VOXEL'
mod.voxel_size = 0.0035
mod.adaptivity = 0.0
apply_modifier(src, "Voxel")
print("AFTER_VOXEL", len(src.data.polygons))


def relax(iterations):
    sm = src.modifiers.new("Relax", 'CORRECTIVE_SMOOTH')
    sm.factor = 0.5
    sm.iterations = iterations
    sm.smooth_type = 'LENGTH_WEIGHTED'
    sm.use_only_smooth = True
    apply_modifier(src, "Relax")


relax(2)
with bpy.context.temp_override(**ctx(src)):
    bpy.ops.object.quadriflow_remesh(target_faces=3000, use_mesh_symmetry=False,
                                     use_preserve_sharp=False, use_preserve_boundary=False,
                                     preserve_attributes=False, smooth_normals=False,
                                     mode='FACES', seed=7)
print("AFTER_QUAD", len(src.data.polygons))
if len(src.data.polygons) > 6500:
    raise RuntimeError("Quadriflow did not retopologise: %d faces" % len(src.data.polygons))
relax(4)
for p in src.data.polygons:
    p.use_smooth = True

# make sure the fur material is the only slot used
fur_material = next(m for m in cat.data.materials if m and m.name == "Cat_FurVC")
src.data.materials.clear()
src.data.materials.append(fur_material)
for p in src.data.polygons:
    p.material_index = 0

# ---------------------------------------------------------------- transfer colours + weights
orig_me = orig.data
orig_me.calc_loop_triangles()
bvh = BVHTree.FromPolygons([v.co.copy() for v in orig_me.vertices],
                           [list(p.vertices) for p in orig_me.polygons],
                           all_triangles=False)

group_names = [g.name for g in orig.vertex_groups]
new_groups = {name: src.vertex_groups.new(name=name) for name in group_names}
col = src.data.color_attributes.new(name="Col", type='FLOAT_COLOR', domain='POINT')
orig_col = orig_me.color_attributes.get("Col")

unweighted = 0
max_inf = 0
for vi, v in enumerate(src.data.vertices):
    loc, nrm, poly_i, dist = bvh.find_nearest(v.co)
    if loc is None:
        # fall back to nearest vertex
        j = min(range(len(orig_me.vertices)), key=lambda k: (orig_me.vertices[k].co - v.co).length)
        loc = orig_me.vertices[j].co
        vids = [j]
    else:
        vids = list(orig_me.polygons[poly_i].vertices)
    # inverse-distance blend over the nearest face's verts
    ws = []
    for j in vids:
        d = max(1e-6, (orig_me.vertices[j].co - loc).length)
        ws.append(1.0 / (d * d))
    s = sum(ws)
    ws = [w / s for w in ws]

    acc = {}
    rgba = [0.0, 0.0, 0.0, 0.0]
    for j, w in zip(vids, ws):
        ov = orig_me.vertices[j]
        for g in ov.groups:
            if g.weight > 1e-4:
                acc[g.group] = acc.get(g.group, 0.0) + g.weight * w
        if orig_col:
            c = orig_col.data[j].color
            for k in range(4):
                rgba[k] += c[k] * w
    # normalise
    tot = sum(acc.values())
    if tot <= 1e-6:
        unweighted += 1
    else:
        inf = 0
        for gi, w in acc.items():
            nw = w / tot
            if nw > 0.002:
                new_groups[group_names[gi]].add([vi], nw, 'REPLACE')
                inf += 1
        max_inf = max(max_inf, inf)
    col.data[vi].color = (rgba[0], rgba[1], rgba[2], 1.0)

print("TRANSFER", {"new_verts": len(src.data.vertices), "new_faces": len(src.data.polygons),
                   "unweighted": unweighted, "max_influences": max_inf})

# ---------------------------------------------------------------- join back
cat.name = "Cat"
bpy.ops.object.select_all(action='DESELECT')
src.select_set(True)
cat.select_set(True)
bpy.context.view_layer.objects.active = cat
with bpy.context.temp_override(object=cat, active_object=cat,
                               selected_objects=[src, cat], selected_editable_objects=[src, cat]):
    bpy.ops.object.join()
cat = bpy.context.view_layer.objects.active
cat.name = "Cat"
cat.data.validate(verbose=False)
bpy.data.objects.remove(orig, do_unlink=True)

# restore the idle and frame range
arm.animation_data.action = bpy.data.actions["Idle"]
scene.frame_start = 1
scene.frame_end = 97
scene.frame_set(1)
bpy.context.view_layer.update()

me = cat.data
me.calc_loop_triangles()
print("FINAL", {"verts": len(me.vertices), "tris": len(me.loop_triangles), "faces": len(me.polygons),
                "groups": len(cat.vertex_groups), "materials": [m.name for m in me.materials],
                "modifiers": [(m.name, m.type) for m in cat.modifiers],
                "parent": cat.parent.name if cat.parent else None})

test_blend = os.path.join(OUT, "blender", "cat_retopo_test.blend")
bpy.ops.wm.save_as_mainfile(filepath=test_blend)
print("SAVED_TEST", test_blend)

# ---------------------------------------------------------------- renders
scene.render.image_settings.file_format = 'PNG'
try:
    scene.eevee.taa_render_samples = 24
except Exception:
    pass


def shot(path, loc, target, ortho=None, res=(700, 800), action=None, frame=1):
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


shot(os.path.join(R, "retopo_rear.png"), (0.0, 1.18, 0.40), (0.0, 0.03, 0.22), res=(650, 820))
shot(os.path.join(R, "retopo_3q.png"), (0.94, -1.10, 0.52), (0.0, 0.02, 0.22), res=(900, 800))
shot(os.path.join(R, "retopo_walk.png"), (0.94, -1.10, 0.52), (0.0, 0.02, 0.22), res=(900, 800),
     action=bpy.data.actions["Walk"], frame=7)
print("RETOPO_DONE")
