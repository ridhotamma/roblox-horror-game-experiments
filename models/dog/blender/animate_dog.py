"""Animates the Dog: Idle, Walk, Run (gallop) and Jump, baked to plain FK keys on DogRig (one action each).

How it works: every clip is a function of time that says where the body is (root offset, spine/neck/head pitch,
tail and ear swing) and where each paw is (planted on the ground in stance, an arc in swing). Leg angles come from an
analytic two-bone IK solved in the side (YZ) plane - elbows bend back, stifles bend forward - so planted paws stay
planted. All rolls make local X = world X (rig_dog.py), so a leg or spine pitch is one local X rotation and the angles
add up along the chain.

  blender -b models/dog/blender/Dog_rig.blend --python models/dog/blender/animate_dog.py -- [--preview]
"""
import os
import sys
import json
import math
import bpy
from math import sin, cos, pi, atan2, acos, radians
from mathutils import Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dog_spec as S  # noqa: E402

FPS = 30
OUT = os.path.join(os.path.dirname(HERE), "out")
TAU = 2 * pi

# clip settings (also exported for the Roblox animator; speeds in metres per second of root travel)
CLIPS = {
    "Idle": {"frames": 90, "loop": True, "speed": 0.0},
    "Walk": {"frames": 24, "loop": True, "speed": None},   # filled in from the stride below
    "Run": {"frames": 16, "loop": True, "speed": None},
    "Jump": {"frames": 36, "loop": False, "speed": 0.0,
             # frame markers for the Roblox animator: crouch+takeoff, the airborne part (held while falling), landing
             "markers": {"takeoff": [0, 13], "air": [13, 23], "land": [23, 36]}},
}

WALK = {"stance": 0.50, "duty": 0.62, "lift_f": 0.055, "lift_h": 0.05,
        "phase": {"HL": 0.00, "FL": 0.25, "HR": 0.50, "FR": 0.75}}
RUN = {"stance": 0.56, "duty": 0.32, "lift_f": 0.11, "lift_h": 0.09,
       "phase": {"HL": 0.00, "HR": 0.10, "FR": 0.42, "FL": 0.52}}
CLIPS["Walk"]["speed"] = WALK["stance"] / (WALK["duty"] * CLIPS["Walk"]["frames"] / FPS)
CLIPS["Run"]["speed"] = RUN["stance"] / (RUN["duty"] * CLIPS["Run"]["frames"] / FPS)


# ------------------------------------------------------------------ rest skeleton in the side plane
class Skeleton:
    def __init__(self, rig):
        self.rig = rig
        self.bones = {}
        for b in rig.data.bones:
            h, t = b.head_local, b.tail_local
            self.bones[b.name] = {
                "parent": b.parent.name if b.parent else None,
                "head": (h.y, h.z),
                "len": (t - h).length,
                "theta": atan2(t.z - h.z, t.y - h.y),
            }
        self.order = [b.name for b in rig.data.bones]   # parents come before children

    def fk(self, alpha, root_off):
        """alpha: local pitch per bone (radians). Returns world head (y, z) and cumulative pitch per bone."""
        pos, cum = {}, {}
        for n in self.order:
            b = self.bones[n]
            p = b["parent"]
            a = alpha.get(n, 0.0)
            if p is None:
                pos[n] = (b["head"][0] + root_off[0], b["head"][1] + root_off[1])
                cum[n] = a
                continue
            c = cum[p]
            dy = b["head"][0] - self.bones[p]["head"][0]
            dz = b["head"][1] - self.bones[p]["head"][1]
            pos[n] = (pos[p][0] + dy * cos(c) - dz * sin(c), pos[p][1] + dy * sin(c) + dz * cos(c))
            cum[n] = c + a
        return pos, cum


def two_bone(a, t, l1, l2, bend):
    """Angles (world, in the YZ plane) of a two-bone chain from a reaching t. bend=+1 puts the joint on the +angle
    side of the a->t line (hind stifle, forward), -1 on the other (front elbow, backward)."""
    dy, dz = t[0] - a[0], t[1] - a[1]
    d = math.hypot(dy, dz)
    d = max(abs(l1 - l2) + 1e-4, min(l1 + l2 - 1e-4, d))
    base = atan2(dz, dy)
    off = acos(max(-1, min(1, (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d))))
    th1 = base + bend * off
    j = (a[0] + l1 * cos(th1), a[1] + l1 * sin(th1))
    th2 = atan2(t[1] - j[1], t[0] - j[0])
    return th1, th2


