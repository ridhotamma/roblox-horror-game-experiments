"""v3 rig + clips + export.

  blender -b models/cat/blender/cat_v3_mesh.blend --python models/cat/blender/16_rig_anim_v3.py [-- --review]

Builds the 25-bone CatRig on the v3 landmarks (same bone names and roll
conventions as before, so game code that addresses bones keeps working), skins
the fur body with bone heat plus left/right and ear masks, rigid-skins the face
parts, joins everything into one `Cat` mesh, generates Idle / Walk / Run / Jump,
clamps paws to the floor, saves out/Cat.blend and exports Cat.glb, Cat.fbx and
Cat.roblox.glb (4.5 studs per metre).

Hind leg note: the femur now points down-FORWARD and the tibia down-BACK (a
real cat knee), so knee flexion is a positive Shin rotation and the hock folds
with a negative Foot rotation.
"""
import bpy
import json
import math
import os
import struct
import sys
from math import radians, sin, cos, pi
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cat_spec as S  # noqa: E402

CAT = os.path.dirname(HERE)
OUT = os.path.join(CAT, "out")
REVIEW = "--review" in sys.argv
scene = bpy.context.scene
scene.render.fps = 24
body = bpy.data.objects["Cat"]
parts = [o for o in bpy.data.objects if o.type == "MESH" and "bone" in o]


def activate(ob, others=()):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in others:
        o.select_set(True)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


# ---------------------------------------------------------------- armature
arm_data = bpy.data.armatures.new("CatRig")
arm = bpy.data.objects.new("CatRig", arm_data)
scene.collection.objects.link(arm)
arm.show_in_front = True
activate(arm)
bpy.ops.object.mode_set(mode="EDIT")
eb = arm_data.edit_bones


def bone(name, head, tail, parent=None, connect=False, roll=None, deform=True):
    b = eb.new(name)
    b.head = Vector(head)
    b.tail = Vector(tail)
    if parent:
        b.parent = eb[parent]
        b.use_connect = connect
    if roll is not None:
        b.align_roll(Vector(roll))
    b.use_deform = deform
    return b


SPINE_ROLL, TAIL_ROLL, LEG_ROLL = (0, 0, -1), (0, -1, 0), (0, 1, 0)
neck_a, neck_b = S.NECK[0], S.NECK[1]
nose = (0.0, S.NOSE_BRIDGE[1][1] - 0.012, S.NOSE_BRIDGE[1][2])
bone("Root", (0, 0, 0), (0, 0.10, 0), roll=(0, 0, 1), deform=False)
bone("Hips", (0, 0.180, 0.262), (0, 0.090, 0.268), "Root", roll=SPINE_ROLL)
bone("Spine1", (0, 0.090, 0.268), (0, -0.005, 0.266), "Hips", True, SPINE_ROLL)
bone("Spine2", (0, -0.005, 0.266), (0, -0.095, 0.266), "Spine1", True, SPINE_ROLL)
bone("Chest", (0, -0.095, 0.266), neck_a, "Spine2", True, SPINE_ROLL)
bone("Neck", neck_a, neck_b, "Chest", True, SPINE_ROLL)
bone("Head", neck_b, nose, "Neck", True, SPINE_ROLL)
for i in range(4):
    bone(f"Tail{i+1}", S.TAIL[i], S.TAIL[i + 1], "Hips" if i == 0 else f"Tail{i}", i > 0, TAIL_ROLL)
