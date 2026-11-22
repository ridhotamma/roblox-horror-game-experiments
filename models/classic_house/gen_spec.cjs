// Generates classic_house.json (model spec for the roblox-modeling skill).
// Measured from refs/ref08.jpg (front view of a 1940s side-gabled cottage, CC BY-SA 2.0):
// door 2.1 m tall = 121 px  ->  ~0.0175 m/px.
// Coordinates: metres, +Y up, front faces +Z, floor y = 0.
const fs = require('fs');
const path = require('path');
const addInterior = require('./interior.cjs');

const parts = [];
const box = (name, size, at, color, extra = {}) => parts.push({ name, shape: 'box', size, at, color, ...extra });
const r3 = v => Math.round(v * 1000) / 1000;

// A straight wall made of boxes around rectangular openings.
// axis 'x': runs along x, thickness along z [t0,t1]; axis 'z': runs along z, thickness along x.
// openings: [ua, ub, ya, yb] (sorted along u, non-overlapping).
function wall(prefix, axis, u0, u1, t0, t1, y0, y1, openings, color, extra = {}) {
  let n = 0;
  const piece = (ua, ub, ya, yb) => {
    if (ub - ua < 1e-3 || yb - ya < 1e-3) return;
    n += 1;
    const size = axis === 'x' ? [ub - ua, yb - ya, t1 - t0] : [t1 - t0, yb - ya, ub - ua];
    const at = axis === 'x' ? [(ua + ub) / 2, (ya + yb) / 2, (t0 + t1) / 2] : [(t0 + t1) / 2, (ya + yb) / 2, (ua + ub) / 2];
    box(`${prefix}${n}`, size.map(r3), at.map(r3), color, { collision: 'box', lod: 'keep', ...extra });
  };
  let u = u0;
  for (const [ua, ub, ya, yb] of openings) {
    piece(u, ua, y0, y1);   // pier up to the opening
    piece(ua, ub, y0, ya);  // below the opening (none for doorways)
    piece(ua, ub, yb, y1);  // above the opening
    u = ub;
  }
  piece(u, u1, y0, y1);
}

// ---- main body ---------------------------------------------------------------
const W = 10.2;          // outside wall width (x)
const D = 8.0;           // outside wall depth (z)
const T = 0.15;          // exterior wall thickness
const WALL_BOTTOM = 0.43; // sinks 2 cm into the foundation top (0.45)
const WALL_TOP = 3.4;    // eave line
const GABLE_PEAK = 5.55; // gable apex (inside the roof)
const S = (GABLE_PEAK - WALL_TOP) / (D / 2); // roof slope 0.5375 (~28 deg)
const XI = W / 2 - T, ZI = D / 2 - T;         // inside faces: x +-4.95, z +-3.85

box('Foundation', [10.4, 0.45, 8.2], [0, 0.225, 0], 'found', { collision: 'box' });

// Window openings (the glass panes fill them through the whole wall).
const WIN_Y = 2.125, WIN_H = 1.65;  // frame: sill ~1.3 m, head 2.95 m
const GY0 = 1.38, GY1 = 2.87;       // glass / opening height
const FRONT_WIN_X = [-3.85, -2.95, 2.95, 3.85];
const BACK_WIN_X = [-2.6, 2.6];
const GW = 0.79;                    // glass / opening width
const winOpen = x => [r3(x - GW / 2), r3(x + GW / 2), GY0, GY1];

// Doors: front opening x -0.47..0.47, back opening x 0.75..1.65 (clear of the centre partition).
const FD = { x0: -0.47, x1: 0.47, top: 2.59 };
const BD = { x0: 0.75, x1: 1.65, top: 2.57 };

wall('WallFront', 'x', -W / 2, W / 2, ZI, D / 2, WALL_BOTTOM, WALL_TOP,
  [winOpen(-3.85), winOpen(-2.95), [FD.x0, FD.x1, WALL_BOTTOM, FD.top], winOpen(2.95), winOpen(3.85)], 'wall');
wall('WallBack', 'x', -W / 2, W / 2, -D / 2, -ZI, WALL_BOTTOM, WALL_TOP,
  [winOpen(-2.6), [BD.x0, BD.x1, WALL_BOTTOM, BD.top], winOpen(2.6)], 'wall');
