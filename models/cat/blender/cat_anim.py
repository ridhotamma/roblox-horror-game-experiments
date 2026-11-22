"""Cat clips: planted-paw locomotion and idles, baked to per-frame quaternion keys on CatRig.

Same approach as the dog (models/dog/blender/animate_dog.py): every clip is a function of time that says where the
body is (root offset, spine / neck / head pitch, yaw and roll, tail and ears) and where each paw is (planted in
stance, an arc in swing). Leg angles come from an analytic two-bone IK in the side (YZ) plane, so planted paws
stay planted instead of sliding, and the hind knee bends forward like a cat's. Spine rolls are cancelled on the
legs so the body can rock over planted paws.

Rig conventions (16_rig_anim_v3.py): the cat faces -Y; every spine, leg and tail bone has local X = world +X, so a
pitch is one local X rotation and the angles add up along a chain. Because the cat faces -Y the signs are mirrored
from the dog, so clips use the named helpers below (nose_up, tail_up, ears_fwd, turn_left, drop_left).

Clips (24 fps)
  Idle         4.0 s loop   breathing, weight shift, look-around with overlap, tail S-sway, ear flicks
  Walk         0.83 s loop  lateral-sequence walk, level head, shoulder-blade roll, hip drop, tail sway
  Run          0.58 s loop  rotary gallop with spine flex and suspension
  Jump         1.5 s        crouch, push-off, tuck, reach, land, recover (vertical motion on Root)
  IdleLook     4.0 s        ears swivel to a sound, head turn and tilt, tail-tip twitch
  IdleStretch  5.0 s        walks the front paws out, chest down / rump up stretch, steps back
  IdleSit      8.0 s        sits down, tail curls round the paws, looks about, stands up
  IdleGroom    7.0 s        sits, licks a front paw, wipes the face twice, stands up
Walk and Run are in place: a controller moving the cat at CLIPS[...]["speed"] m/s keeps the planted paws still.
"""
import json
import math
from math import sin, cos, pi, atan2, acos, radians
from mathutils import Quaternion, Vector

FPS = 24
TAU = 2 * pi

WALK = {"stance": 0.15, "duty": 0.62, "lift_f": 0.034, "lift_h": 0.030,
        "phase": {"HL": 0.00, "FL": 0.25, "HR": 0.50, "FR": 0.75}}
RUN = {"stance": 0.22, "duty": 0.34, "lift_f": 0.070, "lift_h": 0.060,
       "phase": {"HL": 0.00, "HR": 0.08, "FR": 0.42, "FL": 0.50}}

CLIPS = {
    "Idle": {"frames": 96, "loop": True},
    "Walk": {"frames": 20, "loop": True},
    "Run": {"frames": 14, "loop": True},
    "Jump": {"frames": 36, "loop": False},
    "IdleLook": {"frames": 96, "loop": False, "idle_variant": True},
    "IdleStretch": {"frames": 120, "loop": False, "idle_variant": True},
    "IdleSit": {"frames": 192, "loop": False, "idle_variant": True},
    "IdleGroom": {"frames": 168, "loop": False, "idle_variant": True},
}
CLIPS["Walk"]["speed"] = WALK["stance"] / (WALK["duty"] * CLIPS["Walk"]["frames"] / FPS)
CLIPS["Run"]["speed"] = RUN["stance"] / (RUN["duty"] * CLIPS["Run"]["frames"] / FPS)

LEGS = ("FL", "FR", "HL", "HR")
SPINE = ("Hips", "Spine1", "Spine2", "Chest")


# ------------------------------------------------------------------ semantic sign helpers (cat faces -Y)
def nose_up(deg):          # spine / neck / head pitch
    return -radians(deg)


def tail_up(deg):
    return radians(deg)


def ears_fwd(deg):         # ear bones have local X = -X
    return -radians(deg)


def turn_left(deg):        # spine / neck / head yaw
    return -radians(deg)


def drop_left(deg):        # roll about the spine's forward axis
    return -radians(deg)


def ease(x):
    x = max(0.0, min(1.0, x))
    return 0.5 - 0.5 * cos(pi * x)


def bump(x, c, w):
    d = (x - c + 0.5) % 1.0 - 0.5
    return 0.5 + 0.5 * cos(pi * d / w) if abs(d) < w else 0.0


def window(t, a, b, c, d):
    """0 before a, eases to 1 by b, holds, eases back to 0 between c and d."""
    return ease((t - a) / (b - a)) * (1 - ease((t - c) / (d - c)))


