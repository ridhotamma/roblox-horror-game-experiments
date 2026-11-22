"""Render 8-frame review strips for each action."""
import bpy
import os
from mathutils import Vector

OUT = r"C:\Users\ridho\kerjaan\roblox-horror-game-experiments\models\cat"
SRC = os.path.join(OUT, "out", "strip_src")
os.makedirs(SRC, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT, "out", "Cat.blend"))
scene = bpy.context.scene
arm = bpy.data.objects["CatRig"]
cam = bpy.data.objects["Camera"]
scene.camera = cam
scene.render.image_settings.file_format = 'PNG'
scene.render.resolution_x = 420
scene.render.resolution_y = 330
try:
    scene.eevee.taa_render_samples = 12
except Exception:
    pass

clips = {
    "Idle": (bpy.data.actions["Idle"], [1, 13, 25, 37, 49, 61, 73, 85], "persp"),
    "Walk": (bpy.data.actions["Walk"], [1, 4, 7, 10, 13, 16, 19, 22], "side"),
    "Run": (bpy.data.actions["Run"], [1, 3, 5, 7, 9, 11, 13, 15], "side"),
    "Jump": (bpy.data.actions["Jump"], [1, 7, 10, 14, 18, 22, 27, 31], "jump"),
}

view_side = ((1.8, 0.02, 0.25), (0, 0.02, 0.25), 0.92)
view_persp = ((0.94, -1.10, 0.52), (0, 0.02, 0.22), None)
view_jump = ((1.9, 0.02, 0.42), (0, 0.02, 0.36), 1.25)
views = {"side": view_side, "persp": view_persp, "jump": view_jump}

for name, (act, frames, vname) in clips.items():
    arm.animation_data.action = act
    loc, target, ortho = views[vname]
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.type = 'ORTHO' if ortho else 'PERSP'
    if ortho:
        cam.data.ortho_scale = ortho
    for f in frames:
        scene.frame_set(f)
        scene.render.filepath = os.path.join(SRC, f"{name}_{f:03d}.png")
        bpy.ops.render.render(write_still=True)
        print("SHOT", name, f)
print("STRIPS_DONE")