wall('WallLeft', 'z', -ZI, ZI, -W / 2, -XI, WALL_BOTTOM, WALL_TOP, [[-GW / 2, GW / 2, GY0, GY1]], 'wall');
wall('WallRight', 'z', -ZI, ZI, XI, W / 2, WALL_BOTTOM, WALL_TOP, [[-GW / 2, GW / 2, GY0, GY1]], 'wall');
parts.push({
  name: 'GableL', shape: 'extrude', plane: 'zy', depth: T, at: [-(W / 2 - T / 2), 0, 0], mirror: 'x', color: 'wall', collision: 'default',
  outline: [[D / 2, WALL_TOP], [0, GABLE_PEAK], [-D / 2, WALL_TOP]],
  note: 'gable triangle on top of the side wall',
});

// Roof: one chevron slab, 0.26 m thick vertically, 0.5 m eave overhang, 0.35 m at the gable ends.
const EAVE = 4.5, RB = 5.52, RT = 5.78;
parts.push({
  name: 'Roof', shape: 'extrude', plane: 'zy', depth: W + 0.7, color: 'roof', collision: 'default',
  outline: [[EAVE, RB - S * EAVE], [EAVE, RT - S * EAVE], [0, RT], [-EAVE, RT - S * EAVE], [-EAVE, RB - S * EAVE], [0, RB]],
});
box('RidgeCap', [W + 0.75, 0.14, 0.3], [0, 5.76, 0], 'ridge');

// Corner boards and eave frieze (white trim).
const cbH = 3.38 - 0.46;
box('CornerFrontL', [0.18, cbH, 0.18], [-5.07, 0.46 + cbH / 2, 3.97], 'trim', { mirror: 'x' });
box('CornerBackL', [0.18, cbH, 0.18], [-5.07, 0.46 + cbH / 2, -3.97], 'trim', { mirror: 'x' });
box('FriezeFront', [10.0, 0.23, 0.14], [0, 3.295, 3.98], 'trim');
box('FriezeBack', [10.0, 0.23, 0.14], [0, 3.295, -3.98], 'trim');

// ---- chimney (right of centre, just behind the ridge) ------------------------
box('Chimney', [0.85, 3.4, 0.7], [3.6, 5.7, -0.6], 'brick', { collision: 'box' });
box('ChimneyCap', [1.0, 0.14, 0.85], [3.6, 7.45, -0.6], 'cap');
box('ChimneyFlue', [0.35, 0.18, 0.3], [3.6, 7.58, -0.6], 'flue');

// ---- front porch: stoop, steps, paired columns, arched pediment, gable roof --
box('Stoop', [5.2, 0.47, 1.9], [0, 0.235, 5.05], 'concrete', { collision: 'box' });
box('Step1', [2.2, 0.31, 0.35], [0, 0.155, 6.175], 'concrete', { collision: 'box' });
box('Step2', [2.2, 0.155, 0.35], [0, 0.0775, 6.525], 'concrete', { collision: 'box' });

const COL_Z = 5.55;
for (const [tag, x] of [['In', -1.33], ['Out', -1.93]]) {
  box(`ColBase${tag}L`, [0.34, 0.1, 0.34], [x, 0.52, COL_Z], 'trim', { mirror: 'x', collision: 'none' });
  parts.push({
    name: `Col${tag}L`, shape: 'cylinder', radius: 0.12, height: 2.28, segments: 8, shading: 'smooth',
    at: [x, 1.70, COL_Z], color: 'trim', mirror: 'x', collision: 'hull',
  });
  box(`ColCap${tag}L`, [0.34, 0.13, 0.34], [x, 2.895, COL_Z], 'trim', { mirror: 'x', collision: 'none' });
}