def ease(x):
    x = max(0.0, min(1.0, x))
    return 0.5 - 0.5 * cos(pi * x)


def bump(x, c, w):
    """Smooth 0..1..0 bump centred on c with half-width w (periodic on [0,1))."""
    d = (x - c + 0.5) % 1.0 - 0.5
    return 0.5 + 0.5 * cos(pi * d / w) if abs(d) < w else 0.0


def lerp(a, b, t):
    return a + (b - a) * t


# ------------------------------------------------------------------ one frame of a pose
class Pose:
    """Everything a frame needs: root offset (y, z), extra pitch per bone, paw targets, yaw/roll extras."""

    def __init__(self):
        self.root = (0.0, 0.0)
        self.pitch = {}      # bone -> local X rotation (body chain, neck, head, tail, ears)
        self.yaw = {}        # bone -> local Z rotation (tail wag, head turn, ear flick)
        self.legs = {}       # "FL"/"FR"/"HL"/"HR" -> dict(target=(y, z), paw=angle, foot=angle (hind))


def leg_rest(sk):
    """Rest toe / ball points and paw angles, per leg (side-plane)."""
    r = {}
    for side in ("L", "R"):
        fp = sk.bones[f"FrontPaw_{side}"]
        r["F" + side] = {"target": (fp["head"][0] + fp["len"] * cos(fp["theta"]),
                                    fp["head"][1] + fp["len"] * sin(fp["theta"])),
                         "paw": fp["theta"]}
        hp = sk.bones[f"HindPaw_{side}"]
        hf = sk.bones[f"HindFoot_{side}"]
        r["H" + side] = {"target": hp["head"], "paw": hp["theta"], "foot": hf["theta"]}
    return r


UP_IS_NEGATIVE = ("Tail1", "Tail2", "Tail3", "Ear_L", "Ear_R")


def solve(sk, pose):
    """Pose -> local rotations {bone: (pitch, yaw)} and root location."""
    alpha = dict(pose.pitch)
    # tail and ear bones point backward / up, so a positive local X rotation lowers the tail and folds the ears
    # back; clips write them as "positive = tail up / ears forward"
    for n in UP_IS_NEGATIVE:
        if n in alpha:
            alpha[n] = -alpha[n]
    pos, cum = sk.fk(alpha, pose.root)
    for leg, spec in pose.legs.items():
        side = leg[1]
        if leg[0] == "F":
            up, fo, pw = f"FrontUpper_{side}", f"FrontFore_{side}", f"FrontPaw_{side}"
            parent_cum = cum["Chest"]
            lp = sk.bones[pw]["len"]
            tgt = spec["target"]
            wrist = (tgt[0] - lp * cos(spec["paw"]), tgt[1] - lp * sin(spec["paw"]))
            th1, th2 = two_bone(pos[up], wrist, sk.bones[up]["len"], sk.bones[fo]["len"], -1)
            a_up = th1 - sk.bones[up]["theta"] - parent_cum
            a_fo = th2 - sk.bones[fo]["theta"] - (parent_cum + a_up)
            a_pw = spec["paw"] - sk.bones[pw]["theta"] - (parent_cum + a_up + a_fo)
            alpha.update({up: a_up, fo: a_fo, pw: a_pw})
        else:
            th_, sh, ft, pw = f"HindThigh_{side}", f"HindShin_{side}", f"HindFoot_{side}", f"HindPaw_{side}"
            parent_cum = cum["Hips"]
            lf = sk.bones[ft]["len"]
            ball = spec["target"]
            hock = (ball[0] - lf * cos(spec["foot"]), ball[1] - lf * sin(spec["foot"]))
            t1, t2 = two_bone(pos[th_], hock, sk.bones[th_]["len"], sk.bones[sh]["len"], +1)
            a_th = t1 - sk.bones[th_]["theta"] - parent_cum
            a_sh = t2 - sk.bones[sh]["theta"] - (parent_cum + a_th)
            a_ft = spec["foot"] - sk.bones[ft]["theta"] - (parent_cum + a_th + a_sh)
            a_pw = spec["paw"] - sk.bones[pw]["theta"] - (parent_cum + a_th + a_sh + a_ft)
            alpha.update({th_: a_th, sh: a_sh, ft: a_ft, pw: a_pw})
    return alpha


