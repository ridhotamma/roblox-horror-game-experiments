"""Render the four clips to PNG sequences + hero still from the final Cat.blend."""
import bpy
import os
from mathutils import Vector

OUT = r"C:\Users\ridho\kerjaan\roblox-horror-game-experiments\models\cat"
R = os.path.join(OUT, "out")
FR = os.path.join(R, "video_frames")
os.makedirs(FR, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=os.path.join(R, "Cat.blend"))
scene = bpy.context.scene
arm = bpy.data.objects["CatRig"]
cam = bpy.data.objects["Camera"]
scene.camera = cam
scene.render.image_settings.file_format = 'PNG'
scene.render.film_transparent = False
scene.render.resolution_percentage = 100
scene.render.resolution_x = 640
scene.render.resolution_y = 640
try:
    scene.eevee.taa_render_samples = 24
except Exception:
    pass

cam.data.type = 'PERSP'
cam.data.lens = 70
cam.location = (1.45, -1.75, 0.82)
cam.rotation_euler = (Vector((0, 0.00, 0.255)) - Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cat_anim as CA  # noqa: E402
scene.render.fps = CA.FPS
# loops render frames 1..N (frame N+1 repeats frame 1), one-shots 1..N+1
clips = [(n, n, 1, c["frames"] + (0 if c["loop"] else 1)) for n, c in CA.CLIPS.items()]
for name, act_name, f0, f1 in clips:
    act = bpy.data.actions[act_name]
    arm.animation_data.action = act
    scene.frame_start = f0
    scene.frame_end = f1
    outdir = os.path.join(FR, name)
    os.makedirs(outdir, exist_ok=True)
    scene.render.filepath = os.path.join(outdir, "")
    scene.render.use_file_extension = True
    bpy.ops.render.render(animation=True)
    print("SEQUENCE_DONE", name, f0, f1)

# hero still
arm.animation_data.action = bpy.data.actions["Idle"]
scene.frame_set(1)
scene.render.resolution_x = 1200
scene.render.resolution_y = 1000
try:
    scene.eevee.taa_render_samples = 64
except Exception:
    pass
scene.render.filepath = os.path.join(R, "cat_hero.png")
bpy.ops.render.render(write_still=True)
print("HERO_DONE")

# orthographic side blueprint
cam.data.type = 'ORTHO'
cam.data.ortho_scale = 0.92
cam.location = (1.9, 0.02, 0.25)
cam.rotation_euler = (Vector((0, 0.02, 0.25)) - Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()
scene.render.resolution_x = 1200
scene.render.resolution_y = 900
scene.render.filepath = os.path.join(R, "cat_side.png")
bpy.ops.render.render(write_still=True)
print("SIDE_DONE")

# rear view (the blocked-leg angle) and head close-up
cam.data.type = 'PERSP'
cam.data.lens = 70
scene.render.resolution_x = 900
scene.render.resolution_y = 1100
cam.location = (0.0, 1.18, 0.40)
cam.rotation_euler = (Vector((0.0, 0.03, 0.22)) - Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = os.path.join(R, "cat_rear.png")
bpy.ops.render.render(write_still=True)
print("REAR_DONE")

cam.data.type = 'ORTHO'
cam.data.ortho_scale = 0.30
scene.render.resolution_x = 850
scene.render.resolution_y = 850
cam.location = (0.34, -0.70, 0.47)
cam.rotation_euler = (Vector((0.0, -0.29, 0.37)) - Vector(cam.location)).to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = os.path.join(R, "cat_head.png")
bpy.ops.render.render(write_still=True)
print("HEAD_DONE")