def lerp(a, b, t):
    return a + (b - a) * t


# ------------------------------------------------------------------ side-plane skeleton
class Skeleton:
    def __init__(self, rig):
        self.bones = {}
        for b in rig.data.bones:
            h, t = b.head_local, b.tail_local
            self.bones[b.name] = {"parent": b.parent.name if b.parent else None, "head": (h.y, h.z),
                                  "len": (t - h).length, "theta": atan2(t.z - h.z, t.y - h.y),
                                  "tail": (t.y, t.z)}
        self.order = [b.name for b in rig.data.bones]
        # sign that turns a spine roll into the leg rotation that cancels it (spine local Y vs leg local Z)
        hy = rig.data.bones["Hips"].matrix_local.to_3x3().col[1]
        lz = rig.data.bones["Thigh.L"].matrix_local.to_3x3().col[2]
        self.counter = -1.0 if hy.dot(lz) > 0 else 1.0

    def fk(self, alpha, root_off):
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

    def tip(self, name, pos, cum):
        b = self.bones[name]
        ang = b["theta"] + cum[name]
        return (pos[name][0] + b["len"] * cos(ang), pos[name][1] + b["len"] * sin(ang))


def two_bone(a, t, l1, l2, bend):
    dy, dz = t[0] - a[0], t[1] - a[1]
    d = math.hypot(dy, dz)
    d = max(abs(l1 - l2) + 1e-4, min(l1 + l2 - 1e-4, d))
    base = atan2(dz, dy)
    off = acos(max(-1, min(1, (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d))))
    th1 = base + bend * off
    j = (a[0] + l1 * cos(th1), a[1] + l1 * sin(th1))
    return th1, atan2(t[1] - j[1], t[0] - j[0])


class Pose:
    def __init__(self):
        self.root = (0.0, 0.0, 0.0)   # (side, forward, up) metres; forward is -Y
        self.pitch, self.yaw, self.roll = {}, {}, {}
        self.legs = {}                 # leg -> {"target": (y, z) toe tip, "angle": paw/foot angle}

    def root_yz(self):
        return (-self.root[1], self.root[2])


def leg_rest(sk):
    r = {}
    for s in ("L", "R"):
        fp, hf = sk.bones[f"Paw.{s}"], sk.bones[f"Foot.{s}"]
        r["F" + s] = {"target": fp["tail"], "angle": fp["theta"]}
        r["H" + s] = {"target": hf["tail"], "angle": hf["theta"]}
    return r


def solve(sk, p):
    alpha = dict(p.pitch)
    pos, cum = sk.fk(alpha, p.root_yz())
    for leg, spec in p.legs.items():
        s = leg[1]
        tgt, ang = spec["target"], spec["angle"]
        if leg[0] == "F":
            up, fo, end = f"UpperArm.{s}", f"Forearm.{s}", f"Paw.{s}"
            parent, bend = cum["Chest"], +1        # elbow points back
        else:
            up, fo, end = f"Thigh.{s}", f"Shin.{s}", f"Foot.{s}"
            parent, bend = cum["Hips"], -1         # knee points forward
        le = sk.bones[end]["len"]
        joint = (tgt[0] - le * cos(ang), tgt[1] - le * sin(ang))
        th1, th2 = two_bone(pos[up], joint, sk.bones[up]["len"], sk.bones[fo]["len"], bend)
        a1 = th1 - sk.bones[up]["theta"] - parent
        a2 = th2 - sk.bones[fo]["theta"] - (parent + a1)
        a3 = ang - sk.bones[end]["theta"] - (parent + a1 + a2)
        alpha.update({up: a1, fo: a2, end: a3})
    return alpha


def counter_roll(sk, p):
    hips = p.roll.get("Hips", 0.0)
    chest = sum(p.roll.get(n, 0.0) for n in SPINE)
    for s in ("L", "R"):
        p.yaw[f"Thigh.{s}"] = p.yaw.get(f"Thigh.{s}", 0.0) + sk.counter * hips
        p.yaw[f"UpperArm.{s}"] = p.yaw.get(f"UpperArm.{s}", 0.0) + sk.counter * chest


# ------------------------------------------------------------------ shared pieces
def plant(p, rest):
    for leg in LEGS:
        p.legs[leg] = dict(rest[leg])


