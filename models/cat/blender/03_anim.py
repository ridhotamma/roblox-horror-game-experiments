"""Stage 3 (v2): idle / walk / run / jump, paws kept level, ground-contact clamp.

The leg chains counter-rotate each paw against the accumulated upper-leg
rotation so the paw stays parallel to the floor. A final pass lifts the root
per frame wherever the evaluated mesh would otherwise dip below z=0.
"""
import bpy
import math
import os
from math import radians, sin, cos, pi
from mathutils import Vector

OUT = r"C:\Users\ridho\kerjaan\roblox-horror-game-experiments\models\cat"
RENDER_DIR = os.path.join(OUT, "out")
bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT, "blender", "cat_stage2.blend"))
scene = bpy.context.scene
scene.render.fps = 24
arm = bpy.data.objects["CatRig"]
cat = bpy.data.objects["Cat"]
scene.camera = bpy.data.objects["Camera"]

try:
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'BEZIER'
    bpy.context.preferences.edit.keyframe_new_handle_type = 'AUTO_CLAMPED'
except Exception as e:
    print("PREF_SKIP", repr(e))

if arm.animation_data is None:
    arm.animation_data_create()
for tr in list(arm.animation_data.nla_tracks):
    arm.animation_data.nla_tracks.remove(tr)
arm.animation_data.action = None

TWO = 2 * pi


def clear_pose():
    for pb in arm.pose.bones:
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (0, 0, 0)
        pb.location = (0, 0, 0)
        pb.scale = (1, 1, 1)


def key(name, f, rx=0.0, ry=0.0, rz=0.0, loc=None):
    pb = arm.pose.bones[name]
    pb.rotation_mode = 'XYZ'
    pb.rotation_euler = (radians(rx), radians(ry), radians(rz))
    pb.keyframe_insert("rotation_euler", frame=f, group=name)
    if loc is not None:
        pb.location = loc
        pb.keyframe_insert("location", frame=f, group=name)


def new_action(name):
    clear_pose()
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    arm.animation_data.action = act
    return act


