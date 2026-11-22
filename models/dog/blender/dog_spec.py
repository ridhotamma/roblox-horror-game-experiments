"""Shared measurements for the Dog: one source of truth for the body shape, the skeleton and the animations.

Units are metres, Z up, ground at z = 0, the dog faces +Y (Blender +Y becomes Roblox -Z, the LookVector, through
the FBX/glTF axis conversion). Left side is +X.

Reference: a medium mixed-breed dog (~20 kg): 0.56 m at the withers, ~0.65 m point of shoulder to point of buttock,
head ~0.22 m long. Exported for Roblox at 4.5 studs per metre (the same scale as ClassicHouse and StylizedTree):
2.5 studs at the withers next to a 5.2-stud R15 avatar.
"""

STUDS_PER_METRE = 4.5

# ------------------------------------------------------------------ skeleton joints (left side; right = mirrored X)
FRONT = {
    "shoulder": (0.085, 0.235, 0.440),
    "elbow": (0.085, 0.185, 0.270),
    "wrist": (0.085, 0.205, 0.075),
    "toe": (0.085, 0.265, 0.022),
}
HIND = {
    "hip": (0.090, -0.250, 0.450),
    "knee": (0.090, -0.150, 0.285),
    "hock": (0.090, -0.310, 0.135),
    "ball": (0.090, -0.285, 0.035),
    "toe": (0.090, -0.235, 0.022),
}

# name: (head, tail, parent, deform)
SPINE = {
    "DogRoot": ((0, 0.00, 0.0), (0, 0.15, 0.0), None, False),
    "Hips": ((0, -0.250, 0.470), (0, -0.050, 0.480), "DogRoot", True),
    "Spine": ((0, -0.050, 0.480), (0, 0.140, 0.490), "Hips", True),
    "Chest": ((0, 0.140, 0.490), (0, 0.265, 0.520), "Spine", True),
    "Neck": ((0, 0.265, 0.520), (0, 0.395, 0.680), "Chest", True),
    "Head": ((0, 0.395, 0.680), (0, 0.610, 0.665), "Neck", True),
    "Tail1": ((0, -0.320, 0.525), (0, -0.425, 0.590), "Hips", True),
    "Tail2": ((0, -0.425, 0.590), (0, -0.530, 0.620), "Tail1", True),
    "Tail3": ((0, -0.530, 0.620), (0, -0.640, 0.615), "Tail2", True),
}


def leg_bones():
    """Front: Upper (humerus), Fore (radius/ulna), Paw. Hind: Thigh, Shin, Foot (metatarsus), Paw (toes)."""
    bones = {}
    for side, sx in (("L", 1), ("R", -1)):
        f = {k: (v[0] * sx, v[1], v[2]) for k, v in FRONT.items()}
        h = {k: (v[0] * sx, v[1], v[2]) for k, v in HIND.items()}
        bones[f"FrontUpper_{side}"] = (f["shoulder"], f["elbow"], "Chest", True)
        bones[f"FrontFore_{side}"] = (f["elbow"], f["wrist"], f"FrontUpper_{side}", True)
        bones[f"FrontPaw_{side}"] = (f["wrist"], f["toe"], f"FrontFore_{side}", True)
        bones[f"HindThigh_{side}"] = (h["hip"], h["knee"], "Hips", True)
        bones[f"HindShin_{side}"] = (h["knee"], h["hock"], f"HindThigh_{side}", True)
        bones[f"HindFoot_{side}"] = (h["hock"], h["ball"], f"HindShin_{side}", True)
        bones[f"HindPaw_{side}"] = (h["ball"], h["toe"], f"HindFoot_{side}", True)
    return bones


def all_bones():
    b = dict(SPINE)
    b.update(leg_bones())
    # ears: head/tail filled in by the builder once the skull surface is known (raycast), parent Head
    return b


# ------------------------------------------------------------------ coat colours (sRGB)
COAT = {
    "cream": (0.93, 0.86, 0.72),
    "tan": (0.80, 0.53, 0.27),
    "dark": (0.23, 0.14, 0.085),
}
# solid swatches in the right half of the palette texture: name -> (index, sRGB)
SWATCHES = {
    "nose": (0, (0.035, 0.03, 0.03)),
    "eye": (1, (0.36, 0.19, 0.07)),         # warm brown iris (the pupil reads against it)
    "shine": (2, (0.97, 0.97, 0.95)),
    "collar": (3, (0.72, 0.09, 0.10)),
    "tag": (4, (0.95, 0.74, 0.25)),
    "ear_inner": (5, (0.80, 0.55, 0.50)),
    "pad": (6, (0.16, 0.13, 0.12)),
    "mouth": (7, (0.30, 0.12, 0.12)),
}
PALETTE_W, PALETTE_H = 256, 8

# ------------------------------------------------------------------ face rig (see models/shared/face_rig.py)
EYE_R = 0.0155
EYE_PROTRUDE = 0.0085
LID_UP_OPEN, LID_UP_CLOSED = 52.0, -16.0       # lid edges, degrees above the gaze line
LID_LOW_OPEN, LID_LOW_CLOSED = -58.0, -14.0
PUPIL_HALF = (0.0042, 0.0042)                  # round pupil radius at rest (pupil = 0.5)
PUPIL_NARROW = (0.50, 0.50)                    # scale at pupil = 0
PUPIL_WIDE = (1.65, 1.65)                      # scale at pupil = 1
FACE_BONES = ("EyeLidUp", "EyeLidLow", "PupilW1", "PupilW2", "PupilH1", "PupilH2")
COAT_U_MAX = 0.49   # the coat ramp lives in u = 0 .. 0.5; 0 = cream, 0.25 = tan, 0.49 = dark


def swatch_u(name):
    i = SWATCHES[name][0]
    return (128 + 16 * i + 8) / PALETTE_W