// Pediment with a barrel-vault arch cut through it (the arched entry of the reference).
const arch = [150, 120, 90, 60, 30].map(a => [r3(1.2 * Math.cos(a * Math.PI / 180)), r3(2.95 + 0.8 * Math.sin(a * Math.PI / 180))]);
const PS = 0.5927; // porch roof slope (~30.6 deg)
parts.push({
  name: 'Pediment', shape: 'extrude', plane: 'xy', depth: 1.85, at: [0, 0, 4.875], color: 'trim', collision: 'default',
  outline: [[2.55, 2.95], [2.55, r3(4.95 - PS * 2.55)], [0, 4.95], [-2.55, r3(4.95 - PS * 2.55)], [-2.55, 2.95], [-1.2, 2.95], ...arch, [1.2, 2.95]],
  note: 'front gable over the porch with an elliptical arch opening',
});
parts.push({
  name: 'PorchRoof', shape: 'extrude', plane: 'xy', depth: 5.1, at: [0, 0, 3.55], color: 'roof', collision: 'default',
  outline: [[2.75, 3.30], [2.75, 3.52], [0, 5.15], [-2.75, 3.52], [-2.75, 3.30], [0, 4.93]],
  note: 'runs back into the attic so the valley closes',
});

// ---- front door: casing with sidelights, threshold, hinged door -------------
box('FrontCasingL', [0.49, 2.35, 0.04], [-0.705, 1.645, 4.0], 'trim', { mirror: 'x' });
box('FrontCasingHead', [0.92, 0.24, 0.04], [0, 2.70, 4.0], 'trim');
box('SidelightL', [0.26, 1.8, 0.06], [-0.68, 1.55, 4.005], 'glass', { mirror: 'x' });
box('FrontThreshold', [0.94, 0.05, 0.27], [0, 0.455, 3.985], 'oak', { collision: 'box' });

const brass = { color: 'brass', material: { metalness: 0.7, roughness: 0.35 }, collision: 'none' };
// Door 0.93 x 2.10 in a 0.94 opening; hinged on the left jamb at the inside face, swings inward.
box('FrontDoor', [0.93, 2.10, 0.05], [-0.005, 1.535, 3.955], 'door', {
  pivot: [FD.x0, 1.535, 3.93], collision: 'box', note: 'hinge: left jamb, inside face; +Y opens inward',
});
box('FrontDoorGlass', [0.5, 0.6, 0.06], [-0.005, 2.1, 3.955], 'glass', { parent: 'FrontDoor' });
box('FrontDoorPanel', [0.6, 0.7, 0.07], [-0.005, 0.95, 3.955], 'doorDark', { parent: 'FrontDoor', collision: 'none' });
parts.push({ name: 'FrontKnobOut', shape: 'sphere', radius: 0.035, detail: 0, at: [0.36, 1.45, 4.005], parent: 'FrontDoor', ...brass });
parts.push({ name: 'FrontKnobIn', shape: 'sphere', radius: 0.035, detail: 0, at: [0.36, 1.45, 3.905], parent: 'FrontDoor', ...brass });

// ---- windows (frames, mullions and shutters outside; glass through the wall) -
const pairX = -3.4;
box('FrontPairFrameL', [1.9, WIN_H, 0.04], [pairX, WIN_Y, 4.0], 'trim', { mirror: 'x' });
for (const [i, x] of [[1, -2.95], [2, -3.85]]) {
  box(`FrontGlass${i}L`, [GW, 1.49, 0.195], [x, WIN_Y, 3.9375], 'glass', { mirror: 'x' });
  box(`FrontMullV${i}L`, [0.05, 1.47, 0.06], [x, WIN_Y, 4.025], 'trim', { mirror: 'x', collision: 'none' });
  box(`FrontMullH${i}L`, [0.77, 0.05, 0.06], [x, WIN_Y + 0.15, 4.02], 'trim', { mirror: 'x', collision: 'none' });
}
box('FrontSillL', [1.86, 0.07, 0.13], [pairX, 1.33, 4.055], 'trim', { mirror: 'x' });
box('FrontHeadL', [1.86, 0.1, 0.07], [pairX, 2.99, 4.025], 'trim', { mirror: 'x' });
for (const [tag, x] of [['Out', -4.565], ['In', -2.235]]) {
  box(`Shutter${tag}L`, [0.42, WIN_H, 0.04], [x, WIN_Y, 4.01], 'shutter', { mirror: 'x' });
  box(`ShutterRail${tag}L`, [0.38, 0.06, 0.06], [x, WIN_Y, 4.015], 'shutter', { mirror: 'x', collision: 'none' });
}

