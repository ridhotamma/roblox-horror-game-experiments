"""Cat anatomy measured from the references in ../refs (see refs/sources.txt).

Units are metres. The cat faces -Y, +X is the cat's left side, +Z is up.
Landmarks follow the skeleton photo (cat_skeleton.jpg) and the standing photos:

* deep ribcage whose floor sits at elbow height, narrow waist, tucked belly
* top line: shoulder blades, slight dip behind them, gentle arch over the loins,
  croup sloping into the tail
* neck rises ~40 degrees from the withers; the head is carried above the back
* front leg: shoulder joint ahead of the elbow, slender near-vertical forearm
* hind leg: femur runs DOWN and FORWARD to the knee, tibia runs down and BACK to
  a high hock (heel), the metatarsus drops near-vertical to the paw
* paws ~5 cm long, round; tail keeps its thickness to a rounded tip
* head: wide cheeks, short muzzle with two whisker pads, large forward-facing
  eyes set about one eye-width apart, big wide-based ears on the top corners
"""

SHOULDER_TOP = 0.318      # withers height
FRONT_X = 0.046           # half track width of the front legs
HIND_X = 0.049            # half track width of the hind legs

# -------------------------------------------------------------- torso (centre, half-size xyz)
TORSO = [
    ((0.0, -0.085, 0.240), (0.058, 0.095, 0.078)),   # ribcage barrel
    ((0.0, -0.150, 0.247), (0.050, 0.055, 0.068)),   # chest front / shoulders
    ((0.0, 0.035, 0.256), (0.050, 0.085, 0.060)),    # waist / loin
    ((0.0, 0.070, 0.214), (0.040, 0.050, 0.028)),    # soft belly
    ((0.0, 0.140, 0.252), (0.055, 0.066, 0.062)),    # haunch / pelvis
]
WITHERS = [((0.026, -0.118, 0.288), (0.022, 0.045, 0.028)),
           ((-0.026, -0.118, 0.288), (0.022, 0.045, 0.028))]
NECK = ((0.0, -0.150, 0.272), (0.0, -0.228, 0.338), 0.045)
THROAT = ((0.0, -0.205, 0.272), (0.040, 0.036, 0.050))

# -------------------------------------------------------------- head
CRANIUM = ((0.0, -0.258, 0.368), (0.056, 0.056, 0.048))
CHEEKS = ((0.0, -0.278, 0.338), (0.067, 0.048, 0.038))
WHISKER_PADS = [((0.014, -0.316, 0.331), (0.020, 0.020, 0.016)),
                ((-0.014, -0.316, 0.331), (0.020, 0.020, 0.016))]
CHIN = ((0.0, -0.305, 0.313), (0.016, 0.018, 0.011))
NOSE_BRIDGE = ((0.0, -0.290, 0.374), (0.0, -0.327, 0.351), 0.016)

EYE_CENTRE = (0.027, -0.300, 0.362)   # +x side; mirrored for the right eye
EYE_RADIUS = 0.0150
EYE_YAW = 20.0                        # degrees outward from straight ahead
EYE_PITCH = 4.0                       # degrees up
EYE_PROTRUDE = 0.0048                 # how far the eyeball's front stands out of the fur

# face rig: eyelids are hemispherical shells round the eyeball that rotate about its centre;
# the pupil is a curved disc driven by four bones (two widen it, two make it taller)
LID_UP_OPEN = 41.0                    # upper lid edge, degrees above the gaze line
LID_LOW_OPEN = -46.0
LID_UP_CLOSED = -24.0                 # where the edges meet when the eye is shut
LID_LOW_CLOSED = -22.0
PUPIL_HALF = (0.0028, 0.0085)         # rest half width / half height of the slit (pupil = 0.5)
PUPIL_NARROW = (0.35, 0.94)           # scale at pupil = 0 (bright light: thin slit)
PUPIL_WIDE = (2.35, 1.10)             # scale at pupil = 1 (dark / excited: nearly round)
EAR_BASE = (0.036, -0.252, 0.404)     # +x side; the base is pushed onto the skull
EAR_SIZE = (0.025, 0.012, 0.058)      # half width, depth, height
EAR_TILT = 18.0                       # outward lean
EAR_YAW = 22.0                        # opening turned outward
EAR_PITCH = -8.0                      # lean back