F, H = S.FRONT, S.HIND
for s, sx in (("L", 1), ("R", -1)):
    def m(p):
        return (p[0] * sx, p[1], p[2])
    bone(f"UpperArm.{s}", m(F["shoulder"]), m(F["elbow"]), "Chest", False, LEG_ROLL)
    bone(f"Forearm.{s}", m(F["elbow"]), m(F["wrist"]), f"UpperArm.{s}", True, LEG_ROLL)
    bone(f"Paw.{s}", m(F["wrist"]), m(F["toe"]), f"Forearm.{s}", True, LEG_ROLL)
    bone(f"Thigh.{s}", m(H["hip"]), m(H["knee"]), "Hips", False, LEG_ROLL)
    bone(f"Shin.{s}", m(H["knee"]), m(H["hock"]), f"Thigh.{s}", True, LEG_ROLL)
    bone(f"Foot.{s}", m(H["hock"]), m(H["toe"]), f"Shin.{s}", True, LEG_ROLL)
    ear = bpy.data.objects[f"Ear_{s}"]
    bone(f"Ear.{s}", tuple(ear["ear_base"]), tuple(ear["ear_tip"]), "Head", False, (0, 1, 0))
bpy.ops.object.mode_set(mode="OBJECT")
for pb in arm.pose.bones:
    pb.rotation_mode = "XYZ"

# ---------------------------------------------------------------- skin the fur body
activate(arm, [body])
bpy.ops.object.parent_set(type="ARMATURE_AUTO")
names = {vg.index: vg.name for vg in body.vertex_groups}
fixed = 0
for v in body.data.vertices:
    ws = {}
    for g in v.groups:
        n = names[g.group]
        if g.weight < 1e-4 or n.startswith("Ear."):
            continue
        if v.co.x > 0.010 and n.endswith(".R"):
            continue
        if v.co.x < -0.010 and n.endswith(".L"):
            continue
        ws[n] = g.weight
    ws = dict(sorted(ws.items(), key=lambda kv: -kv[1])[:4])
    total = sum(ws.values())
    for g in list(v.groups):
        body.vertex_groups[g.group].remove([v.index])
    if total <= 1e-6:
        fixed += 1
        continue
    for n, w in ws.items():
        body.vertex_groups[n].add([v.index], w / total, "REPLACE")
if fixed:
    # any vertex bone heat missed copies its nearest weighted neighbour
    weighted = [v for v in body.data.vertices if v.groups]
    for v in body.data.vertices:
        if v.groups:
            continue
        near = min(weighted, key=lambda o: (o.co - v.co).length_squared)
        for g in near.groups:
            body.vertex_groups[g.group].add([v.index], g.weight, "REPLACE")
print("SKIN_BODY", {"unweighted_fixed": fixed})

# ---------------------------------------------------------------- rigid parts, join
for ob in parts:
    vg = ob.vertex_groups.new(name=ob["bone"])
    vg.add([v.index for v in ob.data.vertices], 1.0, "REPLACE")
activate(body, parts)
bpy.ops.object.join()
cat = bpy.context.view_layer.objects.active
cat.name = "Cat"
for k in ("bone", "ear_base", "ear_tip"):
    if k in cat:
        del cat[k]
missing = [b.name for b in arm.data.bones if b.use_deform and not cat.vertex_groups.get(b.name)]
print("DEFORM_BONES_WITHOUT_WEIGHTS", missing)

# ---------------------------------------------------------------- animation
TWO = 2 * pi
arm.animation_data_create()


def clear_pose():
    for pb in arm.pose.bones:
        pb.rotation_euler = (0, 0, 0)
        pb.location = (0, 0, 0)
        pb.scale = (1, 1, 1)


def key(name, f, rx=0.0, ry=0.0, rz=0.0, loc=None):
    pb = arm.pose.bones[name]
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


def leg_cycle(t, phase, stance=0.58):
    """(u, hip, flex): hip < 0 swings the leg forward, flex > 0 folds the lower leg."""
    u = (t + phase) % 1.0
    if u < stance:
        s = u / stance
        return u, -20.0 + 40.0 * s, 5.0 + 6.0 * sin(pi * s)
    s = (u - stance) / (1.0 - stance)
    return u, 20.0 - 40.0 * smoothstep(s), 5.0 + 38.0 * sin(pi * s)


def tail(f, t, base_rx, amps, freq=1, extra=0.0):
    for i, (name, amp) in enumerate(zip(("Tail1", "Tail2", "Tail3", "Tail4"), amps)):
        ph = 0.5 * i
        key(name, f, rx=base_rx[i] + extra * sin(2 * TWO * t - ph), rz=amp * sin(TWO * freq * t - ph))


