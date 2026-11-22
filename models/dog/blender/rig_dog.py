"""Rigs the Dog: builds the DogRig armature from dog_spec.py, skins the body with bone-heat weights, gives the
eyes, nose, ears and collar rigid weights, joins everything into one mesh "Dog" and cleans the weights for Roblox
(at most 4 influences per vertex, normalised, no stray tiny weights).

Every bone's roll is set so its local X axis is world +X: a positive local X rotation pitches a spine bone up and
swings a leg bone forward, which keeps the animation maths simple (animate_dog.py).

  blender -b models/dog/blender/Dog_mesh.blend --python models/dog/blender/rig_dog.py
"""
import os
import sys
import json
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dog_spec as S  # noqa: E402

MAX_INFLUENCES = 4      # Roblox skinning limit
MIN_WEIGHT = 0.02


def deselect_all():
    for o in list(bpy.context.scene.objects):
        o.select_set(False)


def make_armature(ear_bones, eye_bones=None):
    arm = bpy.data.armatures.new("DogRig")
    arm.display_type = "STICK"
    rig = bpy.data.objects.new("DogRig", arm)
    bpy.context.scene.collection.objects.link(rig)
    deselect_all()
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bones = S.all_bones()
    for side in ("L", "R"):
        head, tail = ear_bones[side]
        bones[f"Ear_{side}"] = (tuple(head), tuple(tail), "Head", True)
    for side, eye in (eye_bones or {}).items():
        # face rig: lids and pupil bones at the eyeball centre pointing along the gaze (shared/face_rig.py)
        c, d = Vector(eye["centre"]), Vector(eye["dir"])
        for nm in S.FACE_BONES:
            bones[f"{nm}_{side}"] = (tuple(c), tuple(c + d * eye["r"]), "Head", True)
    eb = arm.edit_bones
    for name, (head, tail, _parent, deform) in bones.items():
        b = eb.new(name)
        b.head = head
        b.tail = tail
        b.use_deform = deform
    for name, (head, _tail, parent, _deform) in bones.items():
        if parent:
            b = eb[name]
            b.parent = eb[parent]
            b.use_connect = (Vector(eb[parent].tail) - Vector(head)).length < 1e-5
    for b in eb:
        y = (b.tail - b.head).normalized()
        z = Vector((1, 0, 0)).cross(y)
        b.align_roll(z)
    bpy.ops.object.mode_set(mode="OBJECT")
    return rig, bones


def rigid_group(ob, bone):
    vg = ob.vertex_groups.new(name=bone)
    vg.add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")


def smoothstep(e0, e1, x):
    t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def region(bone, co):
    """How much a bone may influence a body vertex at co (0..1). Bone heat knows nothing about anatomy: it lets the
    ear bones pull the skull, a left leg pull the right side of the chest, a thigh pull the belly."""
    x, y, z = co
    if bone.startswith(("Ear_", "EyeLid", "Pupil")):
        return 0.0                                     # ears and the face rig are separate pieces
    m = 1.0
    if bone.endswith("_L"):
        m *= smoothstep(-0.004, 0.022, x)
    elif bone.endswith("_R"):
        m *= smoothstep(-0.004, 0.022, -x)
    if bone.startswith("Front"):
        m *= smoothstep(0.07, 0.14, y)
    elif bone.startswith("Hind"):
        m *= 1 - smoothstep(-0.14, -0.07, y)
    elif bone.startswith("Tail"):
        m *= 1 - smoothstep(-0.325, -0.285, y)
    elif bone == "Head":
        m *= smoothstep(0.34, 0.39, y)
    return m


def nearest_spine_bone(rig, co):
    best, bd = None, 1e9
    for name in ("Hips", "Spine", "Chest", "Neck", "Head"):
        b = rig.data.bones[name]
        a, t = b.head_local, b.tail_local
        ab = t - a
        k = max(0.0, min(1.0, (co - a).dot(ab) / ab.length_squared))
        d = (a + ab * k - co).length
        if d < bd:
            best, bd = name, d
    return best


def mask_body_weights(body, rig):
    names = {vg.index: vg.name for vg in body.vertex_groups}
    for v in body.data.vertices:
        ws = {names[g.group]: g.weight * region(names[g.group], v.co) for g in v.groups}
        total = sum(ws.values())
        if total < 1e-4:
            ws = {nearest_spine_bone(rig, v.co): 1.0}
            total = 1.0
        for g in list(v.groups):
            body.vertex_groups[names[g.group]].remove([v.index])
        for n, w in ws.items():
            if w / total > 1e-4:
                vg = body.vertex_groups.get(n) or body.vertex_groups.new(name=n)
                vg.add([v.index], w / total, "REPLACE")
        names = {vg.index: vg.name for vg in body.vertex_groups}


