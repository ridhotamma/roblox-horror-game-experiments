// Hand-drawn leaf cluster for the StylizedTree alpha cards (one texture, re-used on every card).
// A round clump of almond leaves fanning out from the middle, in three depth layers (back = dark, front = light),
// each layer casting a soft shadow on the one behind it, with a midrib on every leaf and a drawn ink outline.
// The silhouette is a ragged circle so that cards overlapping at random angles read as one fluffy canopy.
//   node ~/.claude/skills/roblox-2d-art/scripts/rart.mjs build art/leaf_cluster.art.mjs --out textures
export default (k) => {
  const S = 1024, C = S / 2;
  const rnd = k.rng(7);

  // almond leaf, base at (0,0), tip at (0,-L), half-width w
  const leafD = (L, w) =>
    `M0 0 C${w * 1.15} ${-L * 0.22} ${w * 0.95} ${-L * 0.72} 0 ${-L} C${-w * 0.95} ${-L * 0.72} ${-w * 1.15} ${-L * 0.22} 0 0Z`;

  // a scatter of n leaves: bases spread over a disc of radius R (golden-angle spiral + jitter, so the clump is
  // filled with no hole in the middle), each pointing roughly away from the centre with up to +-jit/2 degrees of
  // wobble, length L. `bias` [x, y] pushes the layer toward one side (front leaves toward the light).
  function scatter(n, R, L, w, jit, seedSpin, bias = [0, 0]) {
    const out = [];
    for (let i = 0; i < n; i++) {
      const r = R * Math.sqrt((i + 0.5) / n) * (0.85 + rnd() * 0.3);
      const t = i * 137.508 + seedSpin;
      const rad = (t * Math.PI) / 180;
      const x = C + bias[0] + Math.sin(rad) * r, y = C + bias[1] - Math.cos(rad) * r;
      const out_a = (Math.atan2(x - C, -(y - C)) * 180) / Math.PI;     // direction away from the centre (0 = up)
      const a = (r < 30 ? rnd() * 360 : out_a) + (rnd() - 0.5) * jit;
      const len = L * (0.8 + rnd() * 0.35), wid = w * (0.85 + rnd() * 0.3);
      out.push({ x, y, a, len, wid });
    }
    return out;
  }
  const leafPath = (l) => `<path transform="translate(${l.x.toFixed(1)} ${l.y.toFixed(1)}) rotate(${l.a.toFixed(1)})" d="${leafD(l.len, l.wid)}"/>`;
  const ribPath = (l) =>
    `<path transform="translate(${l.x.toFixed(1)} ${l.y.toFixed(1)}) rotate(${l.a.toFixed(1)})" d="M0 ${-l.len * 0.06} Q${l.wid * 0.12} ${-l.len * 0.45} 0 ${-l.len * 0.84}" fill="none" stroke-width="5" stroke-linecap="round"/>`;

  const back = scatter(26, 250, 210, 62, 70, 10);
  const mid = scatter(18, 210, 175, 56, 80, 50, [-10, -10]);
  // front: fewer, shorter leaves, shifted toward the light (top-left)
  const front = scatter(10, 160, 140, 50, 90, 95, [-45, -45]);

  const group = (leaves, fill) => `<g fill="${fill}">${leaves.map(leafPath).join('')}</g>`;
  const ribs = (leaves, stroke) => `<g stroke="${stroke}" opacity="0.75">${leaves.map(ribPath).join('')}</g>`;

  const G = { back: '#3d7a3a', mid: '#5c9e40', front: '#86c246' };
  const shade = { style: 'toon', depth: 34, shadowArea: 0.4, hueShift: 26, spec: 0.12 };
  return {
    set: { kind: 'item', light: 'tl' },
    assets: [{
      name: 'leaf_cluster',
      size: 1024,
      fit: { pad: 0.03 },
      outline: { width: 10, color: 'auto' },
      shadow: null,                                   // a drop shadow would float off the card
      export: { sizes: [512] },
      layers: [
        { name: 'back', svg: group(back, G.back), shade, outline: { width: 5, color: 'auto' } },
        { name: 'backRibs', clip: 'back', svg: ribs(back, '#1f4a2a') },
        { name: 'mid', svg: group(mid, G.mid), shade, outline: { width: 5, color: 'auto' }, cast: { dy: 14, dx: 8, blur: 10, opacity: 0.4 } },
        { name: 'midRibs', clip: 'mid', svg: ribs(mid, '#2f6a2c') },
        { name: 'front', svg: group(front, G.front), shade, outline: { width: 5, color: 'auto' }, cast: { dy: 12, dx: 7, blur: 9, opacity: 0.4 } },
        { name: 'frontRibs', clip: 'front', svg: ribs(front, '#4d8a32') },
      ],
    }],
  };
};
