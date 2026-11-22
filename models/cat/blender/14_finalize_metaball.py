"""Finalise the metaball body: save Cat.blend and export GLB/FBX/Roblox."""
import bpy
import os
import json
import struct
from mathutils import Vector

OUT = r"C:\Users\ridho\kerjaan\roblox-horror-game-experiments\models\cat"
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT, "blender", "cat_metaball_test.blend"))
scene = bpy.context.scene
arm = bpy.data.objects["CatRig"]
cat = bpy.data.objects["Cat"]
scene.camera = bpy.data.objects["Camera"]

arm.animation_data.action = bpy.data.actions["Idle"]
scene.frame_start = 1
scene.frame_end = 97
scene.frame_set(1)
bpy.context.view_layer.update()

# safety: accessory islands stay neutral white, body keeps the tuxedo colours
me = cat.data
fur_i = me.materials.find("Cat_FurVC")
col = me.color_attributes.get("Col")
if col:
    for p in me.polygons:
        if p.material_index != fur_i:
            for vi in p.vertices:
                col.data[vi].color = (1.0, 1.0, 1.0, 1.0)

# safety: ground contact report
dg = bpy.context.evaluated_depsgraph_get()


def min_z():
    ob = cat.evaluated_get(dg)
    m = ob.to_mesh()
    z = min(v.co.z for v in m.vertices)
    ob.to_mesh_clear()
    return z


contact = {}
for name, (f0, f1) in {"Idle": (1, 97), "Walk": (1, 25), "Run": (1, 17), "Jump": (1, 40)}.items():
    arm.animation_data.action = bpy.data.actions[name]
    vals = []
    for f in range(f0, f1 + 1):
        scene.frame_set(f)
        vals.append((round(min_z(), 4), f))
    vals.sort()
    contact[name] = {"low": vals[:3], "high": vals[-2:]}
print("CONTACT " + json.dumps(contact))

arm.animation_data.action = bpy.data.actions["Idle"]
scene.frame_set(1)
me.calc_loop_triangles()
print("FINAL", {"verts": len(me.vertices), "tris": len(me.loop_triangles), "faces": len(me.polygons),
                "maxinf": max(sum(1 for g in v.groups if g.weight > 1e-4) for v in me.vertices),
                "materials": [m.name for m in me.materials]})
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "out", "Cat.blend"))
print("SAVED_CAT_BLEND")

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


def export(path):
    with bpy.context.temp_override(**_ctx):
        bpy.ops.export_scene.gltf(
            filepath=path, export_format='GLB', use_selection=True, export_apply=False,
            export_yup=True, export_texcoords=False, export_normals=True,
            export_vertex_color='MATERIAL', export_all_vertex_colors=True,
            export_materials='EXPORT', export_skins=True, export_all_influences=False,
            export_def_bones=False, export_animations=True, export_animation_mode='ACTIONS',
            export_frame_range=False, export_anim_slide_to_zero=True,
            export_current_frame=False, export_bake_animation=False,
            export_optimize_animation_size=False, export_anim_single_armature=True,
        )


export(os.path.join(OUT, "out", "Cat.glb"))
with bpy.context.temp_override(**_ctx):
    bpy.ops.export_scene.fbx(
        filepath=os.path.join(OUT, "out", "Cat.fbx"), use_selection=True,
        add_leaf_bones=False, bake_anim=True, bake_anim_use_all_actions=True,
        bake_anim_use_nla_strips=False, bake_anim_step=1.0,
        bake_anim_simplify_factor=0.0, path_mode='COPY', embed_textures=False,
    )
print("EXPORTED_GLB_FBX")

arm.scale = (4.5, 4.5, 4.5)
bpy.context.view_layer.update()
export(os.path.join(OUT, "out", "Cat.roblox.glb"))
arm.scale = (1, 1, 1)
print("EXPORTED_ROBLOX_GLB")

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
    "prims": [sorted(p.get("attributes", {}).keys()) for m in g.get("meshes", []) for p in m.get("primitives", [])],
}))
print("DONE")
