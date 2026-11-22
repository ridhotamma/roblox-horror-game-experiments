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
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "shared"))
import face_rig as FR  # noqa: E402

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
    # idle variants: one-shots that start and end standing; DogAnimator plays one now and then while idle
    "IdleLook": {"frames": 105, "loop": False, "speed": 0.0, "idle_variant": True},
    "IdleSniff": {"frames": 120, "loop": False, "speed": 0.0, "idle_variant": True},
    "IdleSit": {"frames": 210, "loop": False, "speed": 0.0, "idle_variant": True},
    "IdleShake": {"frames": 48, "loop": False, "speed": 0.0, "idle_variant": True},
    # face rig showcase for Blender / glTF users (blink, double blink, pupils wide then narrow). Not exported to
    # Roblox: DogAnimator blinks and sets the pupils itself (SetPupil / Blink / SetEyelids)
    "FaceDemo": {"frames": 150, "loop": True, "speed": 0.0, "face_demo": True},
}

# ------------------------------------------------------------------ face rig angles (models/shared/face_rig.py)
LID_CLOSE = {"EyeLidUp": FR.lid_angles(S.LID_UP_OPEN, S.LID_UP_CLOSED),
             "EyeLidLow": FR.lid_angles(S.LID_LOW_OPEN, S.LID_LOW_CLOSED)}


def pupil_angles(size):
    """(W angle, H angle) for pupil size 0 (narrow) .. 0.5 (rest) .. 1 (wide)."""
    if size < 0.5:
        sc = [lerp(n, 1.0, size / 0.5) for n in S.PUPIL_NARROW]
    else:
        sc = [lerp(1.0, w, (size - 0.5) / 0.5) for w in S.PUPIL_WIDE]
    return (FR.pupil_angle(sc[0], S.PUPIL_HALF[0], S.EYE_R), FR.pupil_angle(sc[1], S.PUPIL_HALF[1], S.EYE_R))


def face(p, blink=0.0, pupil=0.5):
    aw, ah = pupil_angles(max(0.0, min(1.0, pupil)))
    b = max(0.0, min(1.0, blink))
    for s in ("L", "R"):
        p.pitch[f"EyeLidUp_{s}"] = LID_CLOSE["EyeLidUp"] * b
        p.pitch[f"EyeLidLow_{s}"] = LID_CLOSE["EyeLidLow"] * b
        p.yaw[f"PupilW1_{s}"], p.yaw[f"PupilW2_{s}"] = aw, -aw
        p.pitch[f"PupilH1_{s}"], p.pitch[f"PupilH2_{s}"] = ah, -ah


def blinks(sec, times, close=0.07, hold=0.03, open_=0.12):
    v = 0.0
    for t0 in times:
        dt = sec - t0
        if 0 <= dt < close:
            v = max(v, ease(dt / close))
        elif close <= dt < close + hold:
            v = 1.0
        elif close + hold <= dt < close + hold + open_:
            v = max(v, 1 - ease((dt - close - hold) / open_))
    return v

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
        self.roll = {}       # bone -> local Y rotation (spine/hip roll, head tilt, body shake)
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
def counter_roll(p):
    """A spine roll tips the legs sideways with it; turn each leg back about its own forward axis (its local Z, which
    is world +Y here) so planted paws stay where they are while the body rocks over them."""
    hips = p.roll.get("Hips", 0.0)
    chest = hips + p.roll.get("Spine", 0.0) + p.roll.get("Chest", 0.0)
    for s in ("L", "R"):
        p.yaw[f"HindThigh_{s}"] = p.yaw.get(f"HindThigh_{s}", 0.0) - hips
        p.yaw[f"FrontUpper_{s}"] = p.yaw.get(f"FrontUpper_{s}", 0.0) - chest


def plant(p, rest):
    for leg in rest:
        p.legs[leg] = dict(rest[leg])


def window(t, a, b, c, d):
    """0 before a, eases to 1 by b, holds, eases back to 0 between c and d."""
    return ease((t - a) / (b - a)) * (1 - ease((t - c) / (d - c)))