// Gable ends: one window each side plus a small attic window.
const SX = -5.1;
box('SideFrameL', [0.04, WIN_H, 0.95], [SX, WIN_Y, 0], 'trim', { mirror: 'x' });
box('SideGlassL', [0.195, 1.49, GW], [-5.0375, WIN_Y, 0], 'glass', { mirror: 'x' });
box('SideMullVL', [0.06, 1.47, 0.05], [SX - 0.025, WIN_Y, 0], 'trim', { mirror: 'x', collision: 'none' });
box('SideMullHL', [0.06, 0.05, 0.77], [SX - 0.02, WIN_Y + 0.15, 0], 'trim', { mirror: 'x', collision: 'none' });
box('SideSillL', [0.13, 0.07, 1.07], [SX - 0.055, 1.33, 0], 'trim', { mirror: 'x' });
box('SideHeadL', [0.07, 0.1, 1.07], [SX - 0.025, 2.99, 0], 'trim', { mirror: 'x' });
box('SideShutterFrontL', [0.04, WIN_H, 0.42], [SX - 0.01, WIN_Y, 0.71], 'shutter', { mirror: 'x' });
box('SideShutterBackL', [0.04, WIN_H, 0.42], [SX - 0.01, WIN_Y, -0.71], 'shutter', { mirror: 'x' });
box('AtticFrameL', [0.04, 0.8, 0.8], [SX, 4.25, 0], 'trim', { mirror: 'x' });
box('AtticGlassL', [0.06, 0.66, 0.66], [SX - 0.005, 4.25, 0], 'glass', { mirror: 'x' });
box('AtticMullVL', [0.06, 0.64, 0.05], [SX - 0.025, 4.25, 0], 'trim', { mirror: 'x', collision: 'none' });
box('AtticMullHL', [0.06, 0.05, 0.64], [SX - 0.02, 4.25, 0], 'trim', { mirror: 'x', collision: 'none' });

// Back: two windows and a hinged back door with a step.
const BZ = -4.0;
box('BackFrameL', [0.95, WIN_H, 0.04], [-2.6, WIN_Y, BZ], 'trim', { mirror: 'x' });
box('BackGlassL', [GW, 1.49, 0.195], [-2.6, WIN_Y, -3.9375], 'glass', { mirror: 'x' });
box('BackMullVL', [0.05, 1.47, 0.06], [-2.6, WIN_Y, BZ - 0.025], 'trim', { mirror: 'x', collision: 'none' });
box('BackMullHL', [0.77, 0.05, 0.06], [-2.6, WIN_Y + 0.15, BZ - 0.02], 'trim', { mirror: 'x', collision: 'none' });
box('BackSillL', [1.07, 0.07, 0.13], [-2.6, 1.33, BZ - 0.055], 'trim', { mirror: 'x' });
box('BackHeadL', [1.07, 0.1, 0.07], [-2.6, 2.99, BZ - 0.025], 'trim', { mirror: 'x' });
box('BackCasingL', [0.11, 2.24, 0.04], [0.705, 1.59, BZ], 'trim');
box('BackCasingR', [0.11, 2.24, 0.04], [1.695, 1.59, BZ], 'trim');
box('BackCasingHead', [0.88, 0.15, 0.04], [1.2, 2.635, BZ], 'trim');
box('BackThreshold', [0.9, 0.05, 0.27], [1.2, 0.455, -3.985], 'oak', { collision: 'box' });
box('BackDoor', [0.89, 2.08, 0.05], [1.195, 1.525, -3.955], 'backdoor', {
  pivot: [BD.x0, 1.525, -3.93], collision: 'box', note: 'hinge: left jamb seen from inside... x 0.75, inside face; -Y opens inward',
});
box('BackDoorPanelTop', [0.6, 0.75, 0.07], [1.195, 2.0, -3.955], 'backdoorDark', { parent: 'BackDoor', collision: 'none' });
box('BackDoorPanelBottom', [0.6, 0.75, 0.07], [1.195, 1.0, -3.955], 'backdoorDark', { parent: 'BackDoor', collision: 'none' });
parts.push({ name: 'BackKnobOut', shape: 'sphere', radius: 0.035, detail: 0, at: [1.56, 1.45, -4.005], parent: 'BackDoor', ...brass });
parts.push({ name: 'BackKnobIn', shape: 'sphere', radius: 0.035, detail: 0, at: [1.56, 1.45, -3.905], parent: 'BackDoor', ...brass });
box('BackStep', [1.3, 0.44, 0.8], [1.2, 0.22, -4.5], 'concrete', { collision: 'box' });

