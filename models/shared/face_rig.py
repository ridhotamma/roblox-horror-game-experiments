"""Shared eye geometry for the cat and dog face rigs (Blender bmesh; no bpy state).

An eye is a sphere (the iris) of radius r at centre c, looking along d. Six bones sit at c, all with
local Y = d and local Z = the eye's "up" (Z), so local X = d x Z:

  EyeLidUp / EyeLidLow   rotate about local X. Each lid is a hemispherical shell round the eyeball whose
                         straight edge is a great circle through the X axis, so turning it slides the
                         edge over the eye like a real lid. A negative angle lowers an edge.
  PupilW1 / PupilW2      rotate about local Z; the pupil vertices on the +u / -u side follow them.
  PupilH1 / PupilH2      rotate about local X; the +v / -v side follows them.

The pupil is a disc lying on the iris. Every pupil vertex is weighted to all four pupil bones,
bilinearly in its rest (u', v') in [-1, 1]:
  W1 = (1 + u') / 4, W2 = (1 - u') / 4, H1 = (1 + v') / 4, H2 = (1 - v') / 4
so turning W1 by +a and W2 by -a moves each vertex sideways by u' * a * r / 2: the disc scales by
1 + a r / (2 U) across, uniformly. Rotations (not translations) keep the pupil on the eyeball's surface,
and Roblox bones can only rotate in the dog's runtime anyway (Bone.Transform has no scale).
"""
import math
import bmesh
from mathutils import Vector


def frame(d, z_hint):
    """Bone axes for an eye looking along d: (X, Z, u, v). u is the pupil's widening direction for a
    positive W1 rotation, v its upward direction for a positive H1 rotation (and the side a lid edge
    moves toward for a positive lid rotation)."""
    d = Vector(d).normalized()
    z = Vector(z_hint)
    z = (z - d * z.dot(d)).normalized()
    x = d.cross(z)
    return x, z, z.cross(d).normalized(), x.cross(d).normalized()


def pupil_angle(scale, half, r):
    """Bone rotation (radians, for W1 / H1; W2 / H2 take the negative) that scales the pupil by `scale`."""
    return 2.0 * (scale - 1.0) * half / r


def sphere(bm, c, r, segs=24, rings=16):
    geom = bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    for v in geom["verts"]:
        v.co += Vector(c)
    return geom["verts"]


def pupil(bm, c, d, u, v, r, half_u, half_v, lift=0.0008, rings=4, segs=24):
    """Curved elliptical disc on the sphere, facing out along d. Returns [(vert, u', v')]."""
    c, d, u, v = Vector(c), Vector(d).normalized(), Vector(u), Vector(v)
    R = r + lift
    out = []

    def on_sphere(x, y):
        h = math.sqrt(max(1e-12, R * R - x * x - y * y))
        return c + d * h + u * x + v * y

    centre = bm.verts.new(on_sphere(0.0, 0.0))
    out.append((centre, 0.0, 0.0))
    ring_verts = []
    for i in range(1, rings + 1):
        a = i / rings
        row = []
        for k in range(segs):
            t = 2 * math.pi * k / segs
            x, y = a * half_u * math.cos(t), a * half_v * math.sin(t)
            vv = bm.verts.new(on_sphere(x, y))
            out.append((vv, x / half_u, y / half_v))
            row.append(vv)
        ring_verts.append(row)
    for k in range(segs):
        bm.faces.new((centre, ring_verts[0][k], ring_verts[0][(k + 1) % segs]))
    for i in range(rings - 1):
        for k in range(segs):
            k2 = (k + 1) % segs
            bm.faces.new((ring_verts[i][k], ring_verts[i + 1][k], ring_verts[i + 1][k2], ring_verts[i][k2]))
    # face the normals outward (away from the eye centre); call on a bmesh that holds only this disc
    for f in bm.faces:
        f.normal_update()
        if f.normal.dot(f.calc_center_median() - c) < 0:
            f.normal_flip()
    return out


def pupil_weights(uv):
    """Per-vertex bone weights {role: w} for the pupil disc, from (u', v')."""
    up, vp = uv
    return {"W1": 0.25 * (1 + up), "W2": 0.25 * (1 - up), "H1": 0.25 * (1 + vp), "H2": 0.25 * (1 - vp)}


def lid(bm, c, d, x, v, r_in, r_out, edge_deg, upper, n_phi=8, n_lam=14, lam_max=86.0):
    """Closed hemispherical shell round the eye. Its straight edge sits edge_deg above the gaze line
    (negative = below) and the shell runs 180 degrees from there over the top (upper) or the bottom
    (lower) to the back. Points: c + R (sin(lam) X + cos(lam) (cos(phi) d + sin(phi) v))."""
    c, d, x, v = Vector(c), Vector(d).normalized(), Vector(x).normalized(), Vector(v).normalized()
    e = math.radians(edge_deg)
    phis = [e + (math.pi if upper else -math.pi) * i / n_phi for i in range(n_phi + 1)]
    lams = [math.radians(-lam_max + 2 * lam_max * j / n_lam) for j in range(n_lam + 1)]

    def p(R, phi, lam):
        return c + (x * math.sin(lam) + (d * math.cos(phi) + v * math.sin(phi)) * math.cos(lam)) * R

    outer = [[bm.verts.new(p(r_out, ph, la)) for la in lams] for ph in phis]
    inner = [[bm.verts.new(p(r_in, ph, la)) for la in lams] for ph in phis]
    faces = []
    for i in range(n_phi):
        for j in range(n_lam):
            faces.append(bm.faces.new((outer[i][j], outer[i + 1][j], outer[i + 1][j + 1], outer[i][j + 1])))
            faces.append(bm.faces.new((inner[i][j], inner[i][j + 1], inner[i + 1][j + 1], inner[i + 1][j])))
    for j in range(n_lam):        # the visible lid edge and the back edge
        faces.append(bm.faces.new((outer[0][j], outer[0][j + 1], inner[0][j + 1], inner[0][j])))
        faces.append(bm.faces.new((outer[-1][j], inner[-1][j], inner[-1][j + 1], outer[-1][j + 1])))
    for i in range(n_phi):        # side caps near the rotation axis
        faces.append(bm.faces.new((outer[i][0], inner[i][0], inner[i + 1][0], outer[i + 1][0])))
        faces.append(bm.faces.new((outer[i][-1], outer[i + 1][-1], inner[i + 1][-1], inner[i][-1])))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def lid_angles(open_deg, closed_deg):
    """Rotation (radians, about the lid bone's X) that moves a lid edge from open to closed."""
    return math.radians(closed_deg - open_deg)