def tail_wag(p, t, cycles, amp=(14, 12, 10), lag=0.6, pitch=-6.0):
    for i, (bone, a) in enumerate(zip(("Tail1", "Tail2", "Tail3"), amp)):
        p.yaw[bone] = radians(a) * sin(TAU * cycles * t - lag * i)
    p.pitch["Tail1"] = radians(pitch)


def standing(rest, t, breaths):
    """Neutral stance with breathing; `breaths` is a whole number so a one-shot starts and ends on the same pose."""
    p = Pose()
    breath = sin(TAU * breaths * t)
    p.root = (0.0, -0.006 + 0.003 * breath)
    p.pitch["Spine"] = radians(1.2) * breath
    p.pitch["Chest"] = radians(-0.8) * breath
    plant(p, rest)
    return p


def idle(sk, rest, t):
    """3 s breathing loop: chest rise, weight shift, slow look-around with overlap, tail wag, ear flicks."""
    p = Pose()
    breath = sin(TAU * 2 * t)
    shift = sin(TAU * t)
    p.root = (0.004 * shift, -0.006 + 0.003 * breath)
    p.roll["Hips"] = radians(1.4) * shift                  # weight rocks from one hind leg to the other
    p.roll["Chest"] = radians(-0.6) * sin(TAU * t - 0.5)
    p.pitch["Spine"] = radians(1.2) * breath
    p.pitch["Chest"] = radians(-0.8) * breath
    look = sin(TAU * t) * 0.6 + sin(TAU * 2 * t + 1.0) * 0.4
    look_late = sin(TAU * t - 0.35) * 0.6 + sin(TAU * 2 * t + 0.65) * 0.4   # the head follows the neck
    p.pitch["Neck"] = radians(4) * sin(TAU * t + 2.0)
    p.pitch["Head"] = radians(-3) * sin(TAU * t + 2.0) + radians(4) * bump(t, 0.62, 0.08)   # little nod
    p.yaw["Neck"] = radians(9) * look
    p.yaw["Head"] = radians(7) * look_late
    p.roll["Head"] = radians(3) * look_late
    tail_wag(p, t, 6)
    p.pitch["Ear_L"] = radians(-16) * bump(t, 0.30, 0.035) + radians(2) * breath
    p.pitch["Ear_R"] = radians(-16) * bump(t, 0.78, 0.035) + radians(2) * breath
    p.yaw["Ear_L"] = radians(8) * bump(t, 0.30, 0.04)
    p.yaw["Ear_R"] = radians(-8) * bump(t, 0.78, 0.04)
    plant(p, rest)
    return p


