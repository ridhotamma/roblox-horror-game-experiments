"""Import Cat.glb into a clean scene and render verification frames."""
import bpy
import os
from mathutils import Vector

OUT = r"C:\Users\ridho\kerjaan\roblox-horror-game-experiments\models\cat"
GLB = os.path.join(OUT, "out", "Cat.glb")
R = os.path.join(OUT, "out")

bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 720
scene.render.resolution_y = 600
try:
    scene.eevee.taa_render_samples = 20
except Exception:
    pass
try:
    scene.view_settings.look = 'AgX - Medium High Contrast'
except Exception:
    pass

bpy.ops.import_scene.gltf(filepath=GLB)
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
print("IMPORTED", {"meshes": [o.name for o in meshes], "arms": [o.name for o in arms],
                   "actions": [a.name for a in bpy.data.actions]})
for a in arms:
    print("ARM", a.name, "nla", [(t.name, t.mute, [(s.name, s.action.name if s.action else None) for s in t.strips]) for t in (a.animation_data.nla_tracks if a.animation_data else [])])

# world + lights + floor
world = bpy.data.worlds.new("W")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.03, 0.032, 0.036, 1)
scene.world = world

def mat(name, col, rough=0.8):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Roughness"].default_value = rough
    return m

bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 0, 0))
floor = bpy.context.view_layer.objects.active
floor.data.materials.append(mat("Floor", (0.045, 0.05, 0.055), 0.9))

def area(name, loc, e, size):
    ld = bpy.data.lights.new(name, 'AREA'); ld.energy = e; ld.size = size
    ob = bpy.data.objects.new(name, ld); bpy.context.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector((0, 0, 0.25)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()

area("Key", (1.3, -1.5, 1.35), 55, 1.5)
area("Fill", (-1.6, -0.9, 0.95), 30, 1.8)
area("Rim", (0.1, 1.55, 1.2), 45, 1.2)

cam_data = bpy.data.cameras.new("Cam"); cam_data.lens = 65
cam = bpy.data.objects.new("Cam", cam_data); bpy.context.collection.objects.link(cam)
scene.camera = cam

def shot(name, frame, action_name, loc=(0.95, -1.12, 0.52), target=(0, 0.02, 0.22), ortho=None, res=(720, 600)):
    arm = arms[0]
    act = bpy.data.actions.get(action_name)
    if act:
        arm.animation_data_create()
        arm.animation_data.action = act
        try:
            if arm.animation_data.action_slot is None and act.slots:
                arm.animation_data.action_slot = act.slots[0]
        except Exception:
            pass
    scene.frame_set(frame)
    scene.render.resolution_x, scene.render.resolution_y = res
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.type = 'ORTHO' if ortho else 'PERSP'
    if ortho:
        cam.data.ortho_scale = ortho
    scene.render.filepath = os.path.join(R, f"glb_{name}.png")
    bpy.ops.render.render(write_still=True)
    print("GLB_RENDER", name)

shot("walk7", 7, "Walk")
shot("run9", 9, "Run")
shot("jump18", 18, "Jump")
shot("head", 1, "Idle", loc=(0.35, -0.66, 0.42), target=(0.0, -0.27, 0.32), ortho=0.34, res=(700, 700))
print("IMPORT_TEST_DONE")