def skin(rig, body, parts):
    # bone heat on the body only (one closed shell); accessories are rigid
    deselect_all()
    body.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    mask_body_weights(body, rig)
    for ob in parts:
        n = ob.name
        if n.startswith("EyeLid"):
            rigid_group(ob, n)                 # EyeLidUp_L ... (object and bone share the name)
        elif n.startswith("Pupil_"):
            pass                               # carries its own four-bone weights from build_dog.py
        elif n.startswith(("Eye", "Nose")):
            rigid_group(ob, "Head")
        elif n.startswith("Ear_"):
            pass                               # root on Head blending into Ear_L / Ear_R, from build_dog.py
        elif n in ("Collar", "Tag"):
            rigid_group(ob, "Neck")
        else:
            raise RuntimeError(f"no weight rule for {n}")
    deselect_all()
    for ob in parts + [body]:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    dog = bpy.context.view_layer.objects.active
    dog.name = "Dog"
    dog.data.name = "Dog"
    # the join keeps body's Armature modifier and parent
    return dog


def clean_weights(dog, rig):
    deform = {b.name for b in rig.data.bones if b.use_deform}
    for vg in list(dog.vertex_groups):
        if vg.name not in deform:
            dog.vertex_groups.remove(vg)
    names = {vg.index: vg.name for vg in dog.vertex_groups}
    unweighted = 0
    for v in dog.data.vertices:
        ws = sorted(((g.weight, g.group) for g in v.groups if g.weight > 0), reverse=True)
        keep = [(w, g) for (w, g) in ws[:MAX_INFLUENCES] if w >= MIN_WEIGHT] or ws[:1]
        if not keep:
            unweighted += 1
            continue
        total = sum(w for w, _ in keep)
        keep_ids = {g for _, g in keep}
        for g in [g.group for g in v.groups]:
            if g not in keep_ids:
                dog.vertex_groups[names[g]].remove([v.index])
        for w, g in keep:
            dog.vertex_groups[names[g]].add([v.index], w / total, "REPLACE")
    return unweighted


def weight_report(dog):
    names = {vg.index: vg.name for vg in dog.vertex_groups}
    per_bone = {n: 0 for n in names.values()}
    max_inf = 0
    bad_sum = 0
    for v in dog.data.vertices:
        gs = [g for g in v.groups if g.weight > 0]
        max_inf = max(max_inf, len(gs))
        if gs and abs(sum(g.weight for g in gs) - 1) > 1e-3:
            bad_sum += 1
        if gs:
            top = max(gs, key=lambda g: g.weight)
            per_bone[names[top.group]] += 1
    return {"max_influences": max_inf, "not_normalised": bad_sum, "verts_by_main_bone": per_bone}


def bleed_check(dog):
    """Weights that land on the wrong side or the wrong leg: left-leg bones on right-side verts etc."""
    names = {vg.index: vg.name for vg in dog.vertex_groups}
    bad = {}
    for v in dog.data.vertices:
        x, y, z = v.co
        for g in v.groups:
            n = names[g.group]
            if g.weight < 0.05:
                continue
            if (n.endswith("_L") and x < -0.02) or (n.endswith("_R") and x > 0.02):
                bad[n] = bad.get(n, 0) + 1
            if n.startswith("Front") and y < 0.0:
                bad[n] = bad.get(n, 0) + 1
            if n.startswith("Hind") and y > 0.05:
                bad[n] = bad.get(n, 0) + 1
            if n.startswith("Tail") and y > -0.25:
                bad[n] = bad.get(n, 0) + 1
    return bad


def main():
    body = bpy.data.objects["DogBody"]
    parts = list(bpy.data.collections["DogParts"].objects)
    ear_bones = {k: v for k, v in body["ear_bones"].items()}
    eye_bones = {k: dict(v) for k, v in body["eye_bones"].items()} if "eye_bones" in body else None
    rig, bones = make_armature(ear_bones, eye_bones)
    dog = skin(rig, body, parts)
    unweighted = clean_weights(dog, rig)
    coll = bpy.data.collections["DogParts"]
    bpy.data.collections.remove(coll)
    report = weight_report(dog)
    report["unweighted"] = unweighted
    report["bleed"] = bleed_check(dog)
    report["bones"] = len(rig.data.bones)
    report["verts"] = len(dog.data.vertices)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "Dog_rig.blend"))
    print("RESULT", json.dumps(report))


if __name__ == "__main__":
    main()