def walk(sk, rest, t):
    p = Pose()
    g = WALK
    bob = cos(TAU * 2 * (t - 0.10))
    p.root = (0.0, -0.014 - 0.007 * bob)
    # weight shift: each hip drops while its own hind leg swings (left hind swing is centred at t ~ 0.81), and the
    # shoulders rock with the front swing (left fore centred at t ~ 0.06); +roll drops the left side
    hips_roll = radians(2.8) * cos(TAU * (t - 0.81))
    chest_roll = radians(2.2) * cos(TAU * (t - 0.06))
    p.roll["Hips"] = hips_roll
    p.roll["Chest"] = chest_roll - hips_roll
    p.yaw["Spine"] = radians(0.8) * sin(TAU * (t - 0.81))   # a little lateral flex toward the loaded side
    p.yaw["Chest"] = radians(-0.6) * sin(TAU * (t - 0.81))
    p.pitch["Hips"] = radians(1.2) * sin(TAU * 2 * t)
    p.pitch["Spine"] = radians(-0.8) * sin(TAU * 2 * t)
    # the head rides steadier than the body and a beat later (overlap)
    p.pitch["Neck"] = radians(-4) + radians(2.5) * sin(TAU * 2 * (t - 0.15))
    p.pitch["Head"] = radians(4) - radians(2.0) * sin(TAU * 2 * (t - 0.20))
    p.yaw["Neck"] = -0.6 * (p.yaw["Spine"] + p.yaw["Chest"])
    p.yaw["Head"] = radians(2.0) * sin(TAU * (t - 0.1))
    p.roll["Head"] = -0.5 * chest_roll
    # ears bounce after the body bob; the tail swings with the hips, each joint later than the last
    ear = radians(-3) + radians(5) * cos(TAU * 2 * (t - 0.10) - 1.4)
    p.pitch["Ear_L"] = ear + radians(2) * sin(TAU * (t - 0.2))
    p.pitch["Ear_R"] = ear - radians(2) * sin(TAU * (t - 0.2))
    tail_wag(p, t - 0.06, 1, amp=(12, 11, 10), lag=0.75, pitch=-10)
    p.pitch["Tail2"] = radians(3) * cos(TAU * 2 * (t - 0.25))
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
    p.yaw["Tail2"] = radians(5) * sin(TAU * t - 0.7)
    p.yaw["Tail3"] = radians(6) * sin(TAU * t - 1.4)
    p.roll["Hips"] = radians(1.8) * sin(TAU * (t - 0.05))
    p.roll["Chest"] = radians(-1.6) * sin(TAU * (t - 0.47)) - p.roll["Hips"]
    # ears trail the bound (pinned back, flapping a beat late); the head counters half the spine pitch so its
    # gaze stays steadier
    p.pitch["Ear_L"] = radians(-34) + radians(9) * sin(TAU * (t - 0.32))
    p.pitch["Ear_R"] = radians(-34) + radians(9) * sin(TAU * (t - 0.36))
    p.yaw["Ear_L"] = radians(5) * sin(TAU * (t - 0.4))
    p.yaw["Ear_R"] = radians(-5) * sin(TAU * (t - 0.4))
    p.pitch["Head"] -= 0.5 * (p.pitch["Hips"] + p.pitch["Spine"] + p.pitch["Chest"])
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


# ------------------------------------------------------------------ idle variants
def idle_look(sk, rest, t):
    """3.5 s: ears prick, look to the right, then to the left with a curious head tilt, settle."""
    p = standing(rest, t, 3)
    alert = window(t, 0.0, 0.08, 0.86, 0.98)
    right = window(t, 0.06, 0.18, 0.40, 0.50)
    left = window(t, 0.46, 0.58, 0.80, 0.93)
    tilt = window(t, 0.58, 0.66, 0.76, 0.86)
    p.yaw["Neck"] = radians(24) * right - radians(20) * left
    p.yaw["Head"] = radians(16) * window(t, 0.09, 0.21, 0.40, 0.52) - radians(13) * window(t, 0.49, 0.61, 0.80, 0.95)
    p.roll["Head"] = radians(20) * tilt - radians(3) * right
    p.pitch["Neck"] = radians(7) * alert
    p.pitch["Head"] = radians(-4) * alert - radians(5) * tilt
    p.roll["Hips"] = radians(1.5) * (left - right)
    p.roll["Chest"] = radians(2.0) * (left - right) - p.roll["Hips"]
    perk = radians(16) * alert
    p.pitch["Ear_L"] = perk - radians(12) * bump(t, 0.34, 0.03)
    p.pitch["Ear_R"] = perk + radians(10) * tilt
    p.yaw["Ear_R"] = radians(-10) * bump(t, 0.70, 0.04)
    tail_wag(p, t, 4, amp=(6, 6, 6), pitch=-6 + 16 * alert)
    return p