def standing(rest, t, breaths):
    """Neutral stance with breathing; a whole number of breaths so one-shots start and end on the same pose."""
    p = Pose()
    b = sin(TAU * breaths * t)
    p.root = (0.0, 0.0, 0.0015 * b)
    p.pitch["Spine2"] = nose_up(0.8) * b
    p.pitch["Chest"] = nose_up(-0.6) * b
    plant(p, rest)
    return p


def tail_sway(p, t, cycles, amp=(4, 6, 8, 10), lag=0.55, lift=(0, 0, 0, 0)):
    for i, (bone, a) in enumerate(zip(("Tail1", "Tail2", "Tail3", "Tail4"), amp)):
        p.yaw[bone] = radians(a) * sin(TAU * cycles * t - lag * i)
        p.pitch[bone] = p.pitch.get(bone, 0.0) + tail_up(lift[i])


def gait_leg(rest, leg, ph, g, front_fold, hind_fold, reach=0.0):
    """Toe target for one leg at its own phase: stance slides the planted paw back (+Y) at body speed, swing
    brings it forward (-Y) on an arc, folding the wrist / hock on the way."""
    duty, stride = g["duty"], g["stance"]
    r = rest[leg]
    y0, z0 = r["target"]
    if ph < duty:
        s = ph / duty
        late = ease(max(0.0, (s - 0.70) / 0.30))     # heel lifts at the end of stance
        y = y0 + stride * (s - 0.5)
        if leg[0] == "F":
            return {"target": (y, z0 + 0.003 * late), "angle": r["angle"] + radians(30) * late}
        return {"target": (y, z0 + 0.004 * late), "angle": r["angle"] + radians(18) * late}
    s = (ph - duty) / (1 - duty)
    y = y0 + stride * (0.5 - ease(s)) - reach * sin(pi * s)
    lift = g["lift_f"] if leg[0] == "F" else g["lift_h"]
    z = z0 + lift * sin(pi * s) ** 0.8
    if leg[0] == "F":
        fold = sin(pi * min(1, s / 0.75)) if s < 0.75 else 0.0
        return {"target": (y, z), "angle": r["angle"] + front_fold * fold - radians(14) * bump(s, 0.86, 0.14)}
    fold = sin(pi * min(1, s / 0.8)) if s < 0.8 else 0.0
    return {"target": (y, z + 0.012 * fold), "angle": r["angle"] + hind_fold * fold}


# ------------------------------------------------------------------ locomotion
def idle(sk, rest, t):
    p = Pose()
    b = sin(TAU * 2 * t)
    shift = sin(TAU * t)
    p.root = (0.0, 0.002 * shift, 0.0015 * b)
    p.roll["Hips"] = drop_left(1.2) * shift
    p.roll["Chest"] = drop_left(-0.5) * sin(TAU * t - 0.6)
    p.pitch["Spine2"] = nose_up(0.8) * b
    p.pitch["Chest"] = nose_up(-0.6) * b
    look = 0.65 * sin(TAU * t + 0.3) + 0.35 * sin(TAU * 2 * t + 1.2)
    late = 0.65 * sin(TAU * t - 0.1) + 0.35 * sin(TAU * 2 * t + 0.7)
    p.yaw["Neck"] = turn_left(8) * look
    p.yaw["Head"] = turn_left(9) * late
    p.roll["Head"] = drop_left(5) * bump(t, 0.58, 0.10)
    p.pitch["Neck"] = nose_up(2) * sin(TAU * t + 1.8)
    p.pitch["Head"] = nose_up(-2) * sin(TAU * t + 1.8) + nose_up(-3) * bump(t, 0.80, 0.06)
    tail_sway(p, t, 1, amp=(4, 6, 9, 13), lag=0.7)
    p.pitch["Tail4"] += tail_up(10) * sin(TAU * 2 * t - 1.0)        # the tip curls and uncurls
    p.pitch["Ear.L"] = ears_fwd(-22) * bump(t, 0.27, 0.025)        # quick flicks
    p.pitch["Ear.R"] = ears_fwd(-22) * bump(t, 0.71, 0.025)
    p.yaw["Ear.L"] = radians(14) * bump(t, 0.27, 0.03)
    p.yaw["Ear.R"] = radians(-14) * bump(t, 0.71, 0.03)
    plant(p, rest)
    return p


