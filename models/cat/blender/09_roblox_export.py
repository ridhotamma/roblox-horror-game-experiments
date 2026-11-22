"""Export a Roblox-stud version (4.5 studs per metre, matching the house/tree)."""
import bpy
import os
from mathutils import Vector

OUT = r"C:\Users\ridho\kerjaan\roblox-horror-game-experiments\models\cat"
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT, "out", "Cat.blend"))
arm = bpy.data.objects["CatRig"]
cat = bpy.data.objects["Cat"]
scene = bpy.context.scene
arm.animation_data.action = None
for pb in arm.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.location = (0, 0, 0)
scene.frame_set(1)
bpy.context.view_layer.update()

arm.scale = (4.5, 4.5, 4.5)
bpy.context.view_layer.update()

dg = bpy.context.evaluated_depsgraph_get()
ev = cat.evaluated_get(dg)
me = ev.to_mesh()
xs = [v.co.x for v in me.vertices]; ys = [v.co.y for v in me.vertices]; zs = [v.co.z for v in me.vertices]
print("SCALED_MESH_BBOX", [round(min(xs),3), round(max(xs),3), round(min(ys),3), round(max(ys),3), round(min(zs),3), round(max(zs),3)])
ev.to_mesh_clear()

bpy.ops.object.select_all(action='DESELECT')
cat.select_set(True)
arm.select_set(True)
bpy.context.view_layer.objects.active = arm
_sel = [cat, arm]
_win = bpy.context.window_manager.windows[0]
_area = next((a for a in _win.screen.areas if a.type == 'VIEW_3D'), _win.screen.areas[0])
_ctx = dict(window=_win, screen=_win.screen, area=_area,
            active_object=arm, object=arm,
            selected_objects=_sel, selected_editable_objects=_sel)
path = os.path.join(OUT, "out", "Cat.roblox.glb")
with bpy.context.temp_override(**_ctx):
    bpy.ops.export_scene.gltf(
        filepath=path,
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
print("EXPORTED_ROBLOX_GLB", path)
arm.scale = (1, 1, 1)
bpy.context.view_layer.update()