def idle_sniff(sk, rest, t):
    """4 s: nose down to the ground, sweep left and right sniffing in short bursts, come back up."""
    p = standing(rest, t, 3)
    down = window(t, 0.04, 0.20, 0.80, 0.95)
    ry, rz = p.root
    p.root = (ry - 0.015 * down, rz - 0.045 * down)
    p.pitch["Chest"] += radians(-9) * down
    p.pitch["Neck"] = radians(-88) * down
    p.pitch["Head"] = radians(30) * down
    sweep = sin(TAU * 1.25 * (t - 0.2))
    p.yaw["Neck"] = radians(12) * sweep * down
    p.yaw["Head"] = radians(9) * sin(TAU * 1.25 * (t - 0.25)) * down
    sniff = bump(t, 0.36, 0.07) + bump(t, 0.52, 0.06) + bump(t, 0.68, 0.06)
    p.pitch["Head"] += radians(2.5) * sin(TAU * 28 * t) * sniff * down
    p.pitch["Ear_L"] = p.pitch["Ear_R"] = radians(10) * down
    p.roll["Hips"] = radians(1.2) * sweep * down
    tail_wag(p, t, 5, amp=(9, 8, 8), pitch=-6 + 8 * down)
    return p


_SIT = {}


def sit_solution(sk, rest):
    """Hips pitch and root offset for a sit: rump down near the hind paws, front legs straight under the shoulders."""
    if _SIT:
        return _SIT
    rump_z = 0.19
    sh = sk.bones["FrontUpper_L"]["head"]
    hips = sk.bones["Hips"]["head"]
    root_z = rump_z - hips[1]

    def shoulder(a, root_y):
        pos, _ = sk.fk({"Hips": a, "Spine": 0.22 * a, "Chest": 0.05 * a}, (root_y, root_z))
        return pos["FrontUpper_L"]

    lo, hi = 0.0, radians(85)
    for _ in range(40):
        a = (lo + hi) / 2
        if shoulder(a, 0.0)[1] < sh[1] - 0.025:
            lo = a
        else:
            hi = a
    a = (lo + hi) / 2
    root_y = (sh[0] - 0.03) - shoulder(a, 0.0)[0]       # shoulders end a little behind where they stood
    _SIT.update({"hips": a, "root": (root_y, root_z)})
    return _SIT


def sit_pose(sk, rest, p, k):
    """Blend a standing pose toward the sit by k (0..1); the hind paws tuck forward, the hocks lie on the ground."""
    sol = sit_solution(sk, rest)
    a = sol["hips"] * k
    ry, rz = p.root
    p.root = (ry + sol["root"][0] * k, rz + sol["root"][1] * k)
    p.pitch["Hips"] = p.pitch.get("Hips", 0.0) + a
    p.pitch["Spine"] = p.pitch.get("Spine", 0.0) + 0.22 * a
    p.pitch["Chest"] = p.pitch.get("Chest", 0.0) + 0.05 * a
    body = a * 1.27
    p.pitch["Neck"] = p.pitch.get("Neck", 0.0) - 0.45 * body
    p.pitch["Head"] = p.pitch.get("Head", 0.0) - 0.55 * body
    for s in ("L", "R"):
        r = rest["H" + s]
        y0, z0 = r["target"]
        p.legs["H" + s] = {"target": (y0 + (sol["root"][0] - 0.05) * k, z0), "paw": r["paw"],
                           "foot": lerp(r["foot"], radians(-8), k)}
    return p


def idle_sit(sk, rest, t):
    """7 s: sit down, look around with the tail sweeping the floor, stand back up."""
    p = standing(rest, t, 5)
    k = window(t, 0.02, 0.17, 0.83, 0.97)
    sit_pose(sk, rest, p, k)
    hold = window(t, 0.15, 0.25, 0.75, 0.85)
    look = sin(TAU * 1.0 * (t - 0.25))
    p.yaw["Neck"] = radians(16) * look * hold
    p.yaw["Head"] = radians(10) * sin(TAU * 1.0 * (t - 0.29)) * hold
    p.roll["Head"] = radians(8) * bump(t, 0.55, 0.07)
    p.pitch["Ear_L"] = radians(6) * hold - radians(14) * bump(t, 0.42, 0.03)
    p.pitch["Ear_R"] = radians(6) * hold
    # the tail lies on the floor and sweeps it
    p.pitch["Tail1"] = radians(-6) - radians(32) * k
    for i, bone in enumerate(("Tail1", "Tail2", "Tail3")):
        p.yaw[bone] = radians(16 + 4 * i) * sin(TAU * 7 * t - 0.6 * i) * (0.4 + 0.6 * hold)
    p.pitch["Tail2"] = radians(-8) * k
    return p