// ---- interior ----------------------------------------------------------------
// Floor 0.47, ceiling 3.28 (2.8 m clear). Attic above the ceiling stays closed.
box('Floor', [2 * XI, 0.07, 2 * ZI], [0, 0.435, 0], 'floor', { collision: 'box' });
box('Ceiling', [2 * XI, 0.12, 2 * ZI], [0, 3.34, 0], 'ceiling', { collision: 'box' });
// Partitions: living room at the front (z > -0.75), two back rooms split at x = 0.
const PY0 = 0.46, PY1 = 3.29, DOOR_TOP = 2.55;
wall('PartitionMid', 'x', -XI, XI, -0.85, -0.75, PY0, PY1, [[-2.95, -2.05, PY0, DOOR_TOP], [1.05, 1.95, PY0, DOOR_TOP]], 'interior');
wall('PartitionBack', 'z', -ZI, -0.85, -0.05, 0.05, PY0, PY1, [], 'interior');
// Doorway casings (living-room side) so the openings read from across the room.
for (const [tag, x] of [['L', -2.5], ['R', 1.5]]) {
  // jambs straddle the opening edge (no shared planes), head sits 1 cm below the lintel bottom
  box(`DoorwayJambA${tag}`, [0.08, r3(DOOR_TOP - 0.01 - 0.47), 0.14], [r3(x - 0.47), r3((0.47 + DOOR_TOP - 0.01) / 2), -0.80], 'trim', { collision: 'none' });
  box(`DoorwayJambB${tag}`, [0.08, r3(DOOR_TOP - 0.01 - 0.47), 0.14], [r3(x + 0.47), r3((0.47 + DOOR_TOP - 0.01) / 2), -0.80], 'trim', { collision: 'none' });
  box(`DoorwayHead${tag}`, [1.06, 0.1, 0.14], [x, r3(DOOR_TOP + 0.04), -0.80], 'trim', { collision: 'none' });
}
// Brick fireplace on the living-room side of the partition, under the chimney.
box('Hearth', [1.6, 0.08, 0.57], [3.9, 0.49, -0.485], 'cap', { collision: 'box' });
box('FireplaceBody', [1.3, 1.19, 0.48], [3.9, 1.115, -0.54], 'brick', { collision: 'box' });
box('Firebox', [0.7, 0.62, 0.06], [3.9, 0.86, -0.30], 'flue', { collision: 'none' });
box('Mantel', [1.55, 0.08, 0.46], [3.9, 1.75, -0.56], 'oak', { collision: 'box' });
box('ChimneyBreast', [0.95, 1.51, 0.35], [3.9, 2.545, -0.625], 'brick', { collision: 'box' });

// ---- planting (the reference has conifers by the steps and shrubs under the windows)
parts.push({ name: 'ConiferL', shape: 'cone', radius: [0.42, 0], height: 1.5, segments: 7, at: [-1.8, 0.75, 6.35], color: 'leafDark', mirror: 'x', collision: 'none', jitter: 0.02 });
parts.push({ name: 'BushL', shape: 'sphere', radius: [0.6, 0.42, 0.45], detail: 1, jitter: 0.03, at: [-4.3, 0.48, 4.45], color: 'leaf', mirror: 'x', collision: 'none' });

// ---- furnishings (interior.cjs) and the roof group ------------------------------
addInterior(parts, r3);
const lightNames = addInterior.ceilingLights(parts, r3);

// Everything above the rooms (roof, gables, chimney, attic windows, ceiling and the lights hanging
// from it) hangs under RoofGroup, so it exports as its own piece that can be hidden or lifted.
const ROOF = new Set(['Roof', 'RidgeCap', 'PorchRoof', 'Pediment', 'GableL', 'Chimney', 'ChimneyCap', 'ChimneyFlue', 'Ceiling',
  'AtticFrameL', 'AtticGlassL', 'AtticMullVL', 'AtticMullHL', ...lightNames]);