# ------------------------------------------------------------------ gait helper
def gait_leg(rest, leg, ph, g, front_fold, hind_fold, reach=0.0):
    """Paw target for one leg at its own phase ph in [0,1): stance moves the planted paw backward at body speed,
    swing brings it forward on an arc. Returns the leg spec dict."""
    duty, stride = g["duty"], g["stance"]
    r = rest[leg]
    y0, z0 = r["target"]
    if ph < duty:                                  # stance: planted, sliding back under the body
        s = ph / duty
        y = y0 + stride * (0.5 - s)
        z = z0
        late = max(0.0, (s - 0.70) / 0.30)          # heel lifts at the end of stance
        if leg[0] == "F":
            paw = r["paw"] - radians(32) * ease(late)
            return {"target": (y, z + 0.004 * late), "paw": paw}
        paw = r["paw"] - radians(30) * ease(late)
        foot = r["foot"] - radians(14) * ease(late)
        return {"target": (y, z + 0.018 * ease(late)), "paw": paw, "foot": foot}
    s = (ph - duty) / (1 - duty)                    # swing: forward arc
    y = y0 + stride * (ease(s) - 0.5) + reach * sin(pi * s)
    lift = g["lift_f"] if leg[0] == "F" else g["lift_h"]
    z = z0 + lift * sin(pi * s) ** 0.8
    if leg[0] == "F":
        # carpus folds the paw back early in swing, then the paw reaches forward to land
        fold = sin(pi * min(1, s / 0.75)) if s < 0.75 else 0.0
        paw = r["paw"] - front_fold * fold + radians(16) * bump(s, 0.86, 0.14)
        return {"target": (y, z), "paw": paw}
    fold = sin(pi * min(1, s / 0.8)) if s < 0.8 else 0.0
    paw = r["paw"] - radians(40) * fold
    foot = r["foot"] - hind_fold * fold
    return {"target": (y, z + 0.02 * fold), "paw": paw, "foot": foot}


# ------------------------------------------------------------------ clips
def idle(sk, rest, t):
    """3 s breathing loop: chest rise, slow look-around, tail wag, ear flicks, feet planted."""
    p = Pose()
    breath = sin(TAU * 2 * t)
    p.root = (0.004 * sin(TAU * t), -0.006 + 0.003 * breath)
    p.pitch["Spine"] = radians(1.2) * breath
    p.pitch["Chest"] = radians(-0.8) * breath
    look = sin(TAU * t) * 0.6 + sin(TAU * 2 * t + 1.0) * 0.4
    p.pitch["Neck"] = radians(4) * sin(TAU * t + 2.0)
    p.pitch["Head"] = radians(-3) * sin(TAU * t + 2.0) + radians(4) * bump(t, 0.62, 0.08)   # little nod
    p.yaw["Neck"] = radians(9) * look
    p.yaw["Head"] = radians(7) * look
    wag = sin(TAU * 6 * t)
    p.yaw["Tail1"] = radians(14) * wag
    p.yaw["Tail2"] = radians(12) * sin(TAU * 6 * t - 0.6)
    p.yaw["Tail3"] = radians(10) * sin(TAU * 6 * t - 1.2)
    p.pitch["Tail1"] = radians(-6)
    p.pitch["Ear_L"] = radians(-16) * bump(t, 0.30, 0.035)
    p.pitch["Ear_R"] = radians(-16) * bump(t, 0.78, 0.035)
    p.yaw["Ear_L"] = radians(8) * bump(t, 0.30, 0.04)
    p.yaw["Ear_R"] = radians(-8) * bump(t, 0.78, 0.04)
    for leg in rest:
        p.legs[leg] = dict(rest[leg])
    return p


def walk(sk, rest, t):
    p = Pose()
    g = WALK
    p.root = (0.0, -0.014 - 0.007 * cos(TAU * 2 * (t - 0.10)))
    p.pitch["Hips"] = radians(1.2) * sin(TAU * 2 * t)
    p.pitch["Spine"] = radians(-0.8) * sin(TAU * 2 * t)
    p.pitch["Neck"] = radians(-4) + radians(2.5) * sin(TAU * 2 * (t - 0.15))
    p.pitch["Head"] = radians(4) - radians(2.5) * sin(TAU * 2 * (t - 0.15))
    p.yaw["Head"] = radians(2.5) * sin(TAU * t)
    p.pitch["Tail1"] = radians(-10)
    p.yaw["Tail1"] = radians(11) * sin(TAU * t)
    p.yaw["Tail2"] = radians(9) * sin(TAU * t - 0.7)
    p.yaw["Tail3"] = radians(8) * sin(TAU * t - 1.4)
    p.pitch["Ear_L"] = p.pitch["Ear_R"] = radians(-4) * sin(TAU * 2 * t)
    for leg, off in g["phase"].items():
        p.legs[leg] = gait_leg(rest, leg, (t - off) % 1.0, g, radians(95), radians(22))
    return p