def build_idle():
    act = new_action("Idle")
    N = 96
    for f in range(1, N + 2, 2):
        t = (f - 1) / N
        breath = sin(TWO * 2 * t)
        sway = sin(TWO * t)
        key("Root", f, loc=(0.0025 * sway, 0, 0))
        key("Hips", f, rx=0.4 * breath, rz=1.0 * sway)
        key("Spine1", f, rx=0.7 * breath, rz=1.6 * sway)
        key("Spine2", f, rx=-0.9 * breath, rz=-0.8 * sway)
        key("Chest", f, rx=0.6 * breath, rz=-0.6 * sway)
        key("Neck", f, rx=-1.0 + 0.8 * sin(TWO * 2 * t + 0.4), rz=3.0 * sin(TWO * t + 0.2))
        key("Head", f, rx=-2.0 + 1.5 * sin(TWO * 2 * t + 0.9),
            rz=6.0 * sin(TWO * t) + 1.5 * sin(TWO * 2 * t + 1.1), ry=2.0 * sin(TWO * t + 0.7))
        key("UpperArm.L", f, rx=0.8 * sway)
        key("UpperArm.R", f, rx=-0.8 * sway)
        key("Thigh.L", f, rx=-0.6 * sway)
        key("Thigh.R", f, rx=0.6 * sway)
        tail(f, t, (-1, -1, -1, -1), (4, 6, 8, 10), extra=1.0)
    for f, rzv, rx in ((46, 0, 0), (50, -16, -10), (53, -4, -2), (56, 0, 0), (70, 0, 0), (73, 10, -6), (76, 0, 0)):
        key("Ear.L", f, rx=rx, rz=rzv)
        key("Ear.R", f, rx=rx * 0.6, rz=rzv * 0.8)
    return act, 1, N + 1


def build_walk():
    act = new_action("Walk")
    N = 24
    phases = {"FL": 0.25, "FR": 0.75, "HL": 0.0, "HR": 0.5}
    for f in range(1, N + 2):
        t = (f - 1) / N
        sway = sin(TWO * t)
        c2 = cos(2 * TWO * t)
        key("Root", f, loc=(0.0035 * sway, 0, 0))
        key("Hips", f, rx=0.6 * c2, rz=1.4 * sway)
        key("Spine1", f, rx=-0.8 * c2, rz=2.4 * sway)
        key("Spine2", f, rx=0.6 * c2, rz=-1.2 * sway)
        key("Chest", f, rx=0.4 * c2, rz=-1.2 * sway)
        key("Neck", f, rx=1.2 * c2, rz=-1.2 * sway)
        key("Head", f, rx=-1.0 + 1.4 * cos(2 * TWO * t + 0.4), rz=1.8 * sin(TWO * t + 0.5))
        for s in ("L", "R"):
            u, hip, flex = leg_cycle(t, phases["F" + s])
            key(f"UpperArm.{s}", f, rx=hip)
            key(f"Forearm.{s}", f, rx=flex)
            key(f"Paw.{s}", f, rx=-(hip + flex))
            u, hip, _ = leg_cycle(t, phases["H" + s], 0.60)
            if u >= 0.60:
                knee = 6.0 + 40.0 * sin(pi * (u - 0.60) / 0.40)
            else:
                knee = 6.0 + 5.0 * sin(pi * u / 0.60)
            key(f"Thigh.{s}", f, rx=hip - 0.35 * (knee - 6.0))
            key(f"Shin.{s}", f, rx=knee)
            key(f"Foot.{s}", f, rx=-(hip - 0.35 * (knee - 6.0) + knee))
        tail(f, t, (-2, -2, -2, -2), (5, 7, 9, 11), extra=1.5)
    return act, 1, N + 1


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
        key("Neck", f, rx=4.0 - 2.5 * sin(TWO * t), rz=-1.0 * sway)
        key("Head", f, rx=-5.0 + 2.2 * sin(TWO * t + 0.5), rz=1.5 * sin(TWO * t + 0.4))
        for s, phase in (("L", 0.03), ("R", -0.03)):
            u = (t + phase) % 1.0
            hip = -34.0 * cos(TWO * u)
            flex = 18.0 + 46.0 * max(0.0, -sin(TWO * u))
            key(f"UpperArm.{s}", f, rx=hip)
            key(f"Forearm.{s}", f, rx=flex)
            key(f"Paw.{s}", f, rx=-(hip + flex) + 6.0)
        for s, phase in (("L", 0.53), ("R", 0.47)):
            u = (t + phase) % 1.0
            hip = -34.0 * cos(TWO * u)
            knee = 10.0 + 50.0 * max(0.0, -sin(TWO * u))
            key(f"Thigh.{s}", f, rx=hip - 0.3 * knee)
            key(f"Shin.{s}", f, rx=knee)
            key(f"Foot.{s}", f, rx=-(hip - 0.3 * knee + knee) + 6.0)
        for i, (name, amp) in enumerate(zip(("Tail1", "Tail2", "Tail3", "Tail4"), (8, 12, 15, 18))):
            ph = 0.4 * i
            key(name, f, rx=18.0 + 3.0 * sin(2 * TWO * t - ph), rz=amp * sin(TWO * t - ph))
    return act, 1, N + 1


