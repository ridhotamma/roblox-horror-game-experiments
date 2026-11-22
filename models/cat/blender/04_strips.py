"""Render 8-frame review strips for every clip in cat_anim.CLIPS (side view, plus a 3/4 view for idles)."""
import bpy
import os
import sys
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cat_anim as CA  # noqa: E402

OUT = os.path.join(os.path.dirname(HERE), "out")
SRC = os.path.join(OUT, "strip_src")
os.makedirs(SRC, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT, "Cat.blend"))
scene = bpy.context.scene
arm = bpy.data.objects["CatRig"]
cam = bpy.data.objects["Camera"]
scene.camera = cam
scene.render.image_settings.file_format = "PNG"
scene.render.resolution_x = 420
scene.render.resolution_y = 330
try:
    scene.eevee.taa_render_samples = 12
except Exception:
    pass

VIEWS = {
    "side": ((1.8, 0.02, 0.25), (0, 0.02, 0.25), 0.92),
    "persp": ((1.05, -1.20, 0.55), (0, 0.0, 0.20), None),
    "jump": ((1.9, 0.02, 0.36), (0, 0.02, 0.30), 1.10),
}


def frames_for(name):
    n = CA.CLIPS[name]["frames"]
    if name == "Jump":
        return [1, 7, 10, 14, 18, 22, 26, 31]
    return [1 + round(i * n / 8) for i in range(8)]


for name in CA.CLIPS:
    arm.animation_data.action = bpy.data.actions[name]
    view = "jump" if name == "Jump" else ("side" if name in ("Walk", "Run") else "persp")
    loc, target, ortho = VIEWS[view]
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    cam.data.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        cam.data.ortho_scale = ortho
    else:
        cam.data.lens = 50
    for f in frames_for(name):
        scene.frame_set(f)
        scene.render.filepath = os.path.join(SRC, f"{name}_{f:03d}.png")
        bpy.ops.render.render(write_still=True)
print("STRIPS_DONE")
