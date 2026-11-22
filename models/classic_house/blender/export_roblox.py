# Exports the textured ClassicHouse from Blender for Roblox, without touching the scene you work in:
#   out/ClassicHouse.textured.glb  - merged by material: few MeshParts; flat colours become vertex colours
#   roblox/HouseSetup.lua          - Studio command-bar script: collision setup + invisible box collision
# Groups kept apart so scripts can drive them: FrontDoor*, BackDoor* (hinged doors), RoofGroup* (roof toggle).
# MeshPart names: <Group>__<material>__<collision>, collision "none" (rendering only) or "default".
# The main door slabs keep the plain names FrontDoor / BackDoor (HouseDoors.server.luau looks for them).
import os, re, json
import bpy, bmesh

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SPEC = os.path.join(ROOT, "classic_house.json")
GLB = os.path.join(ROOT, "out", "ClassicHouse.textured.glb")
LUA = os.path.join(ROOT, "roblox", "HouseSetup.lua")
GROUP_ROOTS = ("FrontDoor", "BackDoor", "RoofGroup")


def base_name(o):
    return re.sub(r"(_src)?(\.\d{3})?$", "", o.name)


def group_of(o):
    p = o
    while p:
        if base_name(p) in GROUP_ROOTS:
            return base_name(p)
        p = p.parent
    return "House"


def flat_material(emissive):
    name = "RBX_VertexGlow" if emissive else "RBX_VertexColor"
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    ca = nt.nodes.new("ShaderNodeVertexColor")
    ca.layer_name = "Col"
    nt.links.new(ca.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.8
    if emissive:
        nt.links.new(ca.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = 1.5
    return m


def mat_info(m):
    """(is_textured, linear base colour, emissive?)"""
    if m is None or not m.use_nodes:
        return False, (0.8, 0.8, 0.8), False
    if m.name.startswith("TXM_"):
        return True, None, False
    b = m.node_tree.nodes.get("Principled BSDF")
    if not b:
        return False, (0.8, 0.8, 0.8), False
    col = tuple(b.inputs["Base Color"].default_value)[:3]
    em = b.inputs["Emission Color"].default_value
    strength = b.inputs["Emission Strength"].default_value
    emissive = strength > 0 and max(em[:3]) > 0.01
    return False, col, emissive


def split_copy(src, scene_col):
    """World-space copies of src, one per material, each with a single material (flat ones -> vertex colours)."""
    out = []
    me = src.data
    used = sorted({p.material_index for p in me.polygons})
    for mi in used:
        m = src.material_slots[mi].material if mi < len(src.material_slots) else None
        textured, col, emissive = mat_info(m)
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.transform(src.matrix_world)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index != mi], context="FACES")
        for f in bm.faces:
            f.material_index = 0
        nm = bpy.data.meshes.new(base_name(src) + "_x")
        bm.to_mesh(nm)
        bm.free()
        if textured:
            nm.materials.append(m)
            key = m.name[4:]
        else:
            attr = nm.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
            vals = list(col) + [1.0]
            for d in attr.data:
                d.color = vals
            nm.materials.append(flat_material(emissive))
            key = "Glow" if emissive else "Color"
        ob = bpy.data.objects.new(base_name(src) + "_x", nm)
        scene_col.objects.link(ob)
        out.append((ob, key))
    return out


def join(objs, name):
    if len(objs) > 1:
        with bpy.context.temp_override(active_object=objs[0], selected_editable_objects=objs, selected_objects=objs):
            bpy.ops.object.join()
    objs[0].name = name
    objs[0].data.name = name
    return objs[0]