def walk(sk, rest, t):
    p = Pose()
    g = WALK
    bob = cos(TAU * 2 * (t - 0.08))
    p.root = (0.0, 0.0, -0.004 - 0.003 * bob)
    # each hip drops while its own hind leg swings (HL swing centred t ~ 0.81); the shoulder blades roll with the
    # front swing (FL centred t ~ 0.06)
    hips = drop_left(3.0) * cos(TAU * (t - 0.81))
    chest = drop_left(3.6) * cos(TAU * (t - 0.06))
    p.roll["Hips"] = hips
    p.roll["Chest"] = chest - hips
    p.yaw["Spine1"] = turn_left(1.0) * sin(TAU * (t - 0.81))
    p.pitch["Hips"] = nose_up(-0.8) * sin(TAU * 2 * t)
    p.pitch["Spine2"] = nose_up(0.6) * sin(TAU * 2 * t)
    # cats keep the head very level: neck and head cancel most of the bob and roll, a beat late
    p.pitch["Neck"] = nose_up(-2) + nose_up(1.5) * sin(TAU * 2 * (t - 0.18))
    p.pitch["Head"] = nose_up(1) - nose_up(1.2) * sin(TAU * 2 * (t - 0.22))
    p.roll["Neck"] = -0.5 * chest
    p.roll["Head"] = -0.4 * chest
    p.yaw["Head"] = turn_left(1.5) * sin(TAU * (t - 0.1))
    tail_sway(p, t - 0.05, 1, amp=(3, 5, 7, 9), lag=0.7, lift=(6, 2, 0, 0))
    p.pitch["Tail4"] += tail_up(6) * sin(TAU * 2 * (t - 0.3))
    ear = ears_fwd(3) + ears_fwd(-3) * cos(TAU * 2 * (t - 0.08) - 1.4)
    p.pitch["Ear.L"] = p.pitch["Ear.R"] = ear
    for leg, off in g["phase"].items():
        p.legs[leg] = gait_leg(rest, leg, (t - off) % 1.0, g, radians(95), radians(30))
    return p


def run(sk, rest, t):
    p = Pose()
    g = RUN
    flex = cos(TAU * (t - 0.95))            # +1 gathered (back rounded), -1 stretched out
    load = 0.0
    for leg, off in g["phase"].items():
        ph = (t - off) % 1.0
        if ph < g["duty"]:
            load += sin(pi * ph / g["duty"])
    p.root = (0.0, 0.0, -0.016 + 0.024 * (0.5 - min(1.0, load / 1.6)))
    p.pitch["Hips"] = nose_up(7) * flex + nose_up(4) * sin(TAU * (t - 0.2))
    p.pitch["Spine1"] = nose_up(-7) * flex
    p.pitch["Spine2"] = nose_up(-4) * flex
    p.pitch["Chest"] = nose_up(3) * flex
    p.pitch["Neck"] = nose_up(-10) + nose_up(5) * sin(TAU * (t - 0.30))
    p.pitch["Head"] = nose_up(8) - nose_up(5) * sin(TAU * (t - 0.30))
    p.pitch["Head"] -= 0.5 * sum(p.pitch[n] for n in ("Hips", "Spine1", "Spine2", "Chest"))
    p.roll["Hips"] = drop_left(1.5) * sin(TAU * (t - 0.05))
    p.roll["Chest"] = drop_left(-1.5) * sin(TAU * (t - 0.47)) - p.roll["Hips"]
    tail_sway(p, t - 0.05, 1, amp=(3, 4, 5, 6), lag=0.6, lift=(-30, -6, 4, 4))
    for i, bone in enumerate(("Tail1", "Tail2", "Tail3", "Tail4")):
        p.pitch[bone] += tail_up(7) * sin(TAU * (t - 0.15 - 0.08 * i))
    p.pitch["Ear.L"] = ears_fwd(-26) + ears_fwd(6) * sin(TAU * (t - 0.32))
    p.pitch["Ear.R"] = ears_fwd(-26) + ears_fwd(6) * sin(TAU * (t - 0.36))
    for leg, off in g["phase"].items():
        p.legs[leg] = gait_leg(rest, leg, (t - off) % 1.0, g, radians(120), radians(45),
                               reach=0.03 if leg[0] == "F" else 0.012)
    return p


