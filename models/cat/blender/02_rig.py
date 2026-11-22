"""Stage 2: armature, weights and a deformation test pose.

Opens cat_stage1.blend, builds the rig, parents the mesh with automatic weights,
forces rigid accessories (ears, eyes, nose, whiskers, mouth) onto their bones,
renders a test pose and saves cat_stage2.blend.
"""
import bpy
import math
import os
from math import radians
from mathutils import Vector

OUT = r"C:\Users\ridho\kerjaan\roblox-horror-game-experiments\models\cat"
RENDER_DIR = os.path.join(OUT, "out")
BLEND = os.path.join(OUT, "blender", "cat_stage1.blend")
bpy.ops.wm.open_mainfile(filepath=BLEND)
scene = bpy.context.scene
cat = bpy.data.objects["Cat"]


def mode(ob, m):
    bpy.ops.object.select_all(action='DESELECT')
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    with bpy.context.temp_override(object=ob, active_object=ob,
                                   selected_objects=[ob], selected_editable_objects=[ob]):
        bpy.ops.object.mode_set(mode=m)


# ---------------------------------------------------------------- armature
arm_data = bpy.data.armatures.new("CatRig")
arm = bpy.data.objects.new("CatRig", arm_data)
bpy.context.collection.objects.link(arm)
arm.show_in_front = True
arm_data.display_type = 'OCTAHEDRAL'

mode(arm, 'EDIT')
eb = arm_data.edit_bones


def bone(name, head, tail, parent=None, connect=False, roll_z=None, deform=True):
    b = eb.new(name)
    b.head = Vector(head)
    b.tail = Vector(tail)
    if parent:
        b.parent = eb[parent]
        b.use_connect = connect
    if roll_z is not None:
        b.align_roll(Vector(roll_z))
    b.use_deform = deform
    return b


bone("Root", (0, 0, 0), (0, 0.10, 0), roll_z=(0, 0, 1), deform=False)

# spine: local X = +X, local Z = -Z, local Y = forward (-Y)
SPINE_ROLL = (0, 0, -1)
bone("Hips", (0, 0.175, 0.245), (0, 0.085, 0.247), "Root", roll_z=SPINE_ROLL)
bone("Spine1", (0, 0.085, 0.247), (0, -0.005, 0.250), "Hips", True, SPINE_ROLL)
bone("Spine2", (0, -0.005, 0.250), (0, -0.100, 0.257), "Spine1", True, SPINE_ROLL)
bone("Chest", (0, -0.100, 0.257), (0, -0.170, 0.272), "Spine2", True, SPINE_ROLL)
bone("Neck", (0, -0.170, 0.272), (0, -0.225, 0.298), "Chest", True, SPINE_ROLL)
bone("Head", (0, -0.225, 0.298), (0, -0.340, 0.302), "Neck", True, SPINE_ROLL)

# tail: local X = +X, local Z = -Y
TAIL_ROLL = (0, -1, 0)
TP = [(0, 0.195, 0.252), (0, 0.286, 0.292), (0, 0.356, 0.346), (0, 0.400, 0.418), (0, 0.421, 0.498)]
for i in range(4):
    bone(f"Tail{i+1}", TP[i], TP[i + 1], "Hips" if i == 0 else f"Tail{i}", i > 0, TAIL_ROLL)

# legs: local X = +X, local Z = +Y
LEG_ROLL = (0, 1, 0)
for s, sx in (("L", 1), ("R", -1)):
    bone(f"UpperArm.{s}", (0.058 * sx, -0.100, 0.212), (0.058 * sx, -0.073, 0.130), "Chest", False, LEG_ROLL)
    bone(f"Forearm.{s}", (0.058 * sx, -0.073, 0.130), (0.058 * sx, -0.095, 0.057), f"UpperArm.{s}", True, LEG_ROLL)
    bone(f"Paw.{s}", (0.058 * sx, -0.095, 0.057), (0.058 * sx, -0.135, 0.024), f"Forearm.{s}", True, LEG_ROLL)
    bone(f"Thigh.{s}", (0.061 * sx, 0.152, 0.218), (0.062 * sx, 0.200, 0.134), "Hips", False, LEG_ROLL)
    bone(f"Shin.{s}", (0.062 * sx, 0.200, 0.134), (0.062 * sx, 0.176, 0.070), f"Thigh.{s}", True, LEG_ROLL)
    bone(f"Foot.{s}", (0.062 * sx, 0.176, 0.070), (0.060 * sx, 0.120, 0.024), f"Shin.{s}", True, LEG_ROLL)
    bone(f"Ear.{s}", (0.034 * sx, -0.258, 0.331), (0.045 * sx, -0.251, 0.410), "Head", False, (0, 1, 0))