for (const p of parts) if (ROOF.has(p.name)) p.parent = 'RoofGroup';
parts.unshift({ name: 'RoofGroup', shape: 'none', pivot: [0, WALL_TOP, 0], note: 'hide / lift this to see inside' });

// ---- animations: doors swing 90 deg inward about their hinges -----------------
const openKeys = deg => [[0, [0, 0, 0]], [0.2, [0, deg * 0.05, 0], 'out'], [1.6, [0, deg, 0], 'out']];
const closeKeys = deg => [[0, [0, deg, 0]], [0.45, [0, 0, 0], 'in'], [0.55, [0, deg * 0.035, 0], 'out'], [0.65, [0, 0, 0], 'in']];
const animations = [
  { name: 'FrontDoorOpen', duration: 1.6, description: 'Front door creaks open inward to 90 degrees.', tracks: [{ part: 'FrontDoor', rot: openKeys(90) }], markers: [{ t: 0.0, name: 'Unlatch' }, { t: 0.2, name: 'Creak' }] },
  { name: 'FrontDoorClose', duration: 0.65, description: 'Front door swings shut and settles.', tracks: [{ part: 'FrontDoor', rot: closeKeys(90) }], markers: [{ t: 0.45, name: 'Slam' }] },
  { name: 'BackDoorOpen', duration: 1.6, description: 'Back door creaks open inward to 90 degrees.', tracks: [{ part: 'BackDoor', rot: openKeys(-90) }], markers: [{ t: 0.0, name: 'Unlatch' }, { t: 0.2, name: 'Creak' }] },
  { name: 'BackDoorClose', duration: 0.65, description: 'Back door swings shut and settles.', tracks: [{ part: 'BackDoor', rot: closeKeys(-90) }], markers: [{ t: 0.45, name: 'Slam' }] },
  { name: 'RoofLift', duration: 1.2, description: 'Roof, ceiling and ceiling lights lift 4 m to show the rooms (cutaway view).', tracks: [{ part: 'RoofGroup', pos: [[0, [0, 0, 0]], [1.2, [0, 4, 0], 'inOut']] }] },
  { name: 'RoofLower', duration: 1.2, description: 'Roof settles back into place.', tracks: [{ part: 'RoofGroup', pos: [[0, [0, 4, 0]], [1.2, [0, 0, 0], 'inOut']] }] },
];