def jump(sk, rest, t):
    """Frames (24 fps): 0-9 crouch, 9-13 push off, 13-23 airborne (apex ~17), 23-28 land, 28-36 recover."""
    f = t * CLIPS["Jump"]["frames"]
    p = Pose()

    def seg(a, b):
        return ease((f - a) / (b - a))

    crouch = seg(0, 9) * (1 - seg(9, 13))
    air = seg(11, 15) * (1 - seg(21, 24))
    land = seg(22.5, 26) * (1 - seg(27, 35))
    arc = 0.0
    if 12 <= f <= 24:
        k = (f - 12) / 12
        arc = 0.20 * 4 * k * (1 - k)
    p.root = (0.0, 0.012 * air, -0.05 * crouch + arc - 0.04 * land + 0.018 * seg(10, 13) * (1 - seg(13, 16)))
    pitch = nose_up(-5) * crouch + nose_up(12) * seg(10, 14) * (1 - seg(15, 19)) \
        - nose_up(14) * seg(18, 22) * (1 - seg(23, 28))
    p.pitch["Hips"] = pitch
    p.pitch["Spine1"] = nose_up(-6) * crouch + nose_up(4) * air
    p.pitch["Neck"] = nose_up(-8) * crouch + nose_up(-4) * air + nose_up(-6) * land
    p.pitch["Head"] = nose_up(8) * crouch + nose_up(-3) * air + nose_up(8) * land
    for i, bone in enumerate(("Tail1", "Tail2", "Tail3", "Tail4")):
        p.pitch[bone] = tail_up(-10) * crouch + tail_up(-14 + 4 * i) * air + tail_up(10) * land
    p.pitch["Ear.L"] = p.pitch["Ear.R"] = ears_fwd(-8) * crouch + ears_fwd(-26) * air + ears_fwd(6) * land
    for leg in LEGS:
        r = rest[leg]
        y0, z0 = r["target"]
        leave, touch = (10.5, 22.5) if leg[0] == "F" else (13.0, 24.5)
        if f < leave or f >= touch:
            spec = dict(r)
            if f < leave:
                spec["angle"] = r["angle"] + radians(28) * seg(9, leave)
                if leg[0] == "H":
                    spec["target"] = (y0, z0 + 0.012 * seg(11, leave))
            p.legs[leg] = spec
            continue
        k = (f - leave) / (touch - leave)
        ry, rz = p.root_yz()
        if leg[0] == "F":
            tuck = sin(pi * min(1, k / 0.7))
            ty = y0 + ry - 0.035 * tuck - 0.06 * ease((k - 0.45) / 0.55)
            tz = z0 + rz + 0.09 * tuck - 0.015 * ease((k - 0.6) / 0.4)
            ang = r["angle"] + radians(100) * tuck - radians(18) * ease((k - 0.6) / 0.4)
            p.legs[leg] = {"target": (ty, max(z0, tz) if k > 0.85 else tz), "angle": ang}
        else:
            trail = sin(pi * min(1, k / 0.5)) if k < 0.5 else 0.0
            gather = ease((k - 0.35) / 0.65)
            ty = y0 + ry + 0.09 * trail - 0.035 * gather
            tz = z0 + rz + 0.035 * trail + 0.055 * sin(pi * gather) * (1 - gather * 0.5)
            p.legs[leg] = {"target": (ty, tz), "angle": r["angle"] + radians(40) * trail + radians(25) * sin(pi * gather)}
    return p


# ------------------------------------------------------------------ idle variants
def idle_look(sk, rest, t):
    """4 s: an ear swivels toward a sound, the head turns and tilts to it, the tail tip twitches, settle."""
    p = standing(rest, t, 2)
    ear_swivel = window(t, 0.04, 0.09, 0.80, 0.90)
    look = window(t, 0.10, 0.24, 0.66, 0.86)
    tilt = window(t, 0.30, 0.40, 0.56, 0.66)
    p.yaw["Ear.R"] = radians(-30) * ear_swivel
    p.yaw["Ear.L"] = radians(-18) * window(t, 0.12, 0.18, 0.80, 0.90)
    p.pitch["Ear.L"] = p.pitch["Ear.R"] = ears_fwd(8) * look
    p.yaw["Neck"] = turn_left(-22) * look
    p.yaw["Head"] = turn_left(-18) * window(t, 0.13, 0.27, 0.68, 0.88)
    p.roll["Head"] = drop_left(-16) * tilt
    p.pitch["Neck"] = nose_up(6) * look
    p.pitch["Head"] = nose_up(-4) * look + nose_up(-4) * tilt
    p.roll["Hips"] = drop_left(-1.5) * look
    p.roll["Chest"] = drop_left(-1.5) * look
    twitch = sum(bump(t, c, 0.03) for c in (0.30, 0.36, 0.52))
    tail_sway(p, t, 1, amp=(2, 3, 5, 8), lag=0.7)
    p.yaw["Tail4"] += radians(22) * twitch
    p.pitch["Tail4"] += tail_up(12) * twitch
    return p