def build_jump():
    act = new_action("Jump")

    def jp(f, front, hind, spine, tl, root_z, root_y=0.0):
        (ua, fa), (th, kn) = front, hind
        for s in ("L", "R"):
            key(f"UpperArm.{s}", f, rx=ua)
            key(f"Forearm.{s}", f, rx=fa)
            key(f"Paw.{s}", f, rx=-(ua + fa) - 6.0)
            key(f"Thigh.{s}", f, rx=th)
            key(f"Shin.{s}", f, rx=kn)
            key(f"Foot.{s}", f, rx=-(th + kn))
        for name, v in zip(("Hips", "Spine1", "Spine2", "Neck", "Head"), spine):
            key(name, f, rx=v)
        for name, v in zip(("Tail1", "Tail2", "Tail3", "Tail4"), tl):
            key(name, f, rx=v)
        key("Root", f, loc=(0, root_y, root_z))

    # hind (thigh, knee): crouch = thigh forward (-) + knee folded (+); push-off = thigh back, knee open
    jp(1, (0, 0), (0, 0), (0, 0, 0, 0, 0), (0, 0, 0, 0), 0.0)
    jp(7, (-25, 65), (-22, 40), (6, 6, -3, 13, -7), (-12, -8, -6, -4), -0.040)
    jp(10, (-40, 90), (-28, 50), (7, 7, -3, 16, -9), (-14, -10, -7, -5), -0.048)
    jp(14, (-14, 6), (16, -12), (-2, -3, 1, -5, 3), (-22, -16, -12, -8), 0.020)
    jp(18, (-26, 52), (-30, 58), (2, 3, -1, -3, 2), (-28, -22, -18, -14), 0.150, -0.01)
    jp(22, (-24, 48), (-26, 52), (1, 2, 0, -2, 1), (-26, -20, -16, -12), 0.135, -0.01)
    jp(27, (4, 10), (-4, 10), (1, 1, 0, 3, -2), (-20, -15, -11, -8), 0.010, 0.0)
    jp(31, (-30, 75), (-26, 46), (7, 5, -2, 13, -7), (-16, -12, -8, -6), -0.038)
    jp(35, (-10, 30), (-12, 20), (3, 2, -1, 3, -2), (-10, -8, -5, -4), -0.016)
    jp(40, (0, 0), (0, 0), (0, 0, 0, 0, 0), (0, 0, 0, 0), 0.0)
    return act, 1, 40


clips = {}
for builder in (build_idle, build_walk, build_run, build_jump):
    act, f0, f1 = builder()
    clips[act.name] = (act, f0, f1)

# bake Root location on every frame so the clamp can key single frames
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