const spec = {
  name: 'ClassicHouse',
  title: 'Classic cottage house',
  description: 'Low-poly 1940s-style side-gabled cottage: white walls, dark shingle roof, arched gable porch on paired columns, red front door with sidelights, shuttered window pairs and brick chimney. Hollow, with a floor, ceiling, a front living room with a brick fireplace and two back rooms. Front and back doors are hinged and open inward. Furnished from 1940s interior references: living room with fireplace, bookcases, sofa, armchair, rug, dining set, sideboard and radio; kitchen with cabinets, sink, range, fridge and table; bedroom with bed, nightstands, dresser and wardrobe. The roof, ceiling and ceiling lights form RoofGroup, which can be hidden or lifted.',
  ground: true,
  budget: 16000,
  targets: ['roblox', 'blender', 'threejs'],
  reference: {
    sources: [
      { url: 'https://www.flickr.com/photos/59081381@N03/', note: 'refs/ref08.jpg: front view, side-gabled cottage with arched gable porch, paired columns, shuttered window pairs, chimney right of centre (CC BY-SA 2.0)', file: 'refs/ref08.jpg' },
      { url: 'https://www.flickr.com/photos/59081381@N03/52016327411', note: 'refs/ref14.jpg: same house type from a slightly different angle', file: 'refs/ref14.jpg' },
    ],
    dimensions: { width: 10.9, height: 7.67, tolerance: 0.06 },
    notes: 'Scale from the front door (2.1 m = 121 px, ~0.0175 m/px). Wall ~10.3 m wide, eave 3.4 m above ground, ridge ~5.9 m, foundation ~0.45 m, roof span 11.0 m, chimney top ~7.4 m. Porch gable ~5 m wide rising ~1.5 m, columns paired ~0.6 m apart, ~1.3 / 1.9 m off the door centre. Windows ~0.8 x 1.55 m in pairs with ~0.45 m shutters. Depth (8 m), roof pitch (~28 deg) and the floor plan are typical for the type, not measured. Made symmetric about the door.',
  },
  palette: {
    wall: '#e9e5da', trim: '#f7f6f1', roof: '#4a5156', ridge: '#3d4347', found: '#7d8581',
    door: '#c0392b', doorDark: '#a3302a', backdoor: '#6b4a36', backdoorDark: '#5a3d2c',
    glass: '#2c3a47', shutter: '#3d4a4f', brick: '#94473a', cap: '#6a6e70', flue: '#1d1f21',
    concrete: '#a9aca6', leaf: '#4b7a3f', leafDark: '#2f5530', brass: '#c9a43a',
    oak: '#8a6a45', floor: '#6e5038', ceiling: '#e2ddd0', interior: '#b8ae98',
    wood: '#7a5233', woodLight: '#a07a52', woodDark: '#4f3322', fabricGreen: '#5f7a55', fabricRose: '#a0584f',
    cloth: '#f2efe6', gingham: '#c8524a', enamel: '#f1efe8', enamelDoor: '#e6e3da', counter: '#3f4a52',
    steel: '#9aa1a8', steelDark: '#4a5056', kettle: '#c8423a', canister: '#e8c46a', china: '#f4f1ea', vase: '#3f6d8c',
    shade: '#f3e2b3', glowWarm: '#ffcf7a', mirror: '#c9d6de', curtain: '#c7a46a', curtainBed: '#c9a0a0',
    carpet: '#5d6f73', rug: '#8e3b2e', lino: '#d8d2c0', linen: '#f0ece2', quilt: '#7c8fa8', grille: '#6b5a44',
    logBark: '#5a4030', canvas1: '#6d8a6a', canvas2: '#c49a5a', canvas3: '#8a7aa8',
    book1: '#7a2e2a', book2: '#2e4a6b', book3: '#3f5f3a', book4: '#b08a3e', book5: '#5a3f5f', book6: '#2f2f2f',
  },
  camera: { yaw: 32, pitch: 18 },
  parts,
  animations,
  checks: [
    { type: 'ratio', a: 'x', b: 'y', expect: 1.45, tol: 0.07, label: 'roof span : chimney-top height like the reference (11.0 : 7.44)' },
    { type: 'size', axis: 'y', min: 7.3, max: 7.8, label: 'overall height ~7.4-7.7 m' },
    { type: 'angle', clip: 'FrontDoorOpen', at: 'end', part: 'FrontDoor', axis: 'y', min: 88, max: 92, label: 'front door opens 90 deg inward' },
    { type: 'angle', clip: 'BackDoorOpen', at: 'end', part: 'BackDoor', axis: 'y', min: -92, max: -88, label: 'back door opens 90 deg inward' },
    { type: 'pose', clip: 'FrontDoorClose', at: 'end', equals: 'rest', label: 'front door closes fully' },
    { type: 'pose', clip: 'BackDoorClose', at: 'end', equals: 'rest', label: 'back door closes fully' },
    { type: 'pose', clip: 'FrontDoorClose', at: 'start', equals: { clip: 'FrontDoorOpen', at: 'end' }, label: 'front Close starts where Open ends' },
    { type: 'pose', clip: 'BackDoorClose', at: 'start', equals: { clip: 'BackDoorOpen', at: 'end' }, label: 'back Close starts where Open ends' },
    { type: 'apart', a: 'FrontDoor', b: 'FrontThreshold', clip: 'FrontDoorOpen', label: 'front door clears the threshold' },
    { type: 'apart', a: 'FrontDoor', b: 'Floor', clip: 'FrontDoorOpen', label: 'front door clears the floor' },
    { type: 'apart', a: 'BackDoor', b: 'BackThreshold', clip: 'BackDoorOpen', label: 'back door clears the threshold' },
    { type: 'apart', a: 'BackDoor', b: 'PartitionBack1', clip: 'BackDoorOpen', label: 'back door misses the back partition' },
  ],
};

fs.writeFileSync(path.join(__dirname, 'classic_house.json'), JSON.stringify(spec, null, 1));
console.log(`wrote classic_house.json with ${parts.length} part entries`);