def idle_stretch(sk, rest, t):
    """5 s: step the front paws out one at a time, sink the chest with the rump high, hold, rise, step back."""
    p = standing(rest, t, 2)
    reach = 0.075
    out_l = ease((t - 0.04) / 0.10)
    out_r = ease((t - 0.12) / 0.10)
    back_l = ease((t - 0.80) / 0.09)
    back_r = ease((t - 0.88) / 0.09)
    sink = window(t, 0.20, 0.36, 0.62, 0.78)
    for s, out, back in (("L", out_l, back_l), ("R", out_r, back_r)):
        r = rest["F" + s]
        y0, z0 = r["target"]
        k = out * (1 - back)
        lift = 0.03 * (sin(pi * min(1, max(0, (t - (0.04 if s == "L" else 0.12)) / 0.10)))
                       + sin(pi * min(1, max(0, (t - (0.80 if s == "L" else 0.88)) / 0.09))))
        p.legs["F" + s] = {"target": (y0 - reach * k, z0 + lift),
                           "angle": r["angle"] - radians(6) * sink - radians(20) * lift / 0.03}
    # the spine pivots at the hips: the chest goes down, the rump stays up
    p.pitch["Hips"] = nose_up(-14) * sink
    p.pitch["Spine1"] = nose_up(-5) * sink
    p.pitch["Spine2"] = p.pitch.get("Spine2", 0.0) + nose_up(-3) * sink
    p.pitch["Chest"] = p.pitch.get("Chest", 0.0) + nose_up(4) * sink
    p.root = (0.0, -0.012 * sink, p.root[2] - 0.022 * sink)
    p.pitch["Neck"] = nose_up(18) * sink
    p.pitch["Head"] = nose_up(10) * sink + nose_up(-4) * bump(t, 0.5, 0.06)   # a slow blink-like nod at the hold
    p.pitch["Ear.L"] = p.pitch["Ear.R"] = ears_fwd(-16) * sink
    tail_sway(p, t, 1, amp=(2, 3, 4, 6), lag=0.7, lift=(22 * sink, 6 * sink, -6 * sink, -10 * sink))
    # a little tremble at full stretch
    p.pitch["Spine1"] += nose_up(0.6) * sin(TAU * 18 * t) * window(t, 0.38, 0.42, 0.56, 0.60)
    return p


_SIT = {}


def sit_solution(sk, rest):
    """Hips pitch and root shift for a cat sit: haunches on the floor, front legs straight under the shoulders."""
    if _SIT:
        return _SIT
    rump_z = 0.100
    hips = sk.bones["Hips"]["head"]
    root_z = rump_z - hips[1]
    sh = sk.bones["UpperArm.L"]["head"]

    def shoulder(a, ry):
        alpha = {"Hips": a, "Spine1": 0.18 * a, "Spine2": 0.10 * a}
        pos, _ = sk.fk(alpha, (ry, root_z))
        return pos["UpperArm.L"]

    lo, hi = 0.0, radians(80)
    for _ in range(40):
        m = (lo + hi) / 2
        if shoulder(-m, 0.0)[1] < sh[1] + 0.005:
            lo = m
        else:
            hi = m
    a = -(lo + hi) / 2                                    # nose up
    ry = (sh[0] + 0.012) - shoulder(a, 0.0)[0]            # shoulders end just behind where they stood
    _SIT.update({"hips": a, "root_yz": (ry, root_z)})
    return _SIT


def sit_pose(sk, rest, p, k):
    sol = sit_solution(sk, rest)
    a = sol["hips"] * k
    ry, rz = sol["root_yz"]
    side, fwd, up = p.root
    p.root = (side, fwd - ry * k, up + rz * k)
    p.pitch["Hips"] = p.pitch.get("Hips", 0.0) + a
    p.pitch["Spine1"] = p.pitch.get("Spine1", 0.0) + 0.18 * a
    p.pitch["Spine2"] = p.pitch.get("Spine2", 0.0) + 0.10 * a
    body = a * 1.28
    p.pitch["Neck"] = p.pitch.get("Neck", 0.0) - 0.55 * body
    p.pitch["Head"] = p.pitch.get("Head", 0.0) - 0.45 * body
    for s in ("L", "R"):
        r = rest["H" + s]
        y0, z0 = r["target"]
        # the hind paws tuck forward under the body; the foot lies flat with the hock on the floor
        p.legs["H" + s] = {"target": (y0 + (ry - 0.020) * k, z0), "angle": lerp(r["angle"], radians(-148), k)}
    return sol


