// Furnishings for ClassicHouse, in model space (metres, +Y up, front +Z, floor top y = 0.47).
// Layout follows 1940s interior references in refs/living, refs/kitchen, refs/bedroom:
//   living room: fireplace flanked by a bookcase, sofa + armchair + coffee table on a Persian rug,
//                dining table with cloth and four chairs, sideboard, console radio, floor lamp, pictures
//   kitchen:     white base cabinets with the sink under the window, enamel range, rounded fridge,
//                wall cabinet, small table with gingham cloth and two chairs, checkerboard linoleum
//   bedroom:     full-size bed with arched head/footboard, two nightstands with lamps, dresser with a
//                round mirror, wardrobe, wall-to-wall carpet
// Sizes are standard furniture sizes (seat 0.45 m, dining table 0.75 m, counter 0.90 x 0.60 m,
// wall cabinets 0.46 m above the counter, range 0.76 x 0.91 m, full mattress 1.37 x 1.91 m, top ~0.62 m).

const F = 0.47; // finished floor height

module.exports = function addInterior(parts, r3) {
  const add = p => { parts.push(p); return p; };
  const box = (name, size, at, color, extra = {}) => add({ name, shape: 'box', size: size.map(r3), at: at.map(r3), color, collision: 'none', ...extra });

  // Place pieces given in furniture-local coordinates: u = right, y = up, w = forward (the way it faces).
  function place(prefix, cx, cz, facing, pieces) {
    for (const p of pieces) {
      const [pu, py, pw] = p.p;
      let x, z, size = p.s;
      if (facing === '+z') { x = cx + pu; z = cz + pw; }
      else if (facing === '-z') { x = cx - pu; z = cz - pw; }
      else if (facing === '+x') { x = cx + pw; z = cz - pu; size = [p.s[2], p.s[1], p.s[0]]; }
      else { x = cx - pw; z = cz + pu; size = [p.s[2], p.s[1], p.s[0]]; }
      const extra = { ...(p.x || {}) };
      if (p.shape === 'cylinder' && extra.axis === 'w') extra.axis = (facing === '+z' || facing === '-z') ? 'z' : 'x';
      if (p.shape === 'cylinder') add({ name: prefix + p.n, shape: 'cylinder', radius: p.r, height: p.h, segments: p.seg || 8, at: [x, py, z].map(r3), color: p.c, collision: 'none', ...extra });
      else box(prefix + p.n, size, [x, py, z], p.c, extra);
    }
  }

  // ---- reusable furniture ------------------------------------------------------
  const legs = (w, d, h, t, c, inset = 0.03) => [[-1, -1], [1, -1], [-1, 1], [1, 1]].map(([a, b], i) => ({
    n: `Leg${i + 1}`, s: [t, h, t], p: [a * (w / 2 - inset - t / 2), F + h / 2, b * (d / 2 - inset - t / 2)], c,
  }));

  function chair(prefix, cx, cz, facing, wood = 'wood') {
    place(prefix, cx, cz, facing, [
      ...legs(0.44, 0.42, 0.40, 0.045, wood),
      { n: 'Seat', s: [0.44, 0.05, 0.42], p: [0, F + 0.425, 0], c: wood, x: { collision: 'box' } },
      { n: 'PostL', s: [0.045, 0.52, 0.045], p: [-0.1975, F + 0.71, -0.1875], c: wood },
      { n: 'PostR', s: [0.045, 0.52, 0.045], p: [0.1975, F + 0.71, -0.1875], c: wood },
      { n: 'Back', s: [0.35, 0.24, 0.04], p: [0, F + 0.83, -0.1875], c: wood },
    ]);
  }

  function clothTable(prefix, cx, cz, w, d, cloth, wood = 'wood') {
    // Table 0.75 m high; the cloth is a box that wraps the top and drapes 0.2 m.
    place(prefix, cx, cz, '+z', [
      ...legs(w, d, 0.55, 0.06, wood, 0.05),
      { n: 'Cloth', s: [w + 0.12, 0.21, d + 0.12], p: [0, F + 0.645, 0], c: cloth, x: { collision: 'box' } },
    ]);
  }

  function sofa(prefix, cx, cz, facing, w, fabric, seats) {
    const d = 0.89, armW = 0.18, inner = w - 2 * armW;
    const pcs = [
      ...legs(w, d, 0.08, 0.06, 'woodDark', 0.06),
      { n: 'Base', s: [w, 0.25, d], p: [0, F + 0.205, 0], c: fabric, x: { collision: 'box' } },
      { n: 'Back', s: [inner, 0.52, 0.22], p: [0, F + 0.33 + 0.26, -d / 2 + 0.11], c: fabric },
      { n: 'ArmL', s: [armW, 0.3, d], p: [-(w / 2 - armW / 2), F + 0.33 + 0.15 - 0.01, 0], c: fabric, x: { chamfer: 0.03 } },
      { n: 'ArmR', s: [armW, 0.3, d], p: [w / 2 - armW / 2, F + 0.33 + 0.15 - 0.01, 0], c: fabric, x: { chamfer: 0.03 } },
    ];
    const cw = inner / seats;
    for (let i = 0; i < seats; i++) {
      pcs.push({ n: `Cushion${i + 1}`, s: [cw - 0.02, 0.13, d - 0.24], p: [-inner / 2 + cw * (i + 0.5), F + 0.33 + 0.055, 0.09], c: fabric, x: { chamfer: 0.025 } });
    }
    place(prefix, cx, cz, facing, pcs);
  }

  function bookcase(prefix, cx, cz, facing, seed) {
    const w = 0.9, d = 0.3, h = 1.8;
    const pcs = [
      { n: 'SideL', s: [0.04, h, d], p: [-w / 2 + 0.02, F + h / 2, 0], c: 'woodDark', x: { collision: 'box' } },
      { n: 'SideR', s: [0.04, h, d], p: [w / 2 - 0.02, F + h / 2, 0], c: 'woodDark', x: { collision: 'box' } },
      { n: 'BackPanel', s: [w - 0.08, h - 0.12, 0.04], p: [0, F + 0.08 + (h - 0.12) / 2, -d / 2 + 0.02], c: 'woodDark' },
      { n: 'Top', s: [w - 0.08, 0.04, d], p: [0, F + h - 0.02, 0], c: 'woodDark' },
      { n: 'Bottom', s: [w - 0.08, 0.08, d - 0.01], p: [0, F + 0.04, -0.005], c: 'woodDark' },
    ];
    const shelfTops = [F + 0.08];
    [0.48, 0.93, 1.38].forEach((y, i) => {
      pcs.push({ n: `Shelf${i + 1}`, s: [w - 0.08, 0.04, 0.23], p: [0, F + y, 0.005], c: 'woodDark' });
      shelfTops.push(F + y + 0.02);
    });
    // Books: deterministic sizes and colours, standing on the first three levels.
    const colors = ['book1', 'book2', 'book3', 'book4', 'book5', 'book6'];
    let r = seed;
    const rnd = () => { r = (r * 9301 + 49297) % 233280; return r / 233280; };
    shelfTops.slice(0, 4).forEach((top, level) => {
      let u = -w / 2 + 0.045;
      const end = w / 2 - 0.045 - (level === 2 ? 0.3 : 0.05);
      let i = 0;
      while (u < end - 0.05) {
        const t = 0.04 + Math.round(rnd() * 3) * 0.01;
        const bh = 0.2 + Math.round(rnd() * 12) * 0.01;
        pcs.push({ n: `Book${level}_${i++}`, s: [t, bh, 0.2], p: [u + t / 2, top + bh / 2, -d / 2 + 0.04 + 0.1], c: colors[Math.floor(rnd() * colors.length)] });
        u += t;
      }
    });
    place(prefix, cx, cz, facing, pcs);
  }

  function picture(prefix, x, y, z, facing, w, h, canvas) {
    // Frame sinks 1 cm into the wall; canvas stands 5 mm proud of the frame.
    place(prefix, x, z, facing, [
      { n: 'Frame', s: [w, h, 0.04], p: [0, y, 0.01], c: 'woodDark' },
      { n: 'Canvas', s: [w - 0.1, h - 0.1, 0.04], p: [0, y, 0.015], c: canvas },
    ]);
  }

  function tableLamp(prefix, x, y0, z) {
    add({ name: prefix + 'Base', shape: 'cylinder', radius: 0.07, height: 0.04, segments: 8, at: [x, y0 + 0.02, z].map(r3), color: 'brass', material: { metalness: 0.6, roughness: 0.4 }, collision: 'none' });
    add({ name: prefix + 'Stem', shape: 'cylinder', radius: 0.022, height: 0.28, segments: 6, at: [x, y0 + 0.17, z].map(r3), color: 'brass', material: { metalness: 0.6, roughness: 0.4 }, collision: 'none' });
    add({ name: prefix + 'Shade', shape: 'cone', radius: [0.16, 0.1], height: 0.2, segments: 8, at: [x, y0 + 0.39, z].map(r3), color: 'shade', material: { emissive: 'glowWarm' }, collision: 'none' });
  }

  // ======================= LIVING ROOM (z -0.75 .. 3.85) =======================
  // Persian rug under the seating group (1 cm proud of the floor, sunk into the subfloor).
  box('Rug', [2.5, 0.05, 2.0], [3.65, 0.455, 1.3], 'rug');

  sofa('Sofa', 3.85, 2.4, '-z', 2.1, 'fabricGreen', 3);
  sofa('Armchair', 2.5, 0.9, '+x', 0.85, 'fabricRose', 1);
  place('CoffeeTable', 3.9, 1.2, '+z', [
    ...legs(1.1, 0.55, 0.41, 0.05, 'wood'),
    { n: 'Top', s: [1.1, 0.04, 0.55], p: [0, F + 0.43, 0], c: 'wood', x: { collision: 'box' } },
    { n: 'Shelf', s: [0.96, 0.04, 0.41], p: [0, F + 0.12, 0], c: 'wood' },
  ]);
  add({ name: 'CoffeeBowl', shape: 'sphere', radius: [0.12, 0.05, 0.12], detail: 1, at: [3.75, F + 0.47, 1.2], color: 'china', collision: 'none' });

  // Floor lamp beside the sofa.
  add({ name: 'FloorLampBase', shape: 'cylinder', radius: 0.16, height: 0.04, segments: 8, at: [4.62, F + 0.02, 1.45], color: 'brass', material: { metalness: 0.6, roughness: 0.4 }, collision: 'none' });
  add({ name: 'FloorLampPole', shape: 'cylinder', radius: 0.022, height: 1.3, segments: 6, at: [4.62, F + 0.69, 1.45], color: 'brass', material: { metalness: 0.6, roughness: 0.4 }, collision: 'none' });
  add({ name: 'FloorLampShade', shape: 'cone', radius: [0.24, 0.15], height: 0.3, segments: 8, at: [4.62, F + 1.45, 1.45], color: 'shade', material: { emissive: 'glowWarm' }, collision: 'none' });

  // Bookcase beside the fireplace and a second one on the left wall.
  bookcase('BookcaseFire', 2.6, -0.6, '+z', 17);
  bookcase('BookcaseWall', -4.8, 3.0, '+x', 41);

  // Fireplace dressing: logs, mantel clock, candlesticks, painting on the chimney breast.
  for (const [i, dz] of [[1, -0.02], [2, 0.06]]) {
    add({ name: `Log${i}`, shape: 'cylinder', radius: 0.055, height: 0.48, segments: 6, axis: 'x', at: [3.9 + (i - 1.5) * 0.06, 0.585 + (i - 1) * 0.05, -0.24 + dz].map(r3), color: 'logBark', collision: 'none' });
  }
  box('MantelClock', [0.24, 0.2, 0.1], [3.9, 1.89, -0.4], 'woodDark');
  box('MantelClockFace', [0.14, 0.12, 0.04], [3.9, 1.9, -0.345], 'china');
  for (const [i, x] of [[1, 3.35], [2, 4.45]]) {
    add({ name: `Candle${i}Holder`, shape: 'cylinder', radius: 0.04, height: 0.05, segments: 8, at: [x, 1.815, -0.4], color: 'brass', material: { metalness: 0.6, roughness: 0.4 }, collision: 'none' });
    add({ name: `Candle${i}`, shape: 'cylinder', radius: 0.022, height: 0.2, segments: 6, at: [x, 1.935, -0.4], color: 'china', collision: 'none' });
  }
  picture('PaintingFire', 3.9, 2.55, -0.45, '+z', 0.7, 0.5, 'canvas1');
  picture('PaintingHall', -0.5, 1.8, -0.75, '+z', 0.8, 0.6, 'canvas2');

  // Dining: table with cloth, four chairs, sideboard with lamp and vase.
  clothTable('DiningTable', -3.3, 1.5, 1.5, 0.9, 'cloth');
  chair('DiningChair1', -3.7, 0.74, '+z');
  chair('DiningChair2', -2.9, 0.74, '+z');
  chair('DiningChair3', -3.7, 2.26, '-z');
  chair('DiningChair4', -2.9, 2.26, '-z');
  add({ name: 'DiningVase', shape: 'lathe', profile: [[0.0, F + 0.75], [0.06, F + 0.75], [0.08, F + 0.82], [0.05, F + 0.92], [0.04, F + 0.99], [0.0, F + 0.99]], segments: 8, at: [-3.3, 0, 1.5], color: 'vase', collision: 'none' });
  place('Sideboard', -3.9, -0.525, '+z', [
    ...legs(1.4, 0.45, 0.1, 0.05, 'woodDark'),
    { n: 'Body', s: [1.4, 0.72, 0.45], p: [0, F + 0.46, 0], c: 'wood', x: { collision: 'box' } },
    { n: 'Top', s: [1.46, 0.04, 0.48], p: [0, F + 0.84, -0.015], c: 'woodDark' },
    { n: 'DoorL', s: [0.44, 0.5, 0.04], p: [-0.46, F + 0.42, 0.235], c: 'woodLight' },
    { n: 'DoorM', s: [0.44, 0.5, 0.04], p: [0, F + 0.42, 0.235], c: 'woodLight' },
    { n: 'DoorR', s: [0.44, 0.5, 0.04], p: [0.46, F + 0.42, 0.235], c: 'woodLight' },
    { n: 'Drawer', s: [1.34, 0.12, 0.04], p: [0, F + 0.75, 0.235], c: 'woodLight' },
  ]);
  tableLamp('SideboardLamp', -4.35, F + 0.86, -0.55);
  add({ name: 'SideboardVase', shape: 'lathe', profile: [[0.0, F + 0.86], [0.05, F + 0.86], [0.07, F + 0.95], [0.03, F + 1.08], [0.035, F + 1.12], [0.0, F + 1.12]], segments: 8, at: [-3.5, 0, -0.55], color: 'vase', collision: 'none' });

  // Console radio left of the front door (faces into the room, -z).
  place('Radio', -1.6, 3.65, '-z', [
    { n: 'Cabinet', s: [0.6, 1.0, 0.4], p: [0, F + 0.5, 0], c: 'wood', x: { chamfer: 0.03, collision: 'box' } },
    { n: 'Grille', s: [0.42, 0.36, 0.04], p: [0, F + 0.42, 0.195], c: 'grille' },
    { n: 'DialPanel', s: [0.42, 0.14, 0.04], p: [0, F + 0.8, 0.195], c: 'china' },
  ]);

  // Curtains inside the front window pairs and the side windows, valances over the pairs.
  for (const s of [-1, 1]) {
    box(`CurtainOuter${s < 0 ? 'L' : 'R'}`, [0.3, 1.9, 0.06], [s * 4.4, 2.17, 3.82], 'curtain');
    box(`CurtainInner${s < 0 ? 'L' : 'R'}`, [0.3, 1.9, 0.06], [s * 2.4, 2.17, 3.82], 'curtain');
    box(`Valance${s < 0 ? 'L' : 'R'}`, [2.5, 0.2, 0.1], [s * 3.4, 3.17, 3.79], 'curtain');
    const x = s * 4.92;
    box(`SideCurtainA${s < 0 ? 'L' : 'R'}`, [0.06, 1.9, 0.3], [x, 2.17, 0.545], 'curtain');
    box(`SideCurtainB${s < 0 ? 'L' : 'R'}`, [0.06, 1.9, 0.3], [x, 2.17, -0.545], 'curtain');
  }

  // ======================= KITCHEN (x 0.05..4.95, z -3.85..-0.85) =======================
  box('Linoleum', [4.8, 0.045, 2.9], [2.5, 0.4525, -2.35], 'lino');
  // Base cabinets along the back wall (x 1.85..4.19), sink under the window at x 2.6.
  box('BaseCabinets', [2.34, 0.86, 0.6], [3.02, F + 0.43, -3.55], 'enamel', { collision: 'box' });
  box('Countertop', [2.34, 0.04, 0.64], [3.02, F + 0.88, -3.53], 'counter', { collision: 'box' });
  for (let i = 0; i < 4; i++) {
    const x = 1.89 + 0.27 + i * 0.575;
    box(`CabDoor${i + 1}`, [0.54, 0.48, 0.04], [x, F + 0.34, -3.24], 'enamelDoor');
    box(`CabDrawer${i + 1}`, [0.54, 0.18, 0.04], [x, F + 0.71, -3.24], 'enamelDoor');
    box(`CabHandle${i + 1}`, [0.12, 0.04, 0.05], [x, F + 0.71, -3.21], 'steel', { material: { metalness: 0.7, roughness: 0.35 } });
  }
  box('SinkRim', [0.62, 0.04, 0.46], [2.6, F + 0.905, -3.53], 'steel', { material: { metalness: 0.7, roughness: 0.3 } });
  box('SinkBasin', [0.5, 0.04, 0.34], [2.6, F + 0.915, -3.53], 'steelDark', { material: { metalness: 0.7, roughness: 0.3 } });
  add({ name: 'FaucetStem', shape: 'cylinder', radius: 0.025, height: 0.22, segments: 8, at: [2.6, F + 1.0, -3.79], color: 'steel', material: { metalness: 0.8, roughness: 0.25 }, collision: 'none' });
  box('FaucetSpout', [0.05, 0.05, 0.18], [2.6, F + 1.09, -3.71], 'steel', { material: { metalness: 0.8, roughness: 0.25 } });
  for (const [i, x, rad, h] of [[1, 3.35, 0.08, 0.24], [2, 3.55, 0.07, 0.2], [3, 3.73, 0.06, 0.16]]) {
    add({ name: `Canister${i}`, shape: 'cylinder', radius: rad, height: h, segments: 8, at: [x, F + 0.9 + h / 2 - 0.005, -3.72].map(r3), color: 'canister', collision: 'none' });
  }
  // Enamel range at the right end of the run.
  box('Range', [0.76, 0.91, 0.65], [4.57, F + 0.455, -3.525], 'enamel', { collision: 'box' });
  box('RangeBackguard', [0.76, 0.22, 0.08], [4.57, F + 1.02, -3.81], 'enamel');
  box('RangeOvenDoor', [0.6, 0.45, 0.04], [4.57, F + 0.38, -3.21], 'enamelDoor');
  box('RangeOvenHandle', [0.45, 0.04, 0.05], [4.57, F + 0.65, -3.19], 'steel', { material: { metalness: 0.7, roughness: 0.35 } });
  box('RangeControls', [0.7, 0.08, 0.04], [4.57, F + 0.79, -3.21], 'steelDark');
  for (const [i, dx, z] of [[1, -0.18, -3.33], [2, 0.18, -3.33], [3, -0.18, -3.6], [4, 0.18, -3.6]]) {
    add({ name: `Burner${i}`, shape: 'cylinder', radius: 0.09, height: 0.04, segments: 8, at: [4.57 + dx, F + 0.92, z].map(r3), color: 'steelDark', collision: 'none' });
  }
  add({ name: 'Kettle', shape: 'sphere', radius: [0.1, 0.08, 0.1], detail: 1, at: [4.39, F + 1.01, -3.33], color: 'kettle', material: { metalness: 0.5, roughness: 0.35 }, collision: 'none' });
  // Wall cabinet right of the window (bottom 0.46 m above the counter).
  box('WallCabinet', [1.05, 0.77, 0.33], [3.625, F + 1.745, -3.685], 'enamel', { collision: 'box' });
  box('WallCabDoorL', [0.49, 0.71, 0.04], [3.36, F + 1.745, -3.51], 'enamelDoor');
  box('WallCabDoorR', [0.49, 0.71, 0.04], [3.89, F + 1.745, -3.51], 'enamelDoor');
  // Rounded fridge on the right wall, door facing -x; set forward of the range so the oven stays reachable.
  box('Fridge', [0.7, 1.6, 0.75], [4.6, F + 0.8, -1.65], 'enamel', { chamfer: 0.06, collision: 'box' });
  box('FridgeHandle', [0.05, 0.3, 0.05], [4.23, F + 1.1, -1.375], 'steel', { material: { metalness: 0.7, roughness: 0.35 } });
  box('FridgeBadge', [0.04, 0.05, 0.2], [4.25, F + 1.45, -1.65], 'steelDark');
  // Kitchen table with a gingham cloth and two chairs at the ends, leaving a walkway along the counters.
  clothTable('KitchenTable', 2.6, -1.95, 0.9, 0.75, 'gingham');
  chair('KitchenChair1', 1.92, -1.95, '+x', 'woodLight');
  chair('KitchenChair2', 3.28, -1.95, '-x', 'woodLight');
  // Cafe curtain over the lower half of the sink window.
  box('KitchenCurtain', [0.79, 0.4, 0.06], [2.6, F + 1.35, -3.81], 'gingham');

  // ======================= BEDROOM (x -4.95..-0.05, z -3.85..-0.85) =======================
  box('Carpet', [4.8, 0.05, 2.9], [-2.5, 0.455, -2.35], 'carpet');
  // Full-size bed, head against the left wall.
  const BZc = -2.4;
  box('BedBase', [1.93, 0.2, 1.42], [-3.935, F + 0.3, BZc], 'woodDark', { collision: 'box' });
  for (const [i, x, z] of [[1, -4.85, BZc - 0.66], [2, -4.85, BZc + 0.66], [3, -3.02, BZc - 0.66], [4, -3.02, BZc + 0.66]]) {
    box(`BedLeg${i}`, [0.06, 0.21, 0.06], [x, F + 0.095, z], 'woodDark');
  }
  box('Mattress', [1.91, 0.22, 1.37], [-3.93, F + 0.51, BZc], 'linen', { chamfer: 0.04 });
  box('Blanket', [1.39, 0.27, 1.43], [-3.635, F + 0.505, BZc], 'quilt', { chamfer: 0.03 });
  box('PillowA', [0.4, 0.12, 0.6], [-4.62, F + 0.67, BZc - 0.33], 'linen', { chamfer: 0.04 });
  box('PillowB', [0.4, 0.12, 0.6], [-4.62, F + 0.67, BZc + 0.33], 'linen', { chamfer: 0.04 });
  add({
    name: 'Headboard', shape: 'extrude', plane: 'zy', depth: 0.06, at: [-4.915, 0, 0], color: 'woodDark', collision: 'box',
    outline: [[BZc - 0.73, F], [BZc - 0.73, 1.35], [BZc - 0.5, 1.5], [BZc, 1.56], [BZc + 0.5, 1.5], [BZc + 0.73, 1.35], [BZc + 0.73, F]].map(([u, v]) => [r3(u), r3(v)]),
  });
  add({
    name: 'Footboard', shape: 'extrude', plane: 'zy', depth: 0.05, at: [-2.95, 0, 0], color: 'woodDark', collision: 'box',
    outline: [[BZc - 0.73, F], [BZc - 0.73, 1.05], [BZc, 1.15], [BZc + 0.73, 1.05], [BZc + 0.73, F]].map(([u, v]) => [r3(u), r3(v)]),
  });
  // Nightstands (top level with the mattress) with lamps.
  for (const [i, z] of [[1, -3.5], [2, -1.3]]) {
    place(`Nightstand${i}`, -4.75, z, '+x', [
      { n: 'Body', s: [0.5, 0.6, 0.4], p: [0, F + 0.3, 0], c: 'wood', x: { collision: 'box' } },
      { n: 'Drawer', s: [0.42, 0.14, 0.04], p: [0, F + 0.47, 0.195], c: 'woodLight' },
    ]);
    tableLamp(`BedLamp${i}`, -4.78, F + 0.6, z);
  }
  // Dresser against the centre partition, facing -x, with a round mirror.
  place('Dresser', -0.3, -2.0, '-x', [
    { n: 'Body', s: [1.2, 0.85, 0.5], p: [0, F + 0.425, 0], c: 'wood', x: { collision: 'box' } },
    { n: 'Drawer1', s: [1.1, 0.22, 0.04], p: [0, F + 0.17, 0.245], c: 'woodLight' },
    { n: 'Drawer2', s: [1.1, 0.22, 0.04], p: [0, F + 0.42, 0.245], c: 'woodLight' },
    { n: 'Drawer3', s: [1.1, 0.22, 0.04], p: [0, F + 0.67, 0.245], c: 'woodLight' },
  ]);
  add({ name: 'MirrorFrame', shape: 'cylinder', radius: 0.37, height: 0.04, segments: 12, axis: 'x', at: [-0.11, 1.75, -2.0], color: 'woodDark', collision: 'none' });
  add({ name: 'MirrorGlass', shape: 'cylinder', radius: 0.32, height: 0.05, segments: 12, axis: 'x', at: [-0.1, 1.75, -2.0], color: 'mirror', material: { metalness: 0.9, roughness: 0.1 }, collision: 'none' });
  box('MirrorPostA', [0.04, 0.5, 0.04], [-0.12, F + 0.85 + 0.25, -2.38], 'woodDark');
  box('MirrorPostB', [0.04, 0.5, 0.04], [-0.12, F + 0.85 + 0.25, -1.62], 'woodDark');
  // Wardrobe against the back wall.
  place('Wardrobe', -0.8, -3.55, '+z', [
    { n: 'Body', s: [1.0, 1.9, 0.6], p: [0, F + 0.95, 0], c: 'wood', x: { collision: 'box' } },
    { n: 'Crown', s: [1.06, 0.06, 0.64], p: [0, F + 1.93, 0.01], c: 'woodDark' },
    { n: 'DoorL', s: [0.47, 1.7, 0.04], p: [-0.245, F + 0.95, 0.295], c: 'woodLight' },
    { n: 'DoorR', s: [0.47, 1.7, 0.04], p: [0.245, F + 0.95, 0.295], c: 'woodLight' },
    { n: 'KnobL', s: [0.04, 0.12, 0.05], p: [-0.04, F + 1.0, 0.32], c: 'brass' },
    { n: 'KnobR', s: [0.04, 0.12, 0.05], p: [0.04, F + 1.0, 0.32], c: 'brass' },
  ]);
  box('BedCurtainA', [0.3, 1.9, 0.06], [-3.15, 2.17, -3.82], 'curtainBed');
  box('BedCurtainB', [0.3, 1.9, 0.06], [-2.05, 2.17, -3.82], 'curtainBed');
  picture('PaintingBed', -4.95, 2.0, BZc, '+x', 0.6, 0.45, 'canvas3');
};