def run(sk, rest, t):
    """Rotary gallop: hinds land (LH, RH), spine flexes, fronts land (RF, LF), spine extends, suspension."""
    p = Pose()
    g = RUN
    flex = cos(TAU * (t - 0.95))            # +1 gathered (back rounded), -1 stretched
    load = 0.0
    for leg, off in g["phase"].items():
        ph = (t - off) % 1.0
        if ph < g["duty"]:
            load += sin(pi * ph / g["duty"])
    p.root = (0.0, -0.035 + 0.045 * (0.5 - min(1.0, load / 1.6)))
    p.pitch["Hips"] = radians(6) * flex + radians(5) * sin(TAU * (t - 0.20))
    p.pitch["Spine"] = radians(-8) * flex
    p.pitch["Chest"] = radians(3) * flex
    p.pitch["Neck"] = radians(-16) + radians(6) * sin(TAU * (t - 0.30))
    p.pitch["Head"] = radians(12) - radians(6) * sin(TAU * (t - 0.30))
    p.pitch["Tail1"] = radians(-22) + radians(8) * sin(TAU * (t - 0.1))
    p.pitch["Tail2"] = radians(-6) + radians(8) * sin(TAU * (t - 0.25))
    p.pitch["Tail3"] = radians(6) * sin(TAU * (t - 0.4))
    p.yaw["Tail1"] = radians(4) * sin(TAU * t)
    p.pitch["Ear_L"] = p.pitch["Ear_R"] = radians(-34) + radians(6) * sin(TAU * (t - 0.2))
    for leg, off in g["phase"].items():
        p.legs[leg] = gait_leg(rest, leg, (t - off) % 1.0, g, radians(120), radians(40),
                               reach=0.05 if leg[0] == "F" else 0.02)
    return p


def jump(sk, rest, t):
    """Frames: 0-9 crouch, 9-13 push off, 13-23 airborne (rise to apex ~17, fall), 23-28 land, 28-36 recover."""
    f = t * CLIPS["Jump"]["frames"]
    p = Pose()

    def seg(a, b):
        return ease((f - a) / (b - a))

    crouch = seg(0, 9) * (1 - seg(9, 13))
    air = seg(11, 15) * (1 - seg(21, 24))
    land = seg(22.5, 26) * (1 - seg(27, 35))
    # root: down in the crouch, a ballistic arc in the air, a dip on landing (Roblox strips the lift, see export)
    arc = 0.0
    if 12 <= f <= 24:
        k = (f - 12) / 12
        arc = 0.34 * 4 * k * (1 - k)
    p.root = (0.02 * air, -0.085 * crouch + arc - 0.07 * land + 0.03 * seg(10, 13) * (1 - seg(13, 16)))
    # body pitch: nose up leaving the ground, level at the apex, nose down falling, settle on landing
    pitch = radians(-5) * crouch + radians(10) * seg(10, 14) * (1 - seg(15, 19)) - radians(14) * seg(18, 22) \
        * (1 - seg(23, 28))
    p.pitch["Hips"] = pitch
    p.pitch["Spine"] = radians(-7) * crouch + radians(5) * air
    p.pitch["Neck"] = radians(-10) * crouch + radians(-6) * air + radians(-8) * land
    p.pitch["Head"] = radians(8) * crouch + radians(-4) * air + radians(10) * land
    p.pitch["Tail1"] = radians(-8) - radians(18) * air + radians(10) * land
    p.pitch["Tail2"] = radians(-10) * air
    p.pitch["Ear_L"] = p.pitch["Ear_R"] = radians(-10) * crouch - radians(38) * air + radians(10) * land

    # legs: planted until they push off; tucked/reaching in the air; fronts touch down before hinds
    for leg in rest:
        r = rest[leg]
        y0, z0 = r["target"]
        if leg[0] == "F":
            leave, touch = 10.5, 22.5
        else:
            leave, touch = 13.0, 24.5
        if f < leave or f >= touch:
            spec = dict(r)
            if leg[0] == "F" and f < leave:
                spec["paw"] = r["paw"] - radians(30) * seg(8, leave)
            if leg[0] == "H" and f < leave:
                spec["paw"] = r["paw"] - radians(28) * seg(10, leave)
                spec["foot"] = r["foot"] - radians(20) * seg(10, leave)
                spec["target"] = (y0, z0 + 0.03 * seg(11, leave))
            p.legs[leg] = spec
            continue
        k = (f - leave) / (touch - leave)
        ry, rz = p.root
        if leg[0] == "F":
            # tuck under the chest, then reach forward and down for the landing
            tuck = sin(pi * min(1, k / 0.7))
            ty = y0 + ry + 0.06 * tuck + 0.10 * ease((k - 0.45) / 0.55)
            tz = z0 + rz + 0.16 * tuck - 0.03 * ease((k - 0.6) / 0.4)
            paw = r["paw"] - radians(110) * tuck + radians(20) * ease((k - 0.6) / 0.4)
            p.legs[leg] = {"target": (ty, max(z0, tz) if k > 0.85 else tz), "paw": paw}
        else:
            # trail back extended after push-off, then gather under the body
            trail = sin(pi * min(1, k / 0.5)) if k < 0.5 else 0.0
            gather = ease((k - 0.35) / 0.65)
            ty = y0 + ry - 0.16 * trail + 0.06 * gather
            tz = z0 + rz + 0.06 * trail + 0.10 * sin(pi * gather) * (1 - gather * 0.5)
            p.legs[leg] = {"target": (ty, tz), "paw": r["paw"] - radians(40) * trail,
                           "foot": r["foot"] - radians(10) * trail - radians(20) * sin(pi * gather)}
    return p