def tail_curl(sk, p, k, side=1):
    """Tail down onto the floor and wrapped round the paws (side=1: round the left). The pitches are solved from
    world angles (after the hip tilt of the sit), so the tail lies along the floor instead of going through it."""
    cum = p.pitch.get("Hips", 0.0)
    for bone, world, wrap in (("Tail1", -24, 4), ("Tail2", -8, 26), ("Tail3", -2, 36), ("Tail4", 4, 40)):
        flat = radians(world) - sk.bones[bone]["theta"] - cum
        a = lerp(p.pitch.get(bone, 0.0), flat, k)
        p.pitch[bone] = a
        cum += a
        p.yaw[bone] = lerp(p.yaw.get(bone, 0.0), radians(wrap) * side, k)


def idle_sit(sk, rest, t):
    """8 s: sit down, curl the tail round the paws, look about with an ear twitch, stand up."""
    p = standing(rest, t, 4)
    k = window(t, 0.02, 0.15, 0.86, 0.98)
    sit_pose(sk, rest, p, k)
    hold = window(t, 0.14, 0.22, 0.78, 0.86)
    look = sin(TAU * (t - 0.22))
    p.yaw["Neck"] = turn_left(16) * look * hold
    p.yaw["Head"] = turn_left(12) * sin(TAU * (t - 0.26)) * hold
    p.pitch["Head"] += nose_up(-6) * bump(t, 0.62, 0.05)        # slow "blink" nod
    p.pitch["Ear.L"] = ears_fwd(-20) * bump(t, 0.40, 0.025)
    p.yaw["Ear.R"] = radians(-20) * window(t, 0.46, 0.50, 0.58, 0.62)
    tail_curl(sk, p, window(t, 0.08, 0.22, 0.80, 0.92))
    p.yaw["Tail4"] += radians(14) * sin(TAU * 3 * t) * hold     # the tip keeps flicking
    return p


def idle_groom(sk, rest, t):
    """7 s: sit, lift a front paw to the mouth and lick it, wipe it over the face twice, put it down, stand."""
    p = standing(rest, t, 3)
    k = window(t, 0.02, 0.14, 0.88, 0.98)
    sit_pose(sk, rest, p, k)
    raise_ = window(t, 0.16, 0.24, 0.76, 0.84)
    lick = window(t, 0.24, 0.28, 0.46, 0.50)
    wipe = window(t, 0.50, 0.54, 0.70, 0.74)
    # head comes down and turns toward the right paw
    p.pitch["Neck"] += nose_up(-22) * raise_
    p.pitch["Head"] += nose_up(-14) * raise_ + nose_up(4) * sin(TAU * 14 * t) * lick
    p.yaw["Neck"] = turn_left(-12) * raise_
    p.yaw["Head"] = turn_left(-10) * raise_
    p.roll["Head"] = drop_left(-10) * raise_ + drop_left(-14) * wipe * (0.5 + 0.5 * sin(TAU * 2 * (t - 0.50) / 0.20))
    p.pitch["Ear.L"] = p.pitch["Ear.R"] = ears_fwd(-10) * raise_
    tail_curl(sk, p, window(t, 0.08, 0.20, 0.84, 0.94), side=-1)
    # where the mouth is, from the pose so far
    pos, cum = sk.fk(p.pitch, p.root_yz())
    nose = sk.tip("Head", pos, cum)
    r = rest["FR"]
    y0, z0 = r["target"]
    mouth = (nose[0] + 0.035, nose[1] - 0.020)
    brow = (nose[0] + 0.065, nose[1] + 0.040)
    # the paw goes up to the mouth, licks, then wipes from the mouth up over the brow twice
    sweep = 0.5 - 0.5 * cos(TAU * 2 * max(0.0, (t - 0.52)) / 0.20) if 0.52 <= t <= 0.72 else 0.0
    ty = lerp(mouth[0], brow[0], sweep * wipe)
    tz = lerp(mouth[1], brow[1], sweep * wipe)
    p.legs["FR"] = {"target": (lerp(y0, ty, raise_), lerp(z0, tz, raise_)),
                    "angle": r["angle"] + radians(55) * raise_}
    p.roll["Chest"] = drop_left(3) * raise_                     # weight onto the left fore
    return p


