// Walkability check for ClassicHouse at Roblox scale.
//   node walkcheck.cjs [studsPerMetre=4.5]
// Rasterises the collision boxes the Roblox setup builds (spec parts with collision other than "none": boxes and
// upright cylinders, like blender/export_roblox.py) plus the door slabs swung open, at the interior floor, and asks:
// can a default R15 avatar (2 studs wide, 5.2 studs tall, steps over ~1 stud) walk from the front door to every
// room, and how wide is the narrowest gap it must pass on the way (widest-path bottleneck)?
const fs = require('fs');
const path = require('path');

const S = Number(process.argv[2] || 4.5);          // studs per metre
const AVATAR_R = 1.1 / S;                           // half-width incl. corner of the 2 x 1 stud torso (m)
const AVATAR_H = 5.2 / S;                           // height (m)
const STEP = 1.0 / S;                               // ledge the Humanoid walks over (m)
const F = 0.47;                                     // finished floor
const CELL = 0.025;
const IN = { x0: -4.95, x1: 4.95, z0: -3.85, z1: 3.85 };

const spec = JSON.parse(fs.readFileSync(path.join(__dirname, 'classic_house.json'), 'utf8'));
const byName = Object.fromEntries(spec.parts.map(p => [p.name, p]));
const under = (p, root) => { for (; p; p = byName[p.parent]) if (p.name === root) return true; return false; };

const boxes = [];
for (const p of spec.parts) {
  if ((p.collision || 'auto') === 'none' || ['FrontDoor', 'BackDoor', 'RoofGroup'].some(g => under(p, g))) continue;
  let size;
  if (p.shape === 'box') size = p.size;
  else if (p.shape === 'cylinder' && typeof p.radius === 'number' && (p.axis || 'y') === 'y') size = [2 * p.radius, p.height, 2 * p.radius];
  else continue;
  const at = p.at || [0, 0, 0];
  boxes.push({ n: p.name, at, size });
  if (p.mirror === 'x') boxes.push({ n: p.name + '(mirror)', at: [-at[0], at[1], at[2]], size });
}
// Doors swung 90 deg inward about their hinges (what a player walks past).
const fd = byName.FrontDoor, bd = byName.BackDoor;
boxes.push({ n: 'FrontDoor(open)', at: [fd.pivot[0] - 0.025, fd.at[1], fd.pivot[2] - fd.size[0] / 2], size: [0.05, fd.size[1], fd.size[0]] });
boxes.push({ n: 'BackDoor(open)', at: [bd.pivot[0] + 0.025, bd.at[1], bd.pivot[2] + bd.size[0] / 2], size: [0.05, bd.size[1], bd.size[0]] });

const blocking = boxes.filter(b => {
  const y0 = b.at[1] - b.size[1] / 2, y1 = b.at[1] + b.size[1] / 2;
  return y1 > F + STEP && y0 < F + AVATAR_H;
}).map(b => ({ n: b.n, x0: b.at[0] - b.size[0] / 2, x1: b.at[0] + b.size[0] / 2, z0: b.at[2] - b.size[2] / 2, z1: b.at[2] + b.size[2] / 2 }));

const NX = Math.round((IN.x1 - IN.x0) / CELL), NZ = Math.round((IN.z1 - IN.z0) / CELL);
const cx = i => IN.x0 + (i + 0.5) * CELL, cz = j => IN.z0 + (j + 0.5) * CELL;
// clearance = distance from the cell centre to the nearest obstacle or outer wall
const clear = new Float32Array(NX * NZ);
for (let j = 0; j < NZ; j++) for (let i = 0; i < NX; i++) {
  const x = cx(i), z = cz(j);
  let d = Math.min(x - IN.x0, IN.x1 - x, z - IN.z0, IN.z1 - z);
  for (const b of blocking) {
    const dx = Math.max(b.x0 - x, 0, x - b.x1), dz = Math.max(b.z0 - z, 0, z - b.z1);
    const e = (dx === 0 && dz === 0) ? 0 : Math.hypot(dx, dz);
    if (e < d) d = e;
  }
  clear[j * NX + i] = d;
}
const cell = (x, z) => [Math.floor((x - IN.x0) / CELL), Math.floor((z - IN.z0) / CELL)];