CLIP_FUNCS = {"Idle": idle, "Walk": walk, "Run": run, "Jump": jump}


# ------------------------------------------------------------------ baking to keys
def apply_pose(rig, alpha, yaw, root):
    for pb in rig.pose.bones:
        pb.rotation_mode = "QUATERNION"
        q = Quaternion((1, 0, 0), alpha.get(pb.name, 0.0))
        if pb.name in yaw:
            q = Quaternion((0, 0, 1), yaw[pb.name]) @ q
        pb.rotation_quaternion = q
        pb.location = (0, 0, 0)
    # DogRoot.s local axes are the world axes (it points +Y with roll making X = +X), so its location is world-space
    rig.pose.bones["DogRoot"].location = (0.0, root[0], root[1])


def bake(rig):
    sk = Skeleton(rig)
    rest = leg_rest(sk)
    rig.animation_data_create()
    report = {}
    for name, cfg in CLIPS.items():
        act = bpy.data.actions.get(name) or bpy.data.actions.new(name)
        act.use_fake_user = True
        rig.animation_data.action = act
        n = cfg["frames"]
        last = n if cfg["loop"] else n          # loops repeat frame 0 at frame n so Blender cycles seamlessly
        worst_ground = 0.0
        for fr in range(0, last + 1):
            t = (fr % n) / n if cfg["loop"] else fr / n
            pose = CLIP_FUNCS[name](sk, rest, t)
            alpha = solve(sk, pose)
            apply_pose(rig, alpha, pose.yaw, pose.root)
            for pb in rig.pose.bones:
                pb.keyframe_insert("rotation_quaternion", frame=fr, group=pb.name)
            rig.pose.bones["DogRoot"].keyframe_insert("location", frame=fr, group="DogRoot")
            # paws below the ground?
            for leg, spec in pose.legs.items():
                worst_ground = min(worst_ground, spec["target"][1])
        act.use_frame_range = True
        act.frame_range = (0, last)
        act["fps"] = FPS
        act["loop"] = cfg["loop"]
        report[name] = {"frames": n, "speed_mps": round(cfg.get("speed") or 0.0, 3),
                        "lowest_target": round(worst_ground, 4)}
    # leave the rig in rest with no active action; each action becomes a (muted) NLA strip for the exporters
    rig.animation_data.action = None
    for tr in list(rig.animation_data.nla_tracks):
        rig.animation_data.nla_tracks.remove(tr)
    for name in CLIPS:
        tr = rig.animation_data.nla_tracks.new()
        tr.name = name
        act = bpy.data.actions[name]
        st = tr.strips.new(name, 0, act)
        st.action_frame_start, st.action_frame_end = act.frame_range
        tr.mute = True
    for pb in rig.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    return report