# -------------------------------------------------------------- legs (+x side, mirrored)
FRONT = {
    "shoulder": (FRONT_X, -0.140, 0.218),
    "elbow": (FRONT_X, -0.104, 0.146),
    "wrist": (FRONT_X - 0.002, -0.118, 0.040),
    "toe": (FRONT_X - 0.002, -0.150, 0.014),
    "paw": ((FRONT_X - 0.002, -0.130, 0.0155), (0.0175, 0.023, 0.0155)),
    "scapula": ((FRONT_X - 0.006, -0.130, 0.248), (0.016, 0.036, 0.046)),
}
HIND = {
    "hip": (HIND_X, 0.150, 0.236),
    "knee": (HIND_X + 0.001, 0.104, 0.150),
    "hock": (HIND_X + 0.001, 0.172, 0.072),
    "toe": (HIND_X, 0.124, 0.014),
    "paw": ((HIND_X, 0.140, 0.0155), (0.0165, 0.024, 0.0155)),
    "thigh": ((HIND_X - 0.005, 0.132, 0.212), (0.021, 0.048, 0.056)),
    "calf": ((HIND_X + 0.001, 0.146, 0.112), (0.012, 0.016, 0.028)),
}

# limb thickness (capsule radii, m). Slimmer than v3.0 (which was ~25% too thick next to the
# references) while keeping the same taper: upper leg > forearm/shin > wrist/metatarsus.
FRONT_R = {"upper": 0.0185, "fore_top": 0.0150, "fore_low": 0.0125, "wrist": 0.0118}
HIND_R = {"femur": 0.0200, "hamstring": 0.0160, "shin_top": 0.0145, "shin_low": 0.0105, "hock": 0.0085,
          "meta": 0.0102}

# -------------------------------------------------------------- tail (rest pose: low then curling up)
TAIL = [(0.0, 0.200, 0.265), (0.0, 0.268, 0.266), (0.0, 0.324, 0.292),
        (0.0, 0.361, 0.348), (0.0, 0.375, 0.420)]
TAIL_R = [0.021, 0.018, 0.016, 0.015]

# white-mask shapes on the head (scaled with the head below)
MUZZLE_MASK = ((0.0, -0.318, 0.328), (0.036, 0.040, 0.030))
BLAZE = (-0.285, 0.394, 0.55)          # front of y, top z, widening per metre down
THROAT_MASK = ((0.0, -0.300, 0.312), (0.0, -0.205, 0.215))

# -------------------------------------------------------------- head scale
# The references put the head width at ~0.45 x shoulder height; the game cat
# gets a slightly larger head (stylised, reads better at Roblox camera distance).
HEAD_PIVOT = (0.0, -0.215, 0.330)
HEAD_SCALE = 1.12


def _p(p):
    return tuple(HEAD_PIVOT[i] + (p[i] - HEAD_PIVOT[i]) * HEAD_SCALE for i in range(3))


def _h(h):
    return tuple(x * HEAD_SCALE for x in h)


CRANIUM = (_p(CRANIUM[0]), _h(CRANIUM[1]))
CHEEKS = (_p(CHEEKS[0]), _h(CHEEKS[1]))
WHISKER_PADS = [(_p(c), _h(h)) for c, h in WHISKER_PADS]
CHIN = (_p(CHIN[0]), _h(CHIN[1]))
NOSE_BRIDGE = (_p(NOSE_BRIDGE[0]), _p(NOSE_BRIDGE[1]), NOSE_BRIDGE[2] * HEAD_SCALE)
EYE_CENTRE = _p(EYE_CENTRE)
EYE_RADIUS *= HEAD_SCALE
EAR_BASE = _p(EAR_BASE)
EAR_SIZE = _h(EAR_SIZE)
MUZZLE_MASK = (_p(MUZZLE_MASK[0]), _h(MUZZLE_MASK[1]))
BLAZE = (_p((0, BLAZE[0], 0))[1], _p((0, 0, BLAZE[1]))[2], BLAZE[2])
THROAT_MASK = (_p(THROAT_MASK[0]), THROAT_MASK[1])

# -------------------------------------------------------------- colours (linear)
BLACK = (0.020, 0.021, 0.025)
WHITE = (0.78, 0.76, 0.72)