def spec_collision_boxes():
    spec = json.load(open(SPEC, encoding="utf-8"))
    parts = {p["name"]: p for p in spec["parts"]}

    def under(p, root):
        while p:
            if p["name"] == root:
                return True
            p = parts.get(p.get("parent"))
        return False

    boxes = []
    for p in spec["parts"]:
        coll = p.get("collision", "auto")
        if coll == "none" or any(under(p, g) for g in GROUP_ROOTS):
            continue
        if p["shape"] == "box":
            size = p["size"]
        elif p["shape"] == "cylinder" and isinstance(p.get("radius"), (int, float)) and p.get("axis", "y") == "y":
            size = [2 * p["radius"], p["height"], 2 * p["radius"]]
        else:
            continue
        at = p.get("at", [0, 0, 0])
        boxes.append((p["name"], at, size))
        if p.get("mirror") == "x":
            boxes.append((re.sub(r"L$", "R", p["name"]) if p["name"].endswith("L") else p["name"] + "M", [-at[0], at[1], at[2]], size))
    return boxes


def write_lua(bmin, bmax, boxes):
    f3 = lambda v: ", ".join(f"{x:.4f}" for x in v)
    rows = "\n".join(f'\t{{ "{n}", {f3(a)}, {f3(s)} }},' for n, a, s in boxes)
    lua = f"""-- ClassicHouse (textured) - Roblox Studio setup. Generated by blender/export_roblox.py; do not edit by hand.
-- 1. Import out/ClassicHouse.textured.glb (File > Import 3D). Keep the importer's Merge Meshes OFF.
--    Scale it to taste (real size: 1 m = 3.57 studs at a 1.8 m = 6.4 stud avatar scale; the script reads the scale).
-- 2. Select the imported model in the Explorer, paste this into the command bar and press Enter.
-- It anchors everything, turns collision off on the render meshes (their names end in __none), gives the
-- roof meshes Default collision, the door slabs Box collision, and builds invisible box Parts ("Collision")
-- for walls, floors, steps and furniture from the model's own measurements, plus an "InteriorZone" part
-- that RoofToggle.client.luau uses to hide the roof while a player is inside.
-- Set SHOW_COLLISION = true to see the boxes (check they line up, e.g. after rotating the model).
local SHOW_COLLISION = false

-- model-space bounds of the exported file (metres, Y up, front +Z)
local MODEL_MIN = Vector3.new({f3(bmin)})
local MODEL_MAX = Vector3.new({f3(bmax)})
local INTERIOR = {{ Vector3.new(-4.95, 0.47, -3.85), Vector3.new(4.95, 3.28, 3.85) }}
-- {{ name, centre x, y, z, size x, y, z }} in metres, model space
local BOXES = {{
{rows}
}}

local root = game:GetService("Selection"):Get()[1]
assert(root and root:IsA("Model"), "select the imported ClassicHouse model first")

local meshes = 0
for _, d in root:GetDescendants() do
	if d:IsA("BasePart") then
		d.Anchored = true
	end
	if d:IsA("MeshPart") then
		meshes += 1
		local coll = string.match(d.Name, "__(%a+)$")
		if d.Name == "FrontDoor" or d.Name == "BackDoor" then
			d.CollisionFidelity = Enum.CollisionFidelity.Box
			d.CanCollide = true
		elseif coll == "default" then
			d.CollisionFidelity = Enum.CollisionFidelity.Default
			d.CanCollide = true
		else
			d.CanCollide = false
			d.CanTouch = false
			d.CanQuery = string.sub(d.Name, 1, 9) == "FrontDoor" or string.sub(d.Name, 1, 8) == "BackDoor"
		end
	end
end

local old = root:FindFirstChild("Collision")
if old then old:Destroy() end
local oldZone = root:FindFirstChild("InteriorZone")
if oldZone then oldZone:Destroy() end

-- model space -> world: the imported model's bounding box matches MODEL_MIN..MODEL_MAX
local bbCF, bbSize = root:GetBoundingBox()
local modelSize = MODEL_MAX - MODEL_MIN
local scale = bbSize.Y / modelSize.Y
local centre = (MODEL_MIN + MODEL_MAX) / 2
local function toWorld(p: Vector3): CFrame
	return bbCF * CFrame.new((p - centre) * scale)
end

local folder = Instance.new("Folder")
folder.Name = "Collision"
for _, b in BOXES do
	local part = Instance.new("Part")
	part.Name = b[1]
	part.Anchored = true
	part.CanCollide = true
	part.CanTouch = false
	part.Transparency = if SHOW_COLLISION then 0.5 else 1
	part.CastShadow = false
	part.Size = Vector3.new(b[5], b[6], b[7]) * scale
	part.CFrame = toWorld(Vector3.new(b[2], b[3], b[4]))
	part.Parent = folder
end
folder.Parent = root

local zone = Instance.new("Part")
zone.Name = "InteriorZone"
zone.Anchored = true
zone.CanCollide = false
zone.CanTouch = false
zone.CanQuery = false
zone.Transparency = 1
zone.Size = (INTERIOR[2] - INTERIOR[1]) * scale
zone.CFrame = toWorld((INTERIOR[1] + INTERIOR[2]) / 2)
zone.Parent = root
game:GetService("CollectionService"):AddTag(root, "ClassicHouse")

print(("[ClassicHouse] %d MeshParts set up, %d collision boxes, scale %.3f studs per metre"):format(meshes, #BOXES, scale))
"""
    os.makedirs(os.path.dirname(LUA), exist_ok=True)
    open(LUA, "w", encoding="utf-8").write(lua)


