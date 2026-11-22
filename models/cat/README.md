# Tuxedo Cat — low-poly, rigged, animated

Built in Blender 5.3 through the Blender MCP bridge. A stylized tuxedo cat with a
25-bone rig and four game-ready clips: **Idle**, **Walk**, **Run**, **Jump**.

![hero](out/cat_hero.png)

## Specs

| | |
|---|---|
| Bounds | 0.25 m wide × 0.82 m long × 0.50 m tall (tail up) |
| Shoulder height | ~0.33 m |
| Nose-to-tail-base | ~0.57 m |
| Triangles | 5,252 (4,500 body + 752 details) |
| Vertices | 2,668 |
| Materials | 7, no textures — the tuxedo markings are vertex colours (`COLOR_0`) |
| Rig | 25 bones: `Root` + 24 deform bones |
| Frame rate | 24 fps |
| Forward | −Y in Blender, +Z in glTF |

The body is a voxel-unioned, decimated mesh (legs, tail, paws and toes merged into
one continuous surface), with explicit low-poly ears, eyes, nose, mouth and whiskers.
The rig is a simple FK chain, skinned with automatic weights plus rigid weights for
the head details.

## Animations

| Clip | Frames | Duration | Loop | What it shows |
|---|---|---|---|---|
| `Idle` | 1–97 | 4.0 s | yes | breathing, weight shift, slow head look, tail sway, ear flicks |
| `Walk` | 1–25 | 1.0 s | yes | four-beat lateral walk, in place |
| `Run` | 1–17 | 0.667 s | yes | bounding gallop with suspension, in place |
| `Jump` | 1–40 | 1.625 s | no | crouch → launch → tuck at apex → land → recover |

- Loops are authored with the last frame equal to the first; the GLB clips start at
  `t = 0` and loop exactly (`Idle` 4.0 s, `Walk` 1.0 s, `Run` 0.6667 s).
- A per-frame ground-contact pass raises the root just enough to keep the lowest
  vertex at `z = 0`. The jump carries its vertical motion on the `Root` bone.
- `Walk` and `Run` have no forward translation, so a gameplay controller can move
  the character.

## Files

| File | Use |
|---|---|
| `out/Cat.blend` | final scene, `Idle` active; all clips are in the Action editor and stashed in NLA tracks |
| `out/Cat.glb` | main asset: skinned mesh + 4 animations, metres, vertex colours |
| `out/Cat.roblox.glb` | same asset pre-scaled to 4.5 studs per metre (3.70 studs long, 2.24 tall) |
| `out/Cat.fbx` | same rig and clips for DCC/FBX pipelines |
| `out/preview_idle.mp4` | 640×640 preview |
| `out/preview_walk.mp4` | 640×640 preview |
| `out/preview_run.mp4` | 640×640 preview |
| `out/preview_jump.mp4` | 640×640 preview |
| `out/preview_all.mp4` | combined showcase (idle, walk ×2, run ×3, jump) |
| `out/cat_hero.png` | hero render |
| `out/cat_side.png` | orthographic side view |
| `out/strip_*.png` | 8-frame review sheets per clip |
| `blender/*.py` | full build → rig → animate → export pipeline |
| `refs/` | measurement reference and licence |

## Using it

**Blender:** open `out/Cat.blend`, select `CatRig`, and pick an action in the
Dope Sheet → Action Editor. The scene is set to the Idle clip; press Space to play.
Frame range is 1–97 at 24 fps.

**glTF / three.js / Godot / Unity:** import `out/Cat.glb`. It contains one skinned
mesh, one skin and four named animations. The mesh uses vertex colours, so use a
material that supports `COLOR_0` (three.js does by default).

**Roblox:** import `out/Cat.roblox.glb` with the 3D Importer. It is pre-scaled to
**4.5 studs per metre** (the same scale as this repo's house and tree), so the cat is
about **3.70 studs long** and **2.24 studs tall** — no manual scaling needed. If you
prefer real-world metres, use `out/Cat.glb` instead. The `Jump` clip already contains
the vertical root motion. Use `CollisionFidelity = Box` for the body and disable
collision on the whiskers/eyes if your importer splits them out.

## Notes / limits

- Low-poly style with smooth-by-polygon normals; no textures, UV maps or blend shapes.
- The rig is FK-only (no IK controls). Paws are counter-rotated so they stay level,
  and the root is ground-clamped per frame.
- The tuxedo pattern is baked into a point colour attribute; if your engine ignores
  vertex colours, the cat falls back to the material base colour.

## Rebuild

The pipeline is scripted for Blender 5.3. Run the files in order from Blender's
Text Editor or via the MCP bridge:

1. `blender/01_build.py` — body, head details, vertex colours, studio; saves `cat_stage1.blend`
2. `blender/02_rig.py` — armature, automatic weights, accessory weights, test pose; saves `cat_stage2.blend`
3. `blender/03_anim.py` — builds the four actions, ground-clamps them, saves `cat_stage3.blend`
4. `blender/06_export.py` — fixes accessory vertex colours, saves `out/Cat.blend`, exports GLB/FBX
5. `blender/09_roblox_export.py` — exports `out/Cat.roblox.glb` at 4.5 studs/m
6. `blender/08_video.py` / `blender/04_strips.py` — preview renders (optional)

`01_build.py` / `02_rig.py` / `03_anim.py` contain hard-coded absolute paths for this
workspace; change `OUT` if you move the project.

## Reference

`refs/cat_side.jpg` — “Domestic cat in Poland 1.jpg”, Wikimedia Commons, CC BY-SA 4.0.
Used for proportions and silhouette only; the model, colours and animation are original.