// Ceiling lights hang from the ceiling, so they belong to the roof group (hidden / lifted with it).
module.exports.ceilingLights = function addCeilingLights(parts, r3) {
  const add = p => { parts.push(p); return p; };
  const lights = [['LampDining', -3.3, 1.5], ['LampLiving', 1.0, 1.4], ['LampKitchen', 2.6, -2.3]];
  for (const [n, x, z] of lights) {
    add({ name: n + 'Canopy', shape: 'cylinder', radius: 0.08, height: 0.05, segments: 8, at: [x, 3.27, z], color: 'brass', material: { metalness: 0.6, roughness: 0.4 }, collision: 'none' });
    add({ name: n + 'Cord', shape: 'cylinder', radius: 0.022, height: 0.5, segments: 6, at: [x, 3.0, z], color: 'flue', collision: 'none' });
    if (n === 'LampKitchen') {
      add({ name: n + 'Globe', shape: 'sphere', radius: 0.15, detail: 1, at: [x, 2.65, z], color: 'shade', material: { emissive: 'glowWarm' }, collision: 'none' });
    } else {
      add({ name: n + 'Shade', shape: 'cone', radius: [0.28, 0.07], height: 0.22, segments: 8, at: [x, 2.65, z], color: 'shade', material: { emissive: 'glowWarm' }, collision: 'none' });
    }
  }
  add({ name: 'LampBedroom', shape: 'sphere', radius: [0.22, 0.09, 0.22], detail: 1, at: [-2.5, 3.25, -2.35], color: 'shade', material: { emissive: 'glowWarm' }, collision: 'none' });
  return ['LampDining', 'LampLiving', 'LampKitchen'].flatMap(n => [n + 'Canopy', n + 'Cord', n + (n === 'LampKitchen' ? 'Globe' : 'Shade')]).concat(['LampBedroom']);
};