def export(collection_name="ClassicHouse"):
    src_col = bpy.data.collections[collection_name]
    main_scene = bpy.context.window.scene
    tmp = bpy.data.scenes.new("RobloxExportTmp")
    # Object names are global in Blender: free the door names for the exported slabs while exporting.
    renamed = []
    for n in ("FrontDoor", "BackDoor"):
        o = bpy.data.objects.get(n)
        if o:
            o.name = n + "_src"
            renamed.append((o, n))
    try:
        buckets = {}
        for o in src_col.all_objects:
            if o.type != "MESH" or not o.data.polygons:
                continue
            grp = group_of(o)
            name = base_name(o)
            if name in ("FrontDoor", "BackDoor"):
                for ob, key in split_copy(o, tmp.collection):
                    buckets.setdefault((name, "@main", "box"), []).append(ob)  # the slab keeps its plain name
                continue
            coll = "default" if grp == "RoofGroup" and not name.startswith("Lamp") else "none"
            for ob, key in split_copy(o, tmp.collection):
                buckets.setdefault((grp, key, coll), []).append(ob)
        bpy.context.window.scene = tmp  # join works on the active view layer
        made = []
        for (grp, key, coll), objs in sorted(buckets.items()):
            if key == "@main":
                made.append(join(objs, grp))
            else:
                made.append(join(objs, f"{grp}__{key}__{coll}"))
        # bounds in model space (x, y up, z front) = (bx, bz, -by)
        xs, ys, zs = [], [], []
        for ob in made:
            for v in ob.data.vertices:
                xs.append(v.co.x); ys.append(v.co.z); zs.append(-v.co.y)
        bmin = (min(xs), min(ys), min(zs)); bmax = (max(xs), max(ys), max(zs))
        kw = dict(filepath=GLB, export_format="GLB", use_active_scene=True, export_yup=True,
                  export_animations=False, export_materials="EXPORT", export_apply=False)
        try:
            bpy.ops.export_scene.gltf(export_vertex_color="MATERIAL", **kw)
        except TypeError:
            bpy.ops.export_scene.gltf(**kw)
        write_lua(bmin, bmax, spec_collision_boxes())
        names = sorted(o.name for o in made)
        return names, bmin, bmax
    finally:
        bpy.context.window.scene = main_scene
        for ob in list(tmp.collection.objects):
            me = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            if me and me.users == 0:
                bpy.data.meshes.remove(me)
        bpy.data.scenes.remove(tmp)
        for o, n in renamed:
            o.name = n


if __name__ == "__main__":
    names, bmin, bmax = export()
    print(len(names), "MeshParts:", names)
    print("bounds", bmin, bmax, "->", GLB)
