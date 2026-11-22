"""Targeted smoothing of the hip/shoulder junctions on the retopologised cat.

Creates a soft falloff vertex group around the four leg roots and runs a
length-weighted corrective smooth on it. Saves a test blend and renders the
rear angle from the report plus a 3/4 rear view.
"""
import bpy
import bmesh
import math
import os
from mathutils import Vector

OUT = r"C:\Users\ridho\kerjaan\roblox-horror-game-experiments\models\cat"
R = os.path.join(OUT, "out")
bpy.ops.wm.open_mainfile(filepath=os.path.join(R, "Cat.blend"))
scene = bpy.context.scene
arm = bpy.data.objects["CatRig"]
cat = bpy.data.objects["Cat"]
scene.camera = bpy.data.objects["Camera"]
arm.animation_data.action = bpy.data.actions["Idle"]
scene.frame_set(1)
bpy.context.view_layer.update()

# ---------------------------------------------------------------- falloff group
me = cat.data
fur_i = me.materials.find("Cat_FurVC")
centres = [
    (0.060, 0.160, 0.220), (-0.060, 0.160, 0.220),   # hips
    (0.058, -0.100, 0.210), (-0.058, -0.100, 0.210),  # shoulders
]
radii = [0.135, 0.135, 0.115, 0.115]


def smoothstep(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


vg = cat.vertex_groups.get("JunctionSmooth") or cat.vertex_groups.new(name="JunctionSmooth")
weighted = 0
for v in me.vertices:
    w = 0.0
    for (cx, cy, cz), r in zip(centres, radii):
        d = (v.co - Vector((cx, cy, cz))).length
        w = max(w, smoothstep(1.0 - d / r))
    if w > 0.001:
        vg.add([v.index], w, 'REPLACE')
        weighted += 1
print("JUNCTION_GROUP", weighted)

# ---------------------------------------------------------------- smooth
with bpy.context.temp_override(object=cat, active_object=cat,
                               selected_objects=[cat], selected_editable_objects=[cat]):
    mod = cat.modifiers.new("JunctionSmooth", 'CORRECTIVE_SMOOTH')
    mod.factor = 0.45
    mod.iterations = 8
    mod.smooth_type = 'LENGTH_WEIGHTED'
    mod.use_only_smooth = True
    mod.vertex_group = "JunctionSmooth"
    bpy.ops.object.modifier_apply(modifier=mod.name)

# report dihedral angles after
bm = bmesh.new()
bm.from_mesh(me)
bm.edges.ensure_lookup_table()
angles = []
for e in bm.edges:
    if len(e.link_faces) == 2 and e.link_faces[0].material_index == fur_i and e.link_faces[1].material_index == fur_i:
        a = e.calc_face_angle(0.0)
        if a > math.radians(25):
            angles.append((round(math.degrees(a), 1), round(e.verts[0].co.x, 3), round(e.verts[0].co.y, 3), round(e.verts[0].co.z, 3)))
angles.sort(reverse=True)
print("TOP_EDGES_AFTER", angles[:10])
bm.free()

# ---------------------------------------------------------------- save + render
test_blend = os.path.join(OUT, "blender", "cat_smooth_test.blend")
bpy.ops.wm.save_as_mainfile(filepath=test_blend)
print("SAVED", test_blend)

scene.render.image_settings.file_format = 'PNG'
try:
    scene.eevee.taa_render_samples = 28
except Exception:
    pass


def shot(path, loc, target, ortho=None, res=(700, 900)):
    cam = scene.camera
    scene.render.resolution_x, scene.render.resolution_y = res
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.type = 'ORTHO' if ortho else 'PERSP'
    if ortho:
        cam.data.ortho_scale = ortho
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("RENDERED", path)


shot(os.path.join(R, "smooth_rear_high.png"), (0.0, 1.05, 0.56), (0.0, 0.08, 0.23))
shot(os.path.join(R, "smooth_rear_low.png"), (0.0, 1.15, 0.36), (0.0, 0.05, 0.22))
shot(os.path.join(R, "smooth_rear_3q.png"), (0.62, 0.98, 0.46), (0.0, 0.05, 0.22), res=(900, 800))
print("SMOOTH_TEST_DONE")