CLIP_FUNCS = {"Idle": idle, "Walk": walk, "Run": run, "Jump": jump, "IdleLook": idle_look,
              "IdleStretch": idle_stretch, "IdleSit": idle_sit, "IdleGroom": idle_groom}


# ------------------------------------------------------------------ baking
def apply_pose(rig, alpha, p):
    for pb in rig.pose.bones:
        pb.rotation_mode = "QUATERNION"
        q = Quaternion((1, 0, 0), alpha.get(pb.name, 0.0))
        if pb.name in p.roll:
            q = Quaternion((0, 1, 0), p.roll[pb.name]) @ q
        if pb.name in p.yaw:
            q = Quaternion((0, 0, 1), p.yaw[pb.name]) @ q
        pb.rotation_quaternion = q
        pb.location = (0, 0, 0)
    side, fwd, up = p.root
    rig.pose.bones["Root"].location = (side, -fwd, up)    # Root's local axes are the world axes


def bake(rig, scene):
    """Bake every clip to its own action (frames 1..N+1 for loops, 1..N+1 for one-shots) and NLA-stash it."""
    sk = Skeleton(rig)
    rest = leg_rest(sk)
    rig.animation_data_create()
    for tr in list(rig.animation_data.nla_tracks):
        rig.animation_data.nla_tracks.remove(tr)
    acts = {}
    for name, cfg in CLIPS.items():
        old = bpy_actions().get(name)
        if old:
            bpy_actions().remove(old)
        act = bpy_actions().new(name)
        act.use_fake_user = True
        rig.animation_data.action = act
        n = cfg["frames"]
        for fr in range(n + 1):
            t = (fr % n) / n if cfg["loop"] else fr / n
            p = CLIP_FUNCS[name](sk, rest, t)
            counter_roll(sk, p)
            alpha = solve(sk, p)
            apply_pose(rig, alpha, p)
            for pb in rig.pose.bones:
                pb.keyframe_insert("rotation_quaternion", frame=fr + 1, group=pb.name)
            rig.pose.bones["Root"].keyframe_insert("location", frame=fr + 1, group="Root")
        act.use_frame_range = True
        act.frame_range = (1, n + 1)
        act["fps"] = FPS
        act["loop"] = cfg["loop"]
        acts[name] = act
    rig.animation_data.action = None
    for pb in rig.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    return acts


def bpy_actions():
    import bpy
    return bpy.data.actions


def ground_clamp(rig, cat, scene, act, frames):
    """Safety pass for clips with big body motion (Jump): lift Root on any frame where the mesh dips below z=0."""
    import bpy
    dg = bpy.context.evaluated_depsgraph_get()
    rig.animation_data.action = act
    root = rig.pose.bones["Root"]
    fixed = 0
    for fr in range(1, frames + 2):
        scene.frame_set(fr)
        ob = cat.evaluated_get(dg)
        me = ob.to_mesh()
        z = min(v.co.z for v in me.vertices)
        ob.to_mesh_clear()
        if z < -0.001:
            root.location.z -= z
            root.keyframe_insert("location", frame=fr, group="Root")
            fixed += 1
    rig.animation_data.action = None
    return fixed


def contact_report(rig, cat, scene, acts):
    """Lowest mesh point per clip, and how far planted paws drift (in place clips: relative to clip speed)."""
    dg = scene.view_layers[0].depsgraph if hasattr(scene, "view_layers") else None
    import bpy
    dg = bpy.context.evaluated_depsgraph_get()
    out = {}
    for name, act in acts.items():
        rig.animation_data.action = act
        n = CLIPS[name]["frames"]
        speed = CLIPS[name].get("speed", 0.0)
        lows, slide, prev = [], 0.0, {}
        for fr in range(1, n + 2):
            scene.frame_set(fr)
            ob = cat.evaluated_get(dg)
            me = ob.to_mesh()
            lows.append(min(v.co.z for v in me.vertices))
            ob.to_mesh_clear()
            for paw in ("Paw.L", "Paw.R", "Foot.L", "Foot.R"):
                tip = rig.matrix_world @ rig.pose.bones[paw].tail
                if paw in prev and tip.z < 0.02 and prev[paw].z < 0.02:
                    d = Vector((tip.x - prev[paw].x, tip.y - prev[paw].y - speed / FPS, 0)).length
                    slide = max(slide, d)
                prev[paw] = tip
        out[name] = {"lowest": round(min(lows), 4), "highest_low": round(max(lows), 4),
                     "max_paw_slip_per_frame": round(slide, 4)}
    rig.animation_data.action = None
    return out