// Widest path from the start: bottleneck[c] = best possible minimum clearance along any path start -> c.
function widest(x, z) {
  const [si, sj] = cell(x, z);
  const best = new Float32Array(NX * NZ).fill(-1);
  const s = sj * NX + si; best[s] = clear[s];
  // bucketed max-first expansion
  const order = [s];
  const heap = [[best[s], s]];
  const push = (v, k) => { heap.push([v, k]); let n = heap.length - 1; while (n > 0) { const p = (n - 1) >> 1; if (heap[p][0] >= heap[n][0]) break; [heap[p], heap[n]] = [heap[n], heap[p]]; n = p; } };
  const pop = () => { const top = heap[0], last = heap.pop(); if (heap.length) { heap[0] = last; let n = 0; for (;;) { const l = 2 * n + 1, r = l + 1; let m = n; if (l < heap.length && heap[l][0] > heap[m][0]) m = l; if (r < heap.length && heap[r][0] > heap[m][0]) m = r; if (m === n) break; [heap[m], heap[n]] = [heap[n], heap[m]]; n = m; } } return top; };
  while (heap.length) {
    const [v, k] = pop();
    if (v < best[k]) continue;
    const i = k % NX, j = (k / NX) | 0;
    for (const [di, dj] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      const ni = i + di, nj = j + dj;
      if (ni < 0 || nj < 0 || ni >= NX || nj >= NZ) continue;
      const nk = nj * NX + ni, nv = Math.min(v, clear[nk]);
      if (nv > best[nk]) { best[nk] = nv; push(nv, nk); }
    }
  }
  return best;
}

const best = widest(0, 3.0); // just inside the front door
const targets = [
  ['Living room (centre)', 1.0, 2.2], ['Fireplace / sofa', 3.4, 0.25], ['Dining table', -2.1, 1.5],
  ['Kitchen', 1.4, -2.0], ['Kitchen sink', 2.6, -2.95], ['Kitchen range', 4.4, -2.7], ['Back door (inside)', 1.25, -3.5],
  ['Bedroom', -2.3, -1.3], ['Beside the bed', -4.0, -1.3], ['Wardrobe', -0.8, -2.75],
];
const studs = m => (m * S).toFixed(1);
let fail = 0;
console.log(`ClassicHouse walk check at ${S} studs/m: avatar ${studs(2 * AVATAR_R)} studs wide (clearance radius), ${studs(AVATAR_H)} tall, ${blocking.length} blocking boxes`);
console.log(`house ${studs(10.95)} x ${studs(12.06)} studs footprint, ${studs(7.69)} tall; ceiling ${studs(3.28 - F)} studs clear; doorways: front ${studs(1.12)}, back ${studs(1.10)}, interior ${studs(1.2)} wide, ${studs(2.55 - F)} tall`);
for (const [label, x, z] of targets) {
  const [i, j] = cell(x, z), k = j * NX + i;
  const own = clear[k], b = best[k];
  const ok = b >= AVATAR_R && own >= AVATAR_R;
  if (!ok) fail++;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${label.padEnd(22)} narrowest gap on the way ${studs(2 * b).padStart(5)} studs, room here ${studs(2 * own).padStart(5)} studs`);
}
// how much of the free floor (where the avatar fits) is reachable
let free = 0, reach = 0;
for (let k = 0; k < NX * NZ; k++) if (clear[k] >= AVATAR_R) { free++; if (best[k] >= AVATAR_R) reach++; }
console.log(`reachable floor: ${(reach * CELL * CELL * S * S).toFixed(0)} of ${(free * CELL * CELL * S * S).toFixed(0)} sq studs where the avatar fits (${(100 * reach / free).toFixed(1)}%)`);
process.exitCode = fail ? 1 : 0;
