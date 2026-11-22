"""v3 rig + clips (cat_anim.py) + export.

  blender -b models/cat/blender/cat_v3_mesh.blend --python models/cat/blender/16_rig_anim_v3.py [-- --review]

Builds the 25-bone CatRig on the v3 landmarks (same bone names and roll
conventions as before, so game code that addresses bones keeps working), skins
the fur body with bone heat plus left/right and ear masks, rigid-skins the face
parts, joins everything into one `Cat` mesh, bakes the clips from cat_anim.py
(locomotion with planted paws plus idle variants), saves out/Cat.blend and
exports Cat.glb, Cat.fbx and Cat.roblox.glb (4.5 studs per metre).

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
FACE_BONES = ("EyeLidUp", "EyeLidLow", "PupilW1", "PupilW2", "PupilH1", "PupilH2")
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
    # face rig (shared/face_rig.py): lids and pupil bones sit at the eyeball centre, Y = gaze, Z = eye up
    eye = bpy.data.objects[f"Eye_{s}"]["eye"]
    c, d, z = Vector(eye["centre"]), Vector(eye["dir"]), Vector(eye["up"])
    for nm in FACE_BONES:
        bone(f"{nm}.{s}", c, c + d * eye["r"], "Head", False, z)
bpy.ops.object.mode_set(mode="OBJECT")
for pb in arm.pose.bones:
    pb.rotation_mode = "XYZ"

# ---------------------------------------------------------------- skin the fur body
activate(arm, [body])
bpy.ops.object.parent_set(type="ARMATURE_AUTO")
names = {vg.index: vg.name for vg in body.vertex_groups}


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def region(n, co):
    """How much bone n may move a body vertex. Bone heat lets an upper arm drag the chest (the white bib
    tore when a front leg swung) and a thigh drag the belly; legs only own the skin below the shoulder /
    hip joint and away from the midline, the face and ears are separate rigid parts."""
    x, y, z = co
    if n.startswith(("Ear.", "EyeLid", "Pupil")):
        return 0.0
    if n.endswith(".L") and x < 0.010:
        return 0.0
    if n.endswith(".R") and x > -0.010:
        return 0.0
    ax = abs(x)
    if n.startswith(("UpperArm", "Forearm", "Paw")):
        return (1 - smoothstep(0.195, 0.235, z)) * smoothstep(0.014, 0.030, ax) * (1 - smoothstep(-0.07, -0.03, y))
    if n.startswith(("Thigh", "Shin", "Foot")):
        return (1 - smoothstep(0.205, 0.250, z)) * smoothstep(0.014, 0.030, ax) * smoothstep(0.06, 0.10, y)
    return 1.0


me_b = body.data
W = []
for v in me_b.vertices:
    W.append({names[g.group]: g.weight * region(names[g.group], v.co) for g in v.groups if g.weight > 1e-4})
# smooth the weights over the surface so joints bend in soft folds instead of creases
nbrs = [[] for _ in me_b.vertices]
for e in me_b.edges:
    a, b = e.vertices
    nbrs[a].append(b)
    nbrs[b].append(a)
for _ in range(6):
    new = []
    for vi, ws in enumerate(W):
        acc = {k: 0.5 * w for k, w in ws.items()}
        nb = nbrs[vi]
        for o in nb:
            for k, w in W[o].items():
                acc[k] = acc.get(k, 0.0) + 0.5 * w / len(nb)
        new.append(acc)
    W = [{k: w * region(k, me_b.vertices[vi].co) for k, w in ws.items()} for vi, ws in enumerate(new)]
fixed = 0
for vi, ws in enumerate(W):
    v = me_b.vertices[vi]
    ws = dict(sorted(((k, w) for k, w in ws.items() if w > 0.01), key=lambda kv: -kv[1])[:4])
    total = sum(ws.values())
    for g in list(v.groups):
        body.vertex_groups[g.group].remove([vi])
    if total <= 1e-6:
        fixed += 1
        continue
    for n, w in ws.items():
        body.vertex_groups[n].add([vi], w / total, "REPLACE")
if fixed:
    # any vertex left without weights copies its nearest weighted neighbour
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
    if ob["bone"] == "__custom__":
        continue                       # pupils carry their own four-bone weights
    vg = ob.vertex_groups.new(name=ob["bone"])
    vg.add([v.index for v in ob.data.vertices], 1.0, "REPLACE")
activate(body, parts)
bpy.ops.object.join()
cat = bpy.context.view_layer.objects.active
cat.name = "Cat"
for k in ("bone", "ear_base", "ear_tip", "eye"):
    if k in cat:
        del cat[k]
missing = [b.name for b in arm.data.bones if b.use_deform and not cat.vertex_groups.get(b.name)]
print("DEFORM_BONES_WITHOUT_WEIGHTS", missing)

# ---------------------------------------------------------------- animation (cat_anim.py)
import cat_anim as CA  # noqa: E402
scene.render.fps = CA.FPS
acts = CA.bake(arm, scene)
print("JUMP_CLAMPED_FRAMES", CA.ground_clamp(arm, cat, scene, acts["Jump"], CA.CLIPS["Jump"]["frames"]))
print("CONTACT", json.dumps(CA.contact_report(arm, cat, scene, acts)))
print("SPEEDS_MPS", json.dumps({k: round(v.get("speed", 0.0), 3) for k, v in CA.CLIPS.items()}))

# ---------------------------------------------------------------- NLA, save
for name, act in acts.items():
    tr = arm.animation_data.nla_tracks.new()
    tr.name = name
    st = tr.strips.new(name, 1, act)
    st.name = name
    tr.mute = True
arm.animation_data.action = acts["Idle"]
scene.frame_start, scene.frame_end = 1, CA.CLIPS["Idle"]["frames"] + 1
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
