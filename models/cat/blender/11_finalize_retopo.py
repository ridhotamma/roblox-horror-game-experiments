"""Finalise the retopologised cat: ground contact, 4-influence weights, exports."""
import bpy
import os
import json
import struct
from mathutils import Vector

OUT = r"C:\Users\ridho\kerjaan\roblox-horror-game-experiments\models\cat"
BLEND_IN = os.path.join(OUT, "blender", "cat_retopo_test.blend")
BLEND_OUT = os.path.join(OUT, "out", "Cat.blend")

bpy.ops.wm.open_mainfile(filepath=BLEND_IN)
scene = bpy.context.scene
arm = bpy.data.objects["CatRig"]
cat = bpy.data.objects["Cat"]
scene.camera = bpy.data.objects["Camera"]
arm.animation_data.action = None
for pb in arm.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.location = (0, 0, 0)
scene.frame_set(1)
bpy.context.view_layer.update()

# ---------------------------------------------------------------- ground contact
dg = bpy.context.evaluated_depsgraph_get()


def min_z():
    ob = cat.evaluated_get(dg)
    me = ob.to_mesh()
    z = min(v.co.z for v in me.vertices)
    ob.to_mesh_clear()
    return z


def adjust(name, f0, f1, frames=None, mode="both"):
    act = bpy.data.actions[name]
    arm.animation_data.action = act
    root = arm.pose.bones["Root"]
    changed = 0
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
            changed += 1
    print("GROUND_ADJUST", name, changed)


adjust("Idle", 1, 97)
adjust("Walk", 1, 25)
adjust("Run", 1, 17, mode="up")  # keeps the suspension; only fixes penetration
adjust("Jump", 1, 40, frames=set(range(1, 13)) | set(range(29, 41)))

report = {}
for name, (f0, f1) in {"Idle": (1, 97), "Walk": (1, 25), "Run": (1, 17), "Jump": (1, 40)}.items():
    arm.animation_data.action = bpy.data.actions[name]
    vals = []
    for f in range(f0, f1 + 1):
        scene.frame_set(f)
        vals.append((round(min_z(), 4), f))
    vals.sort()
    report[name] = {"low": vals[:3], "high": vals[-2:]}
print("CONTACT_AFTER " + json.dumps(report))

# ---------------------------------------------------------------- 4 influences max
me = cat.data
before = {}
for v in me.vertices:
    n = sum(1 for g in v.groups if g.weight > 1e-4)
    before[n] = before.get(n, 0) + 1
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
after = {}
for v in me.vertices:
    n = sum(1 for g in v.groups if g.weight > 1e-4)
    after[n] = after.get(n, 0) + 1
print("INFLUENCES", {"before": before, "after": after})

# ---------------------------------------------------------------- save final blend
arm.animation_data.action = bpy.data.actions["Idle"]
scene.frame_start = 1
scene.frame_end = 97
scene.frame_set(1)
bpy.context.view_layer.update()
me.calc_loop_triangles()
print("FINAL", {"verts": len(me.vertices), "tris": len(me.loop_triangles),
                "faces": len(me.polygons), "groups": len(cat.vertex_groups),
                "materials": [m.name for m in me.materials],
                "modifiers": [(m.name, m.type) for m in cat.modifiers],
                "parent": cat.parent.name if cat.parent else None})
bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)
print("SAVED", BLEND_OUT)

# ---------------------------------------------------------------- export
_win = bpy.context.window_manager.windows[0]
_area = next((a for a in _win.screen.areas if a.type == 'VIEW_3D'), _win.screen.areas[0])
_region = next((r for r in _area.regions if r.type == 'WINDOW'), _area.regions[0])
_sel = [cat, arm]
_ctx = dict(window=_win, screen=_win.screen, area=_area, region=_region,
            active_object=arm, object=arm,
            selected_objects=_sel, selected_editable_objects=_sel)
bpy.ops.object.select_all(action='DESELECT')
cat.select_set(True)
arm.select_set(True)
bpy.context.view_layer.objects.active = arm

with bpy.context.temp_override(**_ctx):
    bpy.ops.export_scene.gltf(
        filepath=os.path.join(OUT, "out", "Cat.glb"),
        export_format='GLB', use_selection=True, export_apply=False,
        export_yup=True, export_texcoords=False, export_normals=True,
        export_vertex_color='MATERIAL', export_all_vertex_colors=True,
        export_materials='EXPORT', export_skins=True, export_all_influences=False,
        export_def_bones=False, export_animations=True, export_animation_mode='ACTIONS',
        export_frame_range=False, export_anim_slide_to_zero=True,
        export_current_frame=False, export_bake_animation=False,
        export_optimize_animation_size=False, export_anim_single_armature=True,
    )
    bpy.ops.export_scene.fbx(
        filepath=os.path.join(OUT, "out", "Cat.fbx"),
        use_selection=True, add_leaf_bones=False, bake_anim=True,
        bake_anim_use_all_actions=True, bake_anim_use_nla_strips=False,
        bake_anim_step=1.0, bake_anim_simplify_factor=0.0,
        path_mode='COPY', embed_textures=False,
    )
print("EXPORTED_GLB_FBX")

# roblox scale
arm.scale = (4.5, 4.5, 4.5)
bpy.context.view_layer.update()
with bpy.context.temp_override(**_ctx):
    bpy.ops.export_scene.gltf(
        filepath=os.path.join(OUT, "out", "Cat.roblox.glb"),
        export_format='GLB', use_selection=True, export_apply=False,
        export_yup=True, export_texcoords=False, export_normals=True,
        export_vertex_color='MATERIAL', export_all_vertex_colors=True,
        export_materials='EXPORT', export_skins=True, export_all_influences=False,
        export_def_bones=False, export_animations=True, export_animation_mode='ACTIONS',
        export_frame_range=False, export_anim_slide_to_zero=True,
        export_current_frame=False, export_bake_animation=False,
        export_optimize_animation_size=False, export_anim_single_armature=True,
    )
arm.scale = (1, 1, 1)
print("EXPORTED_ROBLOX_GLB")

# ---------------------------------------------------------------- verify
with open(os.path.join(OUT, "out", "Cat.glb"), "rb") as fh:
    data = fh.read()
_, _, length = struct.unpack_from("<III", data, 0)
off = 12
g = None
while off < length:
    clen, ctype = struct.unpack_from("<II", data, off)
    chunk = data[off + 8:off + 8 + clen]
    if ctype == 0x4E4F534A:
        g = json.loads(chunk.decode("utf-8"))
    off += 8 + clen
print("GLB_VERIFY " + json.dumps({
    "animations": [a.get("name") for a in g.get("animations", [])],
    "meshes": [m.get("name") for m in g.get("meshes", [])],
    "primitives": [sorted(p.get("attributes", {}).keys()) for m in g.get("meshes", []) for p in m.get("primitives", [])],
    "materials": [m.get("name") for m in g.get("materials", [])],
}))
print("FINALIZE_DONE")