# ------------------------------------------------------------------ checks: paw contact and mesh sanity
def paw_world(rig, name):
    pb = rig.pose.bones[name]
    return rig.matrix_world @ pb.tail


def contact_check(rig):
    """Measured in Blender's evaluated pose (not the planner): how far planted paws slide, the lowest paw tip."""
    sc = bpy.context.scene
    out = {}
    for name, cfg in CLIPS.items():
        rig.animation_data.action = bpy.data.actions[name]
        n = cfg["frames"]
        lowest = 9
        slide = 0.0
        prev = {}
        speed = cfg.get("speed") or 0.0
        for fr in range(n + 1):
            sc.frame_set(fr)
            for paw in ("FrontPaw_L", "FrontPaw_R", "HindPaw_L", "HindPaw_R"):
                p = paw_world(rig, paw)
                lowest = min(lowest, p.z)
                if paw in prev and p.z < 0.03 and prev[paw].z < 0.03:
                    # a planted paw should move back at exactly the clip speed (the root is in place)
                    dy = (p.y - prev[paw].y) + speed / FPS
                    slide = max(slide, abs(dy))
                prev[paw] = p
        out[name] = {"lowest_paw_tip": round(lowest, 4), "max_slide_per_frame_m": round(slide, 4)}
    rig.animation_data.action = None
    return out


def contact_sheet(rig, frames_per_clip=6):
    """Side-view strips of each clip, stacked into out/anim-<Clip>.png (uses build_dog's preview stage)."""
    import numpy as np
    import build_dog as B
    sc = bpy.context.scene
    if "Preview" not in bpy.data.collections:
        B.setup_preview(sc)
    cam = sc.camera
    paths = {}
    for name, cfg in CLIPS.items():
        rig.animation_data.action = bpy.data.actions[name]
        n = cfg["frames"]
        frames = [round(i * n / frames_per_clip) for i in range(frames_per_clip)]
        if name == "Jump":
            frames = [0, 9, 13, 17, 21, 25]
        tiles = []
        for fr in frames:
            sc.frame_set(fr)
            for view, loc in (("side", (2.3, 0.0, 0.55)), ("3q", (1.5, 1.6, 0.85))):
                cam.location = loc
                tgt = Vector((0, -0.02, 0.45))
                cam.rotation_euler = (tgt - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
                cam.data.type = "ORTHO" if view == "side" else "PERSP"
                cam.data.ortho_scale = 1.7
                cam.data.lens = 45
                sc.render.resolution_x, sc.render.resolution_y = 360, 300
                tmp = os.path.join(OUT, f"_tile_{view}.png")
                sc.render.filepath = tmp
                bpy.ops.render.render(write_still=True)
                img = bpy.data.images.load(tmp, check_existing=False)
                a = np.array(img.pixels[:], dtype=np.float32).reshape(img.size[1], img.size[0], 4)
                bpy.data.images.remove(img)
                os.remove(tmp)
                tiles.append((view, a))
        side = np.concatenate([a for v, a in tiles if v == "side"], axis=1)
        tq = np.concatenate([a for v, a in tiles if v == "3q"], axis=1)
        sheet = np.concatenate([side, tq], axis=0)   # rows are bottom-up in Blender images: 3q row ends on top
        h, w = sheet.shape[:2]
        im = bpy.data.images.new(f"sheet_{name}", w, h, alpha=True)
        im.pixels = sheet.ravel()
        p = os.path.join(OUT, f"anim-{name}.png")
        im.filepath_raw = p
        im.file_format = "PNG"
        im.save()
        paths[name] = p
    rig.animation_data.action = None
    return paths


def main():
    rig = bpy.data.objects["DogRig"]
    sc = bpy.context.scene
    sc.render.fps = FPS
    report = {"bake": bake(rig)}
    report["contact"] = contact_check(rig)
    sc.frame_set(0)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "Dog.blend"))
    if "--preview" in sys.argv:
        report["sheets"] = contact_sheet(rig)
        rig.animation_data.action = None
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "Dog.blend"))
    report["speeds_mps"] = {k: round(v.get("speed") or 0, 3) for k, v in CLIPS.items()}
    print("RESULT", json.dumps(report))


if __name__ == "__main__":
    main()