def smoothstep(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def leg_cycle(t, phase, stance_frac=0.58):
    """Returns (u, hip_deg, flex_deg). hip negative = forward. flex positive = joint folded."""
    u = (t + phase) % 1.0
    if u < stance_frac:
        s = u / stance_frac
        hip = -20.0 + 40.0 * s
        flex = 5.0 + 6.0 * sin(pi * s)
    else:
        s = (u - stance_frac) / (1.0 - stance_frac)
        hip = 20.0 - 40.0 * smoothstep(s)
        flex = 5.0 + 38.0 * sin(pi * s)
    return u, hip, flex


# ---------------------------------------------------------------- IDLE (4 s, loop)
def build_idle():
    act = new_action("Idle")
    N = 96
    for f in range(1, N + 2, 2):
        t = (f - 1) / N
        breath = sin(TWO * 2 * t)
        sway = sin(TWO * t)
        key("Root", f, loc=(0.0025 * sway, 0, 0.0012 * breath))
        key("Hips", f, rx=0.4 * breath, rz=1.0 * sway)
        key("Spine1", f, rx=0.7 * breath, rz=1.6 * sway)
        key("Spine2", f, rx=-0.9 * breath, rz=-0.8 * sway)
        key("Chest", f, rx=0.5 * breath, rz=-0.6 * sway)
        key("Neck", f, rx=-1.2 + 0.8 * sin(TWO * 2 * t + 0.4), rz=2.5 * sin(TWO * t + 0.2))
        key("Head", f, rx=-3.0 + 1.5 * sin(TWO * 2 * t + 0.9),
            rz=5.0 * sin(TWO * t) + 1.5 * sin(TWO * 2 * t + 1.1),
            ry=1.0 * sin(TWO * t + 0.7))
        key("UpperArm.L", f, rx=0.8 * sway)
        key("UpperArm.R", f, rx=-0.8 * sway)
        key("Thigh.L", f, rx=-0.6 * sway)
        key("Thigh.R", f, rx=0.6 * sway)
        for name, amp, ph in (("Tail1", 4, 0.0), ("Tail2", 6, 0.5), ("Tail3", 8, 1.0), ("Tail4", 10, 1.5)):
            key(name, f, rx=-1.0 + 1.0 * sin(TWO * t - ph), rz=amp * sin(TWO * t - ph))
    for f, rzv, rx in ((46, 0, 0), (50, -16, -10), (53, -4, -2), (56, 0, 0), (70, 0, 0), (73, 10, -6), (76, 0, 0)):
        key("Ear.L", f, rx=rx, rz=rzv)
        key("Ear.R", f, rx=rx * 0.6, rz=rzv * 0.8)
    return act, 1, N + 1


# ---------------------------------------------------------------- WALK (1 s, loop, lateral sequence)
def build_walk():
    act = new_action("Walk")
    N = 24
    phases = {"FL": 0.25, "FR": 0.75, "HL": 0.0, "HR": 0.5}
    for f in range(1, N + 2):
        t = (f - 1) / N
        sway = sin(TWO * t)
        key("Root", f, loc=(0.0035 * sway, 0, 0.0015 * cos(2 * TWO * t)))
        key("Hips", f, rx=0.6 * cos(2 * TWO * t), rz=1.2 * sway)
        key("Spine1", f, rx=-0.8 * cos(2 * TWO * t), rz=2.2 * sway)
        key("Spine2", f, rx=0.6 * cos(2 * TWO * t), rz=-1.2 * sway)
        key("Chest", f, rx=0.4 * cos(2 * TWO * t), rz=-1.0 * sway)
        key("Neck", f, rx=1.2 * cos(2 * TWO * t), rz=-1.2 * sway)
        key("Head", f, rx=-1.0 + 1.4 * cos(2 * TWO * t + 0.4), rz=1.8 * sin(TWO * t + 0.5))
        for side in ("L", "R"):
            u, hip, flex = leg_cycle(t, phases["F" + side])
            key(f"UpperArm.{side}", f, rx=hip)
            key(f"Forearm.{side}", f, rx=flex)
            key(f"Paw.{side}", f, rx=-(hip + flex))
        for side in ("L", "R"):
            u, hip, flex = leg_cycle(t, phases["H" + side], 0.60)
            hind_flex = 5.0 + 44.0 * max(0.0, sin(pi * ((u - 0.60) / 0.40))) if u >= 0.60 else 5.0 + 6.0 * sin(pi * u / 0.60)
            shin = -hind_flex
            key(f"Thigh.{side}", f, rx=hip)
            key(f"Shin.{side}", f, rx=shin)
            key(f"Foot.{side}", f, rx=-(hip + shin))
        for name, amp, ph in (("Tail1", 5, 0.0), ("Tail2", 7, 0.5), ("Tail3", 9, 1.0), ("Tail4", 11, 1.5)):
            key(name, f, rx=-2.0 + 1.5 * sin(2 * TWO * t - ph), rz=amp * sin(TWO * t - ph))
    return act, 1, N + 1


# ---------------------------------------------------------------- RUN (0.667 s, loop, gallop)
def build_run():
    act = new_action("Run")
    N = 16
    for f in range(1, N + 2):
        t = (f - 1) / N
        sway = sin(TWO * t)
        key("Root", f, loc=(0.002 * sway, 0, 0.006 + 0.018 * cos(2 * TWO * t + pi)))
        key("Hips", f, rx=2.5 * sin(TWO * t), rz=1.0 * sway)
        key("Spine1", f, rx=-5.5 * sin(TWO * t), rz=1.5 * sway)
        key("Spine2", f, rx=3.5 * sin(TWO * t), rz=-1.0 * sway)
        key("Chest", f, rx=2.0 * sin(TWO * t), rz=-1.0 * sway)
        key("Neck", f, rx=2.0 - 2.5 * sin(TWO * t), rz=-1.0 * sway)
        key("Head", f, rx=-3.0 + 2.2 * sin(TWO * t + 0.5), rz=1.5 * sin(TWO * t + 0.4))
        for side, phase in (("L", 0.03), ("R", -0.03)):
            u = (t + phase) % 1.0
            hip = -34.0 * cos(TWO * u)
            flex = 18.0 + 46.0 * max(0.0, -sin(TWO * u))
            key(f"UpperArm.{side}", f, rx=hip)
            key(f"Forearm.{side}", f, rx=flex)
            key(f"Paw.{side}", f, rx=-(hip + flex) + 6.0)
        for side, phase in (("L", 0.53), ("R", 0.47)):
            u = (t + phase) % 1.0
            hip = -36.0 * cos(TWO * u)
            flex = 14.0 + 58.0 * max(0.0, -sin(TWO * u))
            key(f"Thigh.{side}", f, rx=hip)
            key(f"Shin.{side}", f, rx=-flex)
            key(f"Foot.{side}", f, rx=-(hip - flex) + 6.0)
        for name, amp, ph in (("Tail1", 8, 0.0), ("Tail2", 12, 0.4), ("Tail3", 15, 0.8), ("Tail4", 18, 1.2)):
            key(name, f, rx=24.0 + 3.0 * sin(2 * TWO * t - ph), rz=amp * sin(TWO * t - ph))
    return act, 1, N + 1


# ---------------------------------------------------------------- JUMP (one-shot)
def build_jump():
    act = new_action("Jump")

    def jp(f, front, hind, spine, tail, root_z, root_y=0.0):
        (ua, fa), (th, sh) = front, hind
        key("UpperArm.L", f, rx=ua); key("UpperArm.R", f, rx=ua)
        key("Forearm.L", f, rx=fa); key("Forearm.R", f, rx=fa)
        key("Paw.L", f, rx=-(ua + fa) - 6.0); key("Paw.R", f, rx=-(ua + fa) - 6.0)
        key("Thigh.L", f, rx=th); key("Thigh.R", f, rx=th)
        key("Shin.L", f, rx=sh); key("Shin.R", f, rx=sh)
        key("Foot.L", f, rx=-(th + sh)); key("Foot.R", f, rx=-(th + sh))
        hips, s1, s2, neck, head = spine
        key("Hips", f, rx=hips)
        key("Spine1", f, rx=s1)
        key("Spine2", f, rx=s2)
        key("Neck", f, rx=neck)
        key("Head", f, rx=head)
        t1, t2, t3, t4 = tail
        key("Tail1", f, rx=t1)
        key("Tail2", f, rx=t2)
        key("Tail3", f, rx=t3)
        key("Tail4", f, rx=t4)
        key("Root", f, loc=(0, root_y, root_z))

    # rest
    jp(1, (0, 0), (0, 0), (0, 0, 0, 0, 0), (0, 0, 0, 0), 0.0)
    # settle / crouch
    jp(7, (-25, 65), (26, -46), (6, 6, -3, 13, -7), (-12, -8, -6, -4), -0.040)
    jp(10, (-40, 90), (30, -52), (7, 7, -3, 16, -9), (-14, -10, -7, -5), -0.048)
    # push-off
    jp(14, (-14, 6), (-12, -6), (-2, -3, 1, -5, 3), (-22, -16, -12, -8), 0.020)
    # airborne apex, tucked
    jp(18, (-26, 52), (-22, -60), (2, 3, -1, -3, 2), (-28, -22, -18, -14), 0.150, -0.01)
    jp(22, (-24, 48), (-20, -56), (1, 2, 0, -2, 1), (-26, -20, -16, -12), 0.135, -0.01)
    # reach for the floor
    jp(27, (4, 10), (2, -10), (1, 1, 0, 3, -2), (-20, -15, -11, -8), 0.010, 0.0)
    # landing crouch
    jp(31, (-30, 75), (30, -50), (7, 5, -2, 13, -7), (-16, -12, -8, -6), -0.038)
    jp(35, (-10, 30), (14, -22), (3, 2, -1, 3, -2), (-10, -8, -5, -4), -0.016)
    # recover
    jp(40, (0, 0), (0, 0), (0, 0, 0, 0, 0), (0, 0, 0, 0), 0.0)
    return act, 1, 40


# ---------------------------------------------------------------- build + bake root
clips = {}
for builder in (build_idle, build_walk, build_run, build_jump):
    act, f0, f1 = builder()
    clips[act.name] = (act, f0, f1)
    print("CLIP", act.name, f0, f1)

# bake Root location on every frame (needed for a clean per-frame clamp)
for name, (act, f0, f1) in clips.items():
    arm.animation_data.action = act
    root = arm.pose.bones["Root"]
    vals = []
    for f in range(f0, f1 + 1):
        scene.frame_set(f)
        vals.append((f, root.location.copy()))
    for f, loc in vals:
        root.location = loc
        root.keyframe_insert("location", frame=f, group="Root")
    print("ROOT_BAKED", name)

# ---------------------------------------------------------------- ground-contact clamp
dg = bpy.context.evaluated_depsgraph_get()


def eval_min_z():
    ob = cat.evaluated_get(dg)
    me = ob.to_mesh()
    z = min(v.co.z for v in me.vertices)
    ob.to_mesh_clear()
    return z


for name, (act, f0, f1) in clips.items():
    arm.animation_data.action = act
    root = arm.pose.bones["Root"]
    for it in range(2):
        adjustments = []
        for f in range(f0, f1 + 1):
            scene.frame_set(f)
            mz = eval_min_z()
            if mz < -0.0004:
                adjustments.append((f, -mz))
        for f, dz in adjustments:
            scene.frame_set(f)
            root.location.z = root.location.z + dz
            root.keyframe_insert("location", frame=f, group="Root")
        print("CLAMP", name, "iter", it, "frames", len(adjustments), "max", round(max([a[1] for a in adjustments], default=0), 4))
        if not adjustments:
            break
    lows = []
    for f in range(f0, f1 + 1):
        scene.frame_set(f)
        lows.append((round(eval_min_z(), 4), f))
    lows.sort()
    print("MINZ", name, "lowest", lows[:4], "highest", lows[-2:])

# ---------------------------------------------------------------- previews
def render(path, loc, target, ortho=None, res=(760, 760), frame=1, action=None):
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
    try:
        scene.eevee.taa_render_samples = 20
    except Exception:
        pass
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("RENDERED", path)


side = (1.8, 0.02, 0.25)
side_target = (0, 0.02, 0.25)
q = (0.94, -1.10, 0.52)
q_target = (0, 0.02, 0.22)
idle_act = clips["Idle"][0]
walk_act = clips["Walk"][0]
run_act = clips["Run"][0]
jump_act = clips["Jump"][0]

render(os.path.join(RENDER_DIR, "anim_idle.png"), q, q_target, frame=1, action=idle_act)
for f in (1, 7, 13, 19):
    render(os.path.join(RENDER_DIR, f"anim_walk_f{f:02d}.png"), side, side_target, ortho=0.92, res=(1000, 780), frame=f, action=walk_act)
for f in (1, 5, 9, 13):
    render(os.path.join(RENDER_DIR, f"anim_run_f{f:02d}.png"), side, side_target, ortho=0.92, res=(1000, 780), frame=f, action=run_act)
for f, tag in ((8, "crouch"), (13, "launch"), (18, "apex"), (31, "land")):
    render(os.path.join(RENDER_DIR, f"anim_jump_{tag}.png"), (1.9, 0.02, 0.42), (0, 0.02, 0.36), ortho=1.25, res=(1000, 900), frame=f, action=jump_act)

# ---------------------------------------------------------------- NLA + save
arm.animation_data.action = None
clear_pose()
for name, (act, f0, f1) in clips.items():
    track = arm.animation_data.nla_tracks.new()
    track.name = name
    strip = track.strips.new(name, int(f0), act)
    strip.name = name
    track.mute = True

scene.frame_start = 1
scene.frame_end = 96
scene.frame_set(1)
blend_path = os.path.join(OUT, "blender", "cat_stage3.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print("STAGE3_DONE", {"actions": [a[0].name for a in clips.values()], "blend": blend_path})