# ---------------------------------------------------------------- ground contact
dg = bpy.context.evaluated_depsgraph_get()


def min_z():
    ob = cat.evaluated_get(dg)
    me = ob.to_mesh()
    z = min(v.co.z for v in me.vertices)
    ob.to_mesh_clear()
    return z


GROUNDED = {"Idle": None, "Walk": None, "Run": set(), "Jump": set(range(1, 13)) | set(range(29, 41))}
contact = {}
for name, (act, f0, f1) in clips.items():
    arm.animation_data.action = act
    root = arm.pose.bones["Root"]
    for it in range(3):
        moved = 0
        for f in range(f0, f1 + 1):
            scene.frame_set(f)
            mz = min_z()
            stick = GROUNDED[name] is None or f in GROUNDED[name]
            if mz < -0.0003 or (stick and mz > 0.0003):
                root.location.z -= mz
                root.keyframe_insert("location", frame=f, group="Root")
                moved += 1
        if not moved:
            break
    vals = []
    for f in range(f0, f1 + 1):
        scene.frame_set(f)
        vals.append((round(min_z(), 4), f))
    vals.sort()
    contact[name] = {"low": vals[:2], "high": vals[-2:]}
print("CONTACT", json.dumps(contact))

# ---------------------------------------------------------------- NLA, save
arm.animation_data.action = None
clear_pose()
for name, (act, f0, f1) in clips.items():
    tr = arm.animation_data.nla_tracks.new()
    tr.name = name
    st = tr.strips.new(name, int(f0), act)
    st.name = name
    tr.mute = True
arm.animation_data.action = clips["Idle"][0]
scene.frame_start, scene.frame_end = 1, 97
scene.frame_set(1)
me = cat.data
me.calc_loop_triangles()
stats = {"verts": len(me.vertices), "tris": len(me.loop_triangles),
         "maxinf": max(sum(1 for g in v.groups if g.weight > 1e-4) for v in me.vertices),
         "bones": len(arm.data.bones)}
print("STATS", stats)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "Cat.blend"))

# ---------------------------------------------------------------- export
activate(arm, [cat])


def export_glb(path):
    bpy.ops.export_scene.gltf(
        filepath=path, export_format="GLB", use_selection=True, export_apply=False,
        export_yup=True, export_texcoords=False, export_normals=True,
        export_vertex_color="MATERIAL", export_all_vertex_colors=True,
        export_materials="EXPORT", export_skins=True, export_all_influences=False,
        export_def_bones=False, export_animations=True, export_animation_mode="ACTIONS",
        export_frame_range=False, export_anim_slide_to_zero=True, export_current_frame=False,
        export_bake_animation=False, export_optimize_animation_size=False,
        export_anim_single_armature=True)


export_glb(os.path.join(OUT, "Cat.glb"))
bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, "Cat.fbx"), use_selection=True, add_leaf_bones=False,
                         bake_anim=True, bake_anim_use_all_actions=True, bake_anim_use_nla_strips=False,
                         bake_anim_step=1.0, bake_anim_simplify_factor=0.0, path_mode="COPY", embed_textures=False)
arm.scale = (4.5, 4.5, 4.5)
bpy.context.view_layer.update()
export_glb(os.path.join(OUT, "Cat.roblox.glb"))
arm.scale = (1, 1, 1)

with open(os.path.join(OUT, "Cat.glb"), "rb") as fh:
    data = fh.read()
length = struct.unpack_from("<III", data, 0)[2]
off, g = 12, None
while off < length:
    clen, ctype = struct.unpack_from("<II", data, off)
    if ctype == 0x4E4F534A:
        g = json.loads(data[off + 8:off + 8 + clen].decode("utf-8"))
    off += 8 + clen
print("RESULT", json.dumps({
    **stats,
    "animations": [a.get("name") for a in g.get("animations", [])],
    "meshes": [m.get("name") for m in g.get("meshes", [])],
    "attrs": sorted({k for m in g["meshes"] for p in m["primitives"] for k in p["attributes"]}),
}))
