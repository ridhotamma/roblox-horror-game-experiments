# Review renders of the StylizedTree: a Preview collection (ground, sun, sky, camera; never exported) and EEVEE
# renders from a few angles to ../out/render-<view>.png. Set VIEWS to render fewer.
import os, math
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else bpy.path.abspath("//")
OUT = os.path.join(os.path.dirname(HERE), "out")
VIEWS = {"front": (20, 12), "side": (110, 10), "low": (200, 2), "top": (300, 45)}   # yaw, pitch (degrees)
TARGET = Vector((0, 0, 3.2))
DIST = 15.5


def preview_rig():
    sc = bpy.context.scene
    col = bpy.data.collections.get("Preview")
    if not col:
        col = bpy.data.collections.new("Preview")
        sc.collection.children.link(col)
    for o in list(col.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    # ground
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
    g = bpy.context.active_object; g.name = "PreviewGround"
    for c in g.users_collection: c.objects.unlink(g)
    col.objects.link(g)
    gm = bpy.data.materials.get("PreviewGround") or bpy.data.materials.new("PreviewGround")
    gm.use_nodes = True
    gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.22, 0.30, 0.13, 1)
    gm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 1
    g.data.materials.clear(); g.data.materials.append(gm)
    # sun
    sun = bpy.data.objects.new("PreviewSun", bpy.data.lights.new("PreviewSun", "SUN"))
    sun.data.energy = 4.5
    sun.data.angle = math.radians(3)
    sun.rotation_euler = (math.radians(40), 0, math.radians(-35))
    col.objects.link(sun)
    # camera
    cam = bpy.data.objects.new("PreviewCam", bpy.data.cameras.new("PreviewCam"))
    cam.data.lens = 50
    col.objects.link(cam)
    sc.camera = cam
    # sky
    w = sc.world or bpy.data.worlds.new("World")
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.55, 0.68, 0.85, 1)
    bg.inputs["Strength"].default_value = 0.45
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = sc.render.resolution_y = 900
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX"
    return cam


def render_views(views=VIEWS):
    cam = preview_rig()
    sc = bpy.context.scene
    os.makedirs(OUT, exist_ok=True)
    files = []
    for name, (yaw, pitch) in views.items():
        y, p = math.radians(yaw), math.radians(pitch)
        cam.location = TARGET + Vector((math.sin(y) * math.cos(p), -math.cos(y) * math.cos(p), math.sin(p))) * DIST
        cam.rotation_euler = (TARGET - cam.location).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = os.path.join(OUT, f"render-{name}.png")
        bpy.ops.render.render(write_still=True)
        files.append(sc.render.filepath)
    return files


def compare_normals(view="front"):
    """Renders the same view with plain flat card normals (render-<view>-flat-normals.png), then rebuilds the
    tree with the transferred normals. Shows what the normal transfer does."""
    leaves = bpy.data.objects["Leaves"]
    bpy.ops.object.select_all(action="DESELECT")
    leaves.select_set(True)
    bpy.context.view_layer.objects.active = leaves
    bpy.ops.mesh.customdata_custom_splitnormals_clear()
    for p in leaves.data.polygons:
        p.use_smooth = False
    f = render_views({view + "-flat-normals": VIEWS[view]})
    ns = {"__file__": os.path.join(HERE, "build_tree.py"), "__name__": "build_tree"}
    exec(open(ns["__file__"], encoding="utf-8").read(), ns)
    return f + render_views({view: VIEWS[view]})


if globals().get("COMPARE"):
    result = {"files": compare_normals(globals()["COMPARE"])}
else:
    result = {"files": render_views({k: VIEWS[k] for k in (globals().get("ONLY") or VIEWS)})}
