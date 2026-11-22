"""Finalize: idle active, save Cat.blend, export GLB + FBX, verify animation payload."""
import bpy
import os
import json
import struct

OUT = r"C:\Users\ridho\kerjaan\roblox-horror-game-experiments\models\cat"
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT, "blender", "cat_stage3.blend"))
scene = bpy.context.scene
arm = bpy.data.objects["CatRig"]
cat = bpy.data.objects["Cat"]

# neutral white vertex colour on non-fur material islands
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
print("VALIDATE", _me.validate(verbose=False))

# show the idle when the file is opened
arm.animation_data.action = bpy.data.actions["Idle"]
scene.frame_start = 1
scene.frame_end = 97
scene.frame_set(1)
for tr in arm.animation_data.nla_tracks:
    tr.mute = True

blend_out = os.path.join(OUT, "out", "Cat.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_out)
print("SAVED_BLEND", blend_out)

# selection only: rig + mesh
bpy.ops.object.select_all(action='DESELECT')
cat.select_set(True)
arm.select_set(True)
bpy.context.view_layer.objects.active = arm

glb_path = os.path.join(OUT, "out", "Cat.glb")
_sel = [cat, arm]
_win = bpy.context.window_manager.windows[0]
_area = next((a for a in _win.screen.areas if a.type == 'VIEW_3D'), _win.screen.areas[0])
_ctx = dict(window=_win, screen=_win.screen, area=_area,
            active_object=arm, object=arm,
            selected_objects=_sel, selected_editable_objects=_sel)
with bpy.context.temp_override(**_ctx):
    bpy.ops.export_scene.gltf(
        filepath=glb_path,
        export_format='GLB',
        use_selection=True,
        export_apply=False,
        export_yup=True,
        export_texcoords=False,
        export_normals=True,
        export_vertex_color='MATERIAL',
        export_all_vertex_colors=True,
        export_materials='EXPORT',
        export_skins=True,
        export_all_influences=False,
        export_def_bones=False,
        export_animations=True,
        export_animation_mode='ACTIONS',
        export_frame_range=False,
        export_anim_slide_to_zero=True,
        export_current_frame=False,
        export_bake_animation=False,
        export_optimize_animation_size=False,
        export_anim_single_armature=True,
    )
print("EXPORTED_GLB", glb_path)

fbx_path = os.path.join(OUT, "out", "Cat.fbx")
with bpy.context.temp_override(**_ctx):
    bpy.ops.export_scene.fbx(
        filepath=fbx_path,
        use_selection=True,
        add_leaf_bones=False,
        bake_anim=True,
        bake_anim_use_all_actions=True,
        bake_anim_use_nla_strips=False,
        bake_anim_step=1.0,
        bake_anim_simplify_factor=0.0,
        path_mode='COPY',
        embed_textures=False,
    )
print("EXPORTED_FBX", fbx_path)

# ---------------------------------------------------------------- verify GLB
with open(glb_path, "rb") as fh:
    data = fh.read()
magic, version, length = struct.unpack_from("<III", data, 0)
off = 12
gltf = None
while off < length:
    clen, ctype = struct.unpack_from("<II", data, off)
    chunk = data[off + 8:off + 8 + clen]
    if ctype == 0x4E4F534A:
        gltf = json.loads(chunk.decode("utf-8"))
        break
    off += 8 + clen
summary = {
    "bytes": len(data),
    "animations": [a.get("name") for a in gltf.get("animations", [])],
    "meshes": [m.get("name") for m in gltf.get("meshes", [])],
    "skins": len(gltf.get("skins", [])),
    "nodes": len(gltf.get("nodes", [])),
    "materials": [m.get("name") for m in gltf.get("materials", [])],
    "primitives": [],
}
for m in gltf.get("meshes", []):
    for p in m.get("primitives", []):
        summary["primitives"].append(sorted(p.get("attributes", {}).keys()))
print("GLB_SUMMARY " + json.dumps(summary))
print("DONE")