def idle_shake(sk, rest, t):
    """1.6 s wet-dog shake: a fast roll wave from the head to the tail, ears flapping, paws planted."""
    p = standing(rest, t, 1)
    env = window(t, 0.04, 0.18, 0.70, 0.95)
    w = TAU * 7.5 * t
    ry, rz = p.root
    p.root = (ry, rz - 0.02 * env)
    rolls = (("Head", 26, 0.0), ("Neck", 18, 0.5), ("Chest", 12, 1.0), ("Spine", 9, 1.5), ("Hips", 6, 2.0))
    world = {name: radians(a) * sin(w - ph) * env for name, a, ph in rolls}
    p.roll["Hips"] = world["Hips"]
    p.roll["Spine"] = world["Spine"] - world["Hips"]
    p.roll["Chest"] = world["Chest"] - world["Spine"]
    p.roll["Neck"] = world["Neck"] - world["Chest"]
    p.roll["Head"] = world["Head"] - world["Neck"]
    p.pitch["Neck"] = radians(-10) * env
    p.pitch["Head"] = radians(6) * env
    for s, sgn in (("L", 1), ("R", -1)):
        p.yaw[f"Ear_{s}"] = radians(28) * sin(w - 0.9) * env * sgn
        p.pitch[f"Ear_{s}"] = radians(-14) * env + radians(12) * sin(w - 1.2) * env * sgn
    for i, bone in enumerate(("Tail1", "Tail2", "Tail3")):
        p.yaw[bone] = radians(22) * sin(w - 2.4 - 0.5 * i) * env
    p.pitch["Tail1"] = radians(-6)
    return p


def face_demo(sk, rest, t):
    """5 s: blink, double blink, pupils wide, pupils narrow, a slow blink, back to rest."""
    p = standing(rest, t, 2)
    sec = t * CLIPS["FaceDemo"]["frames"] / FPS
    lids = max(blinks(sec, (0.4, 1.2, 1.45)), blinks(sec, (4.0,), close=0.3, hold=0.3, open_=0.4))
    size = 0.5 + 0.5 * window(t, 0.36, 0.46, 0.52, 0.60) - 0.5 * window(t, 0.58, 0.68, 0.72, 0.80)
    face(p, lids, size)
    plant(p, rest)
    return p


CLIP_FUNCS = {"Idle": idle, "Walk": walk, "Run": run, "Jump": jump, "IdleLook": idle_look,
              "IdleSniff": idle_sniff, "IdleSit": idle_sit, "IdleShake": idle_shake, "FaceDemo": face_demo}


# ------------------------------------------------------------------ baking to keys
def apply_pose(rig, alpha, yaw, root, roll=None):
    roll = roll or {}
    for pb in rig.pose.bones:
        pb.rotation_mode = "QUATERNION"
        q = Quaternion((1, 0, 0), alpha.get(pb.name, 0.0))
        if pb.name in roll:
            q = Quaternion((0, 1, 0), roll[pb.name]) @ q
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
            counter_roll(pose)
            alpha = solve(sk, pose)
            apply_pose(rig, alpha, pose.yaw, pose.root, pose.roll)
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
        side = 0.0
        rest_x = {paw: (rig.matrix_world @ rig.data.bones[paw].tail_local).x for paw in
                  ("FrontPaw_L", "FrontPaw_R", "HindPaw_L", "HindPaw_R")}
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
                if p.z < 0.03:
                    side = max(side, abs(p.x - rest_x[paw]))
                prev[paw] = p
        out[name] = {"lowest_paw_tip": round(lowest, 4), "max_slide_per_frame_m": round(slide, 4),
                     "max_sideways_m": round(side, 4)}
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
