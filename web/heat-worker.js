/* Offscreen heat rasteriser. The main thread keeps map projection and labels;
   this worker only turns already-projected route shapes into the padded bitmap. */
"use strict";

const HEAT_SCALE = 0.4;
const RAMP = [
  [0.00, [244, 196, 13]],
  [0.26, [238, 159, 24]],
  [0.50, [230, 111, 26]],
  [0.74, [209, 51, 25]],
  [1.00, [150, 13, 10]],
];

const RAMP_LUT = (() => {
  const lut = new Uint8Array(256 * 3);
  for (let i = 0; i < 256; i++) {
    const v = i / 255;
    let colour = RAMP[RAMP.length - 1][1];
    for (let j = 1; j < RAMP.length; j++) {
      if (v <= RAMP[j][0]) {
        const [t0, c0] = RAMP[j - 1];
        const [t1, c1] = RAMP[j];
        const f = (v - t0) / (t1 - t0 || 1);
        colour = [0, 1, 2].map((k) => Math.round(c0[k] + (c1[k] - c0[k]) * f));
        break;
      }
    }
    lut[i * 3] = colour[0];
    lut[i * 3 + 1] = colour[1];
    lut[i * 3 + 2] = colour[2];
  }
  return lut;
})();

function cumulativeLengths(pts) {
  const cum = [0];
  for (let i = 1; i < pts.length; i++) {
    cum.push(cum[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
  }
  return cum;
}

function stampAlong(c, sprite, pts, cum, count, radius) {
  const total = cum[cum.length - 1] || 0;
  let seg = 1;
  for (let k = 0; k <= count; k++) {
    const target = total * k / count;
    while (seg < pts.length - 1 && cum[seg] < target) seg++;
    const a = pts[seg - 1], b = pts[seg] || a;
    const span = cum[seg] - cum[seg - 1];
    const f = span ? Math.min(1, Math.max(0, (target - cum[seg - 1]) / span)) : 0;
    const x = a[0] + (b[0] - a[0]) * f;
    const y = a[1] + (b[1] - a[1]) * f;
    c.drawImage(sprite, x - radius, y - radius, radius * 2, radius * 2);
  }
}

function makeHeatSprite(midStop) {
  const size = 64;
  const canvas = new OffscreenCanvas(size, size);
  const c = canvas.getContext("2d");
  const g = c.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(midStop, "rgba(255,255,255,.5)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  c.fillStyle = g;
  c.fillRect(0, 0, size, size);
  return canvas;
}

let heatSprite = null;
let homeSprite = null;

function deposit(half, shapes, zoom, quality) {
  const c = half.getContext("2d");
  if (!heatSprite) heatSprite = makeHeatSprite(0.45);
  if (!homeSprite) homeSprite = makeHeatSprite(0.55);
  const lens = shapes.map((s) => cumulativeLengths(s.pts).at(-1) || 0);
  const density = shapes.map((s, i) => Math.max(1, s.people) / Math.max(80, lens[i]));
  const top = Math.max(1e-6, ...density);
  const topPeople = Math.max(1, ...shapes.map((s) => Math.max(1, s.people)));
  shapes.forEach((s, i) => {
    const cum = cumulativeLengths(s.pts);
    const len = cum[cum.length - 1] || 0;
    const weight = Math.pow(Math.min(1, density[i] / top), 0.6);
    const sampleCap = Math.round(180 * quality);
    const n = Math.max(6, Math.min(sampleCap, Math.round(len / 7 * quality)));
    const zoomBoost = Math.min(2.4, Math.max(0.6, Math.pow(2, 13.2 - zoom)));
    const radius = (6 + 7.5 * weight) * zoomBoost;
    const alpha = 0.10 + 0.27 * weight;
    const home = s.pts[0];
    const share = Math.pow(Math.max(1, s.people) / topPeople, 0.6);
    const homeRadius = (7 + 12 * share) * zoomBoost;
    c.globalAlpha = 0.1 + 0.3 * share;
    c.drawImage(homeSprite, home[0] - homeRadius, home[1] - homeRadius, homeRadius * 2, homeRadius * 2);
    c.globalAlpha = alpha;
    stampAlong(c, heatSprite, s.pts, cum, n, radius);
    c.globalAlpha = 1;
  });
}

function colourise(half, ctx, map, maxAlpha, magnitude) {
  const c = half.getContext("2d");
  const img = c.getImageData(0, 0, half.width, half.height);
  const d = img.data;
  const hist = new Uint32Array(256);
  let sampled = 0;
  for (let i = 3; i < d.length; i += 4 * 7) {
    if (d[i]) { hist[d[i]]++; sampled++; }
  }
  if (!sampled) return;
  let top = 28, seen = 0;
  const target = Math.ceil(sampled * 0.97);
  for (let a = 1; a < 256; a++) {
    seen += hist[a];
    if (seen >= target) { top = Math.max(28, a); break; }
  }
  for (let i = 0; i < d.length; i += 4) {
    const a = d[i + 3];
    if (!a) continue;
    const t = Math.min(1, Math.pow(a / top, 0.8));
    const idx = Math.round(t * 255) * 3;
    d[i] = RAMP_LUT[idx]; d[i + 1] = RAMP_LUT[idx + 1]; d[i + 2] = RAMP_LUT[idx + 2];
    d[i + 3] = Math.min(255, Math.round(t * maxAlpha * (magnitude == null ? 1 : magnitude)));
  }
  c.putImageData(img, 0, 0);
  ctx.save();
  ctx.imageSmoothingEnabled = true;
  ctx.drawImage(half, 0, 0, map.w, map.h);
  ctx.restore();
}

self.onmessage = (event) => {
  const { id, width, height, zoom, quality, magnitude, shapes } = event.data;
  try {
    const full = new OffscreenCanvas(width, height);
    const ctx = full.getContext("2d");
    const scale = quality < 1 ? HEAT_SCALE * 0.7 : HEAT_SCALE;
    const half = new OffscreenCanvas(
      Math.max(1, Math.round(width * scale)),
      Math.max(1, Math.round(height * scale))
    );
    const hc = half.getContext("2d");
    hc.globalCompositeOperation = "lighter";
    hc.scale(scale, scale);
    deposit(half, shapes, zoom, quality);
    colourise(half, ctx, { w: width, h: height }, 235, magnitude);
    const bitmap = full.transferToImageBitmap();
    self.postMessage({ id, bitmap, width, height }, [bitmap]);
  } catch (err) {
    self.postMessage({ id, error: String(err && err.message || err) });
  }
};