mode(arm, 'OBJECT')

# ---------------------------------------------------------------- automatic weights
bpy.ops.object.select_all(action='DESELECT')
cat.select_set(True)
arm.select_set(True)
bpy.context.view_layer.objects.active = arm
with bpy.context.temp_override(object=arm, active_object=arm,
                               selected_objects=[cat, arm], selected_editable_objects=[cat, arm]):
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
print("PARENTED auto weights")

# ---------------------------------------------------------------- force rigid accessories
def force_group(tag_name, bone_name):
    tag = cat.vertex_groups.get(tag_name)
    if not tag:
        print("MISSING TAG", tag_name)
        return
    ti = tag.index
    ids = [v.index for v in cat.data.vertices if any(g.group == ti for g in v.groups)]
    vg = cat.vertex_groups.get(bone_name)
    if vg is None:
        vg = cat.vertex_groups.new(name=bone_name)
    for group in list(cat.vertex_groups):
        group.remove(ids)
    vg.add(ids, 1.0, 'REPLACE')
    bpy.data.objects  # no-op
    print("FORCED", tag_name, "->", bone_name, len(ids), "verts")


force_group("TAG_Ear_L", "Ear.L")
force_group("TAG_Ear_R", "Ear.R")
force_group("TAG_Head", "Head")

for name in ("TAG_Ear_L", "TAG_Ear_R", "TAG_Head"):
    vg = cat.vertex_groups.get(name)
    if vg:
        cat.vertex_groups.remove(vg)

# make sure every pose bone has an XYZ mode and clean rest pose
for pb in arm.pose.bones:
    pb.rotation_mode = 'XYZ'

# ---------------------------------------------------------------- report weights
missing = []
for b in arm.data.bones:
    if b.use_deform and not cat.vertex_groups.get(b.name):
        missing.append(b.name)
print("DEFORM_BONES_WITH_NO_GROUP", missing)
print("VGROUPS", [g.name for g in cat.vertex_groups])

# ---------------------------------------------------------------- test pose
def pose(name, rx=0, ry=0, rz=0):
    pb = arm.pose.bones[name]
    pb.rotation_mode = 'XYZ'
    pb.rotation_euler = (radians(rx), radians(ry), radians(rz))


pose("Spine2", rz=6)
pose("Neck", rz=10, rx=-8)
pose("Head", rz=18, rx=-6)
pose("UpperArm.L", rx=-28)
pose("Forearm.L", rx=30)
pose("Thigh.R", rx=26)
pose("Shin.R", rx=-38)
pose("Foot.R", rx=10)
pose("Tail1", rx=-10, rz=8)
pose("Tail2", rx=-14, rz=10)
pose("Tail3", rx=-18, rz=12)
pose("Tail4", rx=-20, rz=10)
bpy.context.view_layer.update()


def render(path, loc, target, ortho=None, res=(900, 900)):
    cam = bpy.data.objects["Camera"]
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = res
    cam.location = loc
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    if ortho:
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = ortho
    else:
        cam.data.type = 'PERSP'
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("RENDERED", path)


render(os.path.join(RENDER_DIR, "cat_rig_test_3q.png"), (0.94, -1.10, 0.52), (0.0, 0.02, 0.22))
render(os.path.join(RENDER_DIR, "cat_rig_test_side.png"), (1.8, 0.02, 0.25), (0, 0.02, 0.25), ortho=0.92, res=(1100, 850))

# clear pose
for pb in arm.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.location = (0, 0, 0)
    pb.scale = (1, 1, 1)
bpy.context.view_layer.update()

# save
blend_path = os.path.join(OUT, "blender", "cat_stage2.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print("STAGE2_DONE", {
    "bones": len(arm.data.bones),
    "deform_bones": sum(1 for b in arm.data.bones if b.use_deform),
    "verts": len(cat.data.vertices),
    "blend": blend_path,
})
