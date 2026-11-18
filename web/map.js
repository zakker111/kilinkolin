/* Kilinkolin — one estimated heat map: where the crowd comes from, or how it arrives.
   OpenStreetMap tiles on a canvas, our own projection, our own heat. No SDK, no key. */
(() => {
  "use strict";
  const CFG = window.KILINKOLIN || {};
  const TILE = 256;
  const HEAT_SCALE = 0.4;
  // Pan the existing heat bitmap while the camera stays inside this margin.
  // A full 600 px drag then stays on the cached bitmap instead of restamping
  // every street on every animation frame.
  const HEAT_PAD = 640;
  const MOBILE = window.matchMedia("(max-width: 700px), (pointer: coarse) and (max-width: 1024px), (max-width: 1000px) and (max-height: 520px)").matches;
  document.documentElement.classList.toggle("is-mobile", MOBILE);
  document.documentElement.dataset.mobile = MOBILE ? "true" : "false";

  const S = { events: [], flows: {}, venues: {}, routes: {}, map: null, dotHits: [],
              hoverId: null, onHover: null, day: null, minutes: 19 * 60,
              aggVersion: 0, heatLayer: null, heatView: null, heatAggVersion: -1, heatQuality: -1,
              heatShapes: null, labelShapes: [], shapes: [], zooming: false, scrubbing: false,
              worker: undefined, heatRequestId: 0, heatPendingKey: null, heatRequestMeta: null,
              dayList: [], sortedLegs: null, sortedLegsVersion: -1,
              sortedVenues: null, sortedVenuesVersion: -1, fullFlows: false };
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

  /* ------------------------------------------------------------ tile map */
  class TileMap {
    constructor(canvas) {
      this.canvas = canvas;
      this.ctx = canvas.getContext("2d");
      this.center = { lat: 61.4978, lon: 23.7610 };
      this.zoom = 12.2;
      this.minZoom = 8;
      this.maxZoom = 16.5;
      this.tiles = new Map();
      this.tileLayer = null;
      this.tileKey = null;
      this.paint = null;
      this._z = 12; this._scale = 1; this._ox = 0; this._oy = 0;
      this._zoomRaf = null;
      this._low = false;
      this._lowTimer = null;
      this._bind();
      this.resize();
    }
    resize() {
      const w = this.canvas.clientWidth || 800;
      const h = this.canvas.clientHeight || 520;
      // Large canvases are fill-rate bound; 1.5x is visually ample for the heat
      // and keeps retina desktops from painting 2x the pixels every frame.
      this.baseDpr = Math.min(window.devicePixelRatio || 1, MOBILE ? 1.75 : (w * h > 900000 ? 1.5 : 2));
      const dpr = this._low ? Math.min(this.baseDpr, MOBILE ? 1.2 : 1.5) : this.baseDpr;
      this.w = w; this.h = h; this.dpr = dpr;
      this.canvas.width = Math.round(w * dpr);
      this.canvas.height = Math.round(h * dpr);
      this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      this.schedule();
    }
    setLowRes(on) {
      if (this._low === on) return;
      this._low = on;
      this.resize();
    }
    startInteraction() {
      clearTimeout(this._lowTimer);
      this.setLowRes(true);
    }
    endInteraction(delay = 120) {
      clearTimeout(this._lowTimer);
      this._lowTimer = setTimeout(() => this.setLowRes(false), delay);
    }
    worldX(lon, z) { return (lon + 180) / 360 * TILE * Math.pow(2, z); }
    worldY(lat, z) {
      const s = Math.sin(Math.max(-85, Math.min(85, lat)) * Math.PI / 180);
      return (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * TILE * Math.pow(2, z);
    }
    lonAt(x, z) { return x / (TILE * Math.pow(2, z)) * 360 - 180; }
    latAt(y, z) {
      const n = Math.PI - 2 * Math.PI * y / (TILE * Math.pow(2, z));
      return 180 / Math.PI * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)));
    }
    project(lat, lon) {
      return { x: this.worldX(lon, this._z) * this._scale - this._ox, y: this.worldY(lat, this._z) * this._scale - this._oy };
    }
    unproject(px, py) {
      return { lon: this.lonAt((px + this._ox) / this._scale, this._z), lat: this.latAt((py + this._oy) / this._scale, this._z) };
    }
    schedule() {
      if (this._raf) return;
      this._raf = requestAnimationFrame(() => { this._raf = null; this.draw(); });
    }
    hitAt(x, y) {
      return S.dotHits.find((h) => Math.hypot(h.x - x, h.y - y) < 16) || null;
    }
    /* hovering a dot names the event; dragging still pans */
    _hover(e) {
      const r = this.canvas.getBoundingClientRect();
      const mx = e.clientX - r.left, my = e.clientY - r.top;
      const hit = this.hitAt(mx, my);
      this.canvas.style.cursor = hit ? "pointer" : "grab";
      const id = hit ? hit.ev.id : null;
      if (id === S.hoverId) {
        if (hit) showTipAt(mx, my, hit); else if (S.hideTip) S.hideTip();
        return;
      }
      S.hoverId = id;
      if (hit) showTipAt(mx, my, hit);
      else if (S.hideTip) S.hideTip();
      if (S.onHover) S.onHover(id);
      this.schedule();
    }
    draw() {
      const z = Math.max(3, Math.min(CFG.TILE_MAX_ZOOM || 18, Math.round(this.zoom)));
      const scale = Math.pow(2, this.zoom - z);
      const ts = TILE * scale;
      const ox = this.worldX(this.center.lon, z) * scale - this.w / 2;
      const oy = this.worldY(this.center.lat, z) * scale - this.h / 2;
      this._z = z; this._scale = scale; this._ox = ox; this._oy = oy;

      const ctx = this.ctx;
      const tileKey = `${z}|${scale}|${ox}|${oy}|${this.w}|${this.h}`;
      if (!this.tileLayer) this.tileLayer = document.createElement("canvas");
      const tw = Math.max(1, Math.round(this.w));
      const th = Math.max(1, Math.round(this.h));
      let painted = 0;
      if (this.tileKey !== tileKey || this.tileLayer.width !== tw || this.tileLayer.height !== th) {
        this.tileLayer.width = tw;
        this.tileLayer.height = th;
        const tc = this.tileLayer.getContext("2d");
        tc.setTransform(1, 0, 0, 1, 0, 0);
        tc.fillStyle = "#e7e2d6";
        tc.fillRect(0, 0, tw, th);
        const n = Math.pow(2, z);
        const x0 = Math.floor(ox / ts), x1 = Math.floor((ox + this.w) / ts);
        const y0 = Math.floor(oy / ts), y1 = Math.floor((oy + this.h) / ts);
        for (let x = x0; x <= x1; x++) {
          for (let y = y0; y <= y1; y++) {
            if (y < 0 || y >= n) continue;
            const tx = ((x % n) + n) % n;
            const img = this.tile(z, tx, y);
            if (!img) continue;
            tc.drawImage(img, Math.round(x * ts - ox), Math.round(y * ts - oy), Math.ceil(ts) + 1, Math.ceil(ts) + 1);
            painted++;
          }
        }
        this.tileKey = tileKey;
      } else {
        painted = 1;
      }
      ctx.drawImage(this.tileLayer, 0, 0, this.w, this.h);
      if (painted) {
        const loading = $("mapLoading");
        if (loading && loading.style.display !== "none") {
          loading.style.opacity = "0";
          setTimeout(() => { loading.style.display = "none"; }, 260);
        }
        this.canvas.classList.add("ready");
      }
      if (this.paint) this.paint(ctx, this);
    }
    tile(z, x, y) {
      const key = z + "/" + x + "/" + y;
      let rec = this.tiles.get(key);
      if (!rec) {
        const img = new Image();
        img.crossOrigin = "anonymous";
        img.addEventListener("load", () => { this.tileKey = null; this.schedule(); });
        img.src = (CFG.TILE_URL || "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
          .replace("{z}", z).replace("{x}", x).replace("{y}", y);
        rec = { img };
        this.tiles.set(key, rec);
        return null;
      }
      return rec.img.complete && rec.img.naturalWidth ? rec.img : null;
    }
    setCenter(lat, lon, zoom) {
      this.center = { lat, lon };
      if (zoom) this.zoom = Math.max(this.minZoom, Math.min(this.maxZoom, zoom));
      this.schedule();
    }
    zoomBy(d) {
      this.zoomTo(this.zoom + d);
    }
    zoomTo(target) {
      const end = Math.max(this.minZoom, Math.min(this.maxZoom, target));
      const start = this.zoom, t0 = performance.now();
      if (this._zoomRaf) cancelAnimationFrame(this._zoomRaf);
      S.zooming = true;
      this.startInteraction();
      const step = (now) => {
        const k = Math.min(1, (now - t0) / 240);
        const eased = 1 - Math.pow(1 - k, 3);
        this.zoom = start + (end - start) * eased;
        this.draw();
        if (k < 1) this._zoomRaf = requestAnimationFrame(step);
        else {
          this._zoomRaf = null;
          S.zooming = false;
          this.endInteraction(0);
          // One fresh raster after the animation, not one per zoom frame.
          S.heatView = null;
          S.heatAggVersion = -1;
          this.schedule();
        }
      };
      this._zoomRaf = requestAnimationFrame(step);
    }
    _bind() {
      const c = this.canvas;
      c.style.cursor = "grab";
      let drag = null, down = null;
      c.addEventListener("pointerdown", (e) => {
        drag = { x: e.clientX, y: e.clientY };
        down = { x: e.clientX, y: e.clientY, t: Date.now() };
        c.setPointerCapture(e.pointerId);
        c.style.cursor = "grabbing";
        this.startInteraction();
        if (S.hideTip) S.hideTip();
      });
      c.addEventListener("pointermove", (e) => {
        if (!drag) { this._hover(e); return; }
        const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
        drag = { x: e.clientX, y: e.clientY };
        const cx = this.worldX(this.center.lon, this._z) - dx / this._scale;
        const cy = this.worldY(this.center.lat, this._z) - dy / this._scale;
        this.center = { lon: this.lonAt(cx, this._z), lat: this.latAt(cy, this._z) };
        this.schedule();
      });
      const end = (e) => {
        const wasTap = down && e && Math.hypot((e.clientX || 0) - down.x, (e.clientY || 0) - down.y) < 8 && Date.now() - down.t < 700;
        drag = null; down = null; c.style.cursor = "grab";
        this.endInteraction();
        this.schedule();
        if (wasTap && this.onTap) this.onTap(e);
      };
      c.addEventListener("pointerup", end);
      c.addEventListener("pointercancel", () => end(null));
      c.addEventListener("pointerleave", (e) => {
        if (drag) return;
        // a finger lifts straight after a tap, so the touch pointer leaves and
        // this would undo the selection that tap just made; only a pointer that
        // can hover should clear the dot it left
        if (e && e.pointerType === "touch") return;
        S.hoverId = null;
        if (S.hideTip) S.hideTip();
        if (S.onHover) S.onHover(null);
        this.schedule();
      });
      c.addEventListener("wheel", (e) => {
        e.preventDefault();
        const r = c.getBoundingClientRect();
        const mx = e.clientX - r.left, my = e.clientY - r.top;
        const before = this.unproject(mx, my);
        this.startInteraction();
        this.zoom = Math.max(this.minZoom, Math.min(this.maxZoom, this.zoom - e.deltaY * 0.0025));
        const after = this.unproject(mx, my);
        this.center = { lat: this.center.lat + (before.lat - after.lat), lon: this.center.lon + (before.lon - after.lon) };
        this.endInteraction(180);
        this.schedule();
      }, { passive: false });
      window.addEventListener("resize", () => this.resize());
    }
  }

  /* ------------------------------------------------------------- helpers */
  /* ----------------------------------------------------- density renderer
     Walking traffic is drawn as a density field, not as lines: intensity is
     deposited along every street, then mapped through the palette. */
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
      cum.push(cum[i - 1] + Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y));
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
      const x = a.x + (b.x - a.x) * f, y = a.y + (b.y - a.y) * f;
      c.drawImage(sprite, x - radius, y - radius, radius * 2, radius * 2);
    }
  }

  /* reduced-resolution buffer: smooth heat, cheap to colourise every frame */
  function ensureHalf(map, scale = HEAT_SCALE) {
    const w = Math.max(1, Math.round(map.w * scale));
    const h = Math.max(1, Math.round(map.h * scale));
    if (!S.half) S.half = document.createElement("canvas");
    if (S.half.width !== w || S.half.height !== h) { S.half.width = w; S.half.height = h; }
    const c = S.half.getContext("2d");
    c.setTransform(1, 0, 0, 1, 0, 0);
    c.clearRect(0, 0, w, h);
    c.globalCompositeOperation = "lighter";
    c.scale(scale, scale);
    return S.half;
  }

  let heatSprite = null, homeSprite = null;
  function makeHeatSprite(midStop) {
    const size = 64;
    const canvas = document.createElement("canvas");
    canvas.width = size; canvas.height = size;
    const c = canvas.getContext("2d");
    const g = c.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
    g.addColorStop(0, "rgba(255,255,255,1)");
    g.addColorStop(midStop, "rgba(255,255,255,.5)");
    g.addColorStop(1, "rgba(255,255,255,0)");
    c.fillStyle = g;
    c.fillRect(0, 0, size, size);
    return canvas;
  }

  function deposit(half, shapes, zoom, quality = 1) {
    const c = half.getContext("2d");
    if (!heatSprite) heatSprite = makeHeatSprite(0.45);
    if (!homeSprite) homeSprite = makeHeatSprite(0.55);
    // traffic concentration: people per metre of street, not per route
    const lens = shapes.map((s) => s.cum[s.cum.length - 1] || 0);
    const density = shapes.map((s, i) => Math.max(1, s.people) / Math.max(80, lens[i]));
    const top = Math.max(1e-6, ...density);
    const topPeople = Math.max(1, ...shapes.map((s) => Math.max(1, s.people)));
    shapes.forEach((s, i) => {
      const len = lens[i];
      // sqrt-ish: a long approach with few people still needs to be seen
      const weight = Math.pow(Math.min(1, density[i] / top), 0.6);
      const sampleCap = Math.round((MOBILE ? 120 : 180) * quality);
      const n = Math.max(6, Math.min(sampleCap, Math.round(len / 7 * quality)));
      // wider kernels when zoomed out, so long approaches read as heat and not as hairlines
      const zoomBoost = Math.min(2.4, Math.max(0.6, Math.pow(2, 13.2 - zoom)));
      const radius = (6 + 7.5 * weight) * zoomBoost;
      const alpha = 0.10 + 0.27 * weight;
      // origin patch: where this part of the crowd comes from. Sized by people, not by
      // walk length, so a distant district still reads as a source area.
      const home = s.pts[0];
      const share = Math.pow(Math.max(1, s.people) / topPeople, 0.6);
      const homeRadius = (7 + 12 * share) * zoomBoost;
      c.globalAlpha = 0.1 + 0.3 * share;
      c.drawImage(homeSprite, home.x - homeRadius, home.y - homeRadius, homeRadius * 2, homeRadius * 2);

      // A cached alpha sprite is much cheaper than creating a radial gradient for every
      // sample point, and it preserves the same additive heat profile.
      c.globalAlpha = alpha;
      stampAlong(c, heatSprite, s.pts, s.cum, n, radius);
      c.globalAlpha = 1;
    });
  }

  function colourise(half, ctx, map, maxAlpha, magnitude) {
    const c = half.getContext("2d");
    const img = c.getImageData(0, 0, half.width, half.height);
    const d = img.data;
    // normalise against a high percentile, not the maximum: one saturated core would
    // otherwise flatten every approach street to nothing. A 256-bin histogram avoids
    // allocating and sorting a sampled array on every frame.
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
      // magnitude keeps a quiet hour quiet: three people should not paint the whole city
      d[i + 3] = Math.min(255, Math.round(t * maxAlpha * (magnitude == null ? 1 : magnitude)));
    }
    c.putImageData(img, 0, 0);
    ctx.save();
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(half, 0, 0, map.w, map.h);
    ctx.restore();
  }

  function drawTrafficHeat(ctx, map, shapes, magnitude, quality = 1) {
    if (!shapes.length) return;
    const scale = quality < 1 ? HEAT_SCALE * 0.7 : HEAT_SCALE;
    const half = ensureHalf(map, scale);
    deposit(half, shapes, map.zoom, quality);
    colourise(half, ctx, map, 235, magnitude);
  }

  /* ------------------------------------------------------------- aggregate */
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

  function dayLabel(iso) {
    const p = (iso || "").split("-");
    if (p.length !== 3) return iso || "";
    const d = new Date(+p[0], +p[1] - 1, +p[2]);
    return `${DOW[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]}`;
  }

  function addDays(iso, delta) {
    const p = (iso || "").split("-");
    if (p.length !== 3) return iso;
    const d = new Date(+p[0], +p[1] - 1, +p[2] + delta);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  }

  function clockLabel(min) {
    const m = ((Math.round(min) % 1440) + 1440) % 1440;
    return String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0");
  }

  function parseMin(s) {
    const m = /^(\d{1,2}):(\d{2})$/.exec(s || "");
    if (!m) return null;
    let v = +m[1] * 60 + +m[2];
    if (v < 6 * 60) v += 24 * 60;   // after-midnight starts belong to the previous night
    return v;
  }

  /* the chosen day's strip runs to 06:00 the next morning: label those starts +1.
     A missing start is shown as TBA with its documented heat window, never as a
     published 19:00. */
  function eventClock(ev) {
    const flow = S.flows[ev.id] || {};
    if (ev.timeKnown === false) {
      return flow.start_window ? `TBA · ${flow.start_window}` : "TBA";
    }
    const start = flow.start != null ? flow.start : parseMin(ev.time);
    if (start == null) return ev.time || "";
    return clockLabel(start) + (start >= 24 * 60 ? " +1" : "");
  }

  /* each curve entry is a share spread over its slot (15 minutes unless the build says
     otherwise), so a chosen minute can take a fraction of the slot instead of snapping
     to a boundary it never lands on. */
  function sliceShare(curve, from, to) {
    let sum = 0;
    (curve || []).forEach((c) => {
      const span = c.span || 15;
      const lo = Math.max(c.t, from), hi = Math.min(c.t + span, to);
      if (hi > lo) sum += c.share * (hi - lo) / span;
    });
    return Math.min(1, Math.max(0, sum));
  }

  /* people on a route in the 15 minutes up to `now`: travelling in before the start,
     or heading home after the estimated end. A TBA flow carries several candidate
     starts, so its curves are averaged instead of pinning the heat to one peak. */
  function enRoute(flow, now, startMin) {
    const mid = Number(flow.attendance && flow.attendance.mid);
    if (!Number.isFinite(mid) || mid <= 0) return 0;
    const starts = (flow.start_options && flow.start_options.length)
      ? flow.start_options : [startMin];
    const base = flow.start != null ? flow.start : startMin;
    // old cached flows have no end; they simply count arrivals until the next build
    const endOffset = flow.end != null ? flow.end - base : null;
    let arrive = 0, leave = 0;
    starts.forEach((start) => {
      arrive += sliceShare(flow.arrival, now - start - 15, now - start);
      if (endOffset != null) {
        const end = start + endOffset;
        leave += sliceShare(flow.egress, now - end - 15, now - end);
      }
    });
    arrive /= starts.length;
    leave /= starts.length;
    return mid * Math.min(1, arrive + leave);
  }

  function aggregate() {
    const now = S.minutes;
    const out = { people: 0, events: 0, legs: new Map(), venues: new Map() };
    if (!S.day) return out;
    S.events.forEach((ev) => {
      if (ev.date !== S.day) return;
      const flow = S.flows[ev.id];
      if (!flow) return;
      const start = parseMin(ev.time);
      if (start == null) return;
      const weight = enRoute(flow, now, start);
      if (weight < 1) return;
      out.people += weight;
      out.events += 1;
      out.venues.set(flow.venue_id, (out.venues.get(flow.venue_id) || 0) + weight);
      (flow.legs || []).forEach((leg) => {
        if (!S.routes[leg.key]) return;
        const rec = out.legs.get(leg.key) || { key: leg.key, name: leg.name, mode: leg.mode, people: 0 };
        rec.people += weight * leg.share;
        out.legs.set(leg.key, rec);
      });
    });
    return out;
  }

  /* ---------------------------------------------------------- heat layer */
  function buildShapes(map, legs, total, pad = 0) {
    const shapes = [];
    for (const leg of legs) {
      const route = S.routes[leg.key];
      if (!route || !route.geometry) continue;
      // The heat does not need every vertex of a long OSRM trace. Reuse a
      // decimated trace for the density field; the untouched geometry remains
      // available for any detailed consumer.
      const source = route.geometry;
      const step = source.length > 80 ? 3 : source.length > 28 ? 2 : 1;
      const pts = [];
      for (let i = 0; i < source.length; i++) {
        if (i % step === 0 || i === source.length - 1) {
          pts.push(map.project(source[i][0], source[i][1]));
        }
      }
      if (pts.length < 2) continue;
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
      for (const p of pts) {
        if (p.x < minX) minX = p.x;
        if (p.x > maxX) maxX = p.x;
        if (p.y < minY) minY = p.y;
        if (p.y > maxY) maxY = p.y;
      }
      // Keep geometry in the padding too, so a pan can reveal cached heat
      // before the next full rasterisation.
      const margin = 40 + pad;
      if (maxX < -margin || minX > map.w + margin ||
          maxY < -margin || minY > map.h + margin) continue;
      shapes.push({
        pts, cum: cumulativeLengths(pts), people: Math.max(1, leg.people),
        share: leg.people / total, name: leg.name,
      });
    }
    return shapes;
  }

  /* The worker returns the padded heat bitmap off the main thread. It is an
     enhancement: unsupported browsers fall back to the synchronous renderer. */
  function ensureHeatWorker() {
    if (S.worker !== undefined) return S.worker;
    if (typeof Worker === "undefined" || typeof OffscreenCanvas === "undefined") {
      S.worker = null;
      return null;
    }
    try {
      const worker = new Worker("./heat-worker.js");
      worker.onmessage = (event) => {
        const msg = event.data || {};
        if (msg.id !== S.heatRequestId || !S.heatRequestMeta) {
          if (msg.bitmap && msg.bitmap.close) msg.bitmap.close();
          return;
        }
        const meta = S.heatRequestMeta;
        S.heatPendingKey = null;
        S.heatRequestMeta = null;
        if (msg.error || !msg.bitmap) {
          console.warn("heat worker failed, using main-thread fallback", msg.error || "no bitmap");
          worker.terminate();
          S.worker = null;
          if (S.map) S.map.schedule();
          return;
        }
        if (S.heatLayer && S.heatLayer.close) S.heatLayer.close();
        S.heatLayer = msg.bitmap;
        S.heatView = meta.view;
        S.heatAggVersion = meta.aggVersion;
        S.heatQuality = meta.quality;
        if (S.map) S.map.schedule();
      };
      worker.onerror = (event) => {
        console.warn("heat worker error, using main-thread fallback", event.message || event);
        worker.terminate();
        S.worker = null;
        S.heatPendingKey = null;
        S.heatRequestMeta = null;
        if (S.map) S.map.schedule();
      };
      S.worker = worker;
      return worker;
    } catch (err) {
      console.warn("heat worker unavailable", err);
      S.worker = null;
      return null;
    }
  }

  function startHeatRender(map, width, height, quality, magnitude, view) {
    const worker = ensureHeatWorker();
    if (!worker) return false;
    const key = `${S.aggVersion}|${quality}|${map._z}|${map._scale}|${map._ox}|${map._oy}|${width}|${height}`;
    if (S.heatPendingKey === key) return true;
    const id = ++S.heatRequestId;
    S.heatPendingKey = key;
    S.heatRequestMeta = { view, aggVersion: S.aggVersion, quality };
    worker.postMessage({
      id, width, height, zoom: map.zoom, quality, magnitude,
      shapes: S.heatShapes.map((s) => ({
        people: s.people,
        pts: s.pts.map((p) => [p.x, p.y]),
      })),
    });
    return true;
  }

  function paintFlow(ctx, map) {
    ctx.fillStyle = "rgba(250,247,241,.34)";
    ctx.fillRect(0, 0, map.w, map.h);

    const agg = S.agg || { legs: new Map(), venues: new Map(), people: 0 };
    if (S.sortedLegsVersion !== S.aggVersion) {
      S.sortedLegs = [...agg.legs.values()].sort((a, b) => b.people - a.people);
      S.sortedLegsVersion = S.aggVersion;
    }
    const legs = S.sortedLegs || [];
    if (!legs.length) {
      S.shapes = []; S.labelShapes = []; S.heatShapes = null;
      S.heatView = null; S.heatAggVersion = -1;
      paintEventDots(ctx, map);
      return;
    }
    const total = legs.reduce((sum, l) => sum + l.people, 0) || 1;
    const quality = S.scrubbing ? 0.55 : 1;

    // The heat bitmap is padded beyond the viewport. During a pan we crop the
    // appropriate region from it; only a large camera move, a zoom or new data
    // forces a fresh rasterisation of all street geometry.
    let pad = 0, shiftX = 0, shiftY = 0;
    let labelScale = 1, labelDX = 0, labelDY = 0;
    let drawHeat = true;
    const cached = S.heatLayer && S.heatView && S.heatAggVersion === S.aggVersion
      && S.heatQuality === quality;
    const sameSize = cached && S.heatView.w === map.w && S.heatView.h === map.h;
    const sameView = sameSize && S.heatView.z === map._z && S.heatView.scale === map._scale;
    const canShift = sameView
      && Math.abs(map._ox - S.heatView.ox) <= S.heatView.pad * 0.95
      && Math.abs(map._oy - S.heatView.oy) <= S.heatView.pad * 0.95;
    const canZoomPreview = sameSize && S.zooming;

    if (canZoomPreview) {
      // The animation is a transform of the last raster; rebuilding 2,500
      // projected routes on every zoom frame is what made zooming hitch.
      pad = S.heatView.pad;
      labelScale = map._scale / S.heatView.scale;
      labelDX = S.heatView.ox * labelScale - map._ox;
      labelDY = S.heatView.oy * labelScale - map._oy;
      const sx = pad - labelDX / labelScale;
      const sy = pad - labelDY / labelScale;
      ctx.drawImage(S.heatLayer, sx, sy, map.w / labelScale, map.h / labelScale,
                    0, 0, map.w, map.h);
    } else if (canShift) {
      pad = S.heatView.pad;
      shiftX = S.heatView.ox - map._ox;
      shiftY = S.heatView.oy - map._oy;
      labelDX = shiftX;
      labelDY = shiftY;
    } else {
      S.shapes = buildShapes(map, legs, total, HEAT_PAD);
      // Keep enough candidates that the visible subset still has district
      // names after a pan into the padded area.
      S.labelShapes = S.shapes.slice()
        .sort((a, b) => b.share - a.share)
        .slice(0, 48);
      S.heatShapes = S.shapes.map((s) => ({
        ...s,
        pts: s.pts.map((p) => ({ x: p.x + HEAT_PAD, y: p.y + HEAT_PAD })),
      }));
      pad = HEAT_PAD;
      const w = Math.max(1, Math.round(map.w + pad * 2));
      const h = Math.max(1, Math.round(map.h + pad * 2));
      // a touch more presence: quiet hours stay faint, busy ones fill the streets
      const magnitude = Math.min(1, Math.max(0.14, Math.log10(total + 1) / 3.1));
      const view = { z: map._z, scale: map._scale, ox: map._ox, oy: map._oy,
                     w: map.w, h: map.h, pad };
      const heatMap = { w, h, zoom: map.zoom, _z: map._z, _scale: map._scale,
                        _ox: map._ox - pad, _oy: map._oy - pad };
      if (startHeatRender(map, w, h, quality, magnitude, view)) {
        // The worker owns the new raster; keep the current frame responsive and
        // let the map show tiles/labels until the bitmap arrives.
        drawHeat = false;
      } else {
        if (!S.heatLayer || !S.heatLayer.getContext) {
          if (S.heatLayer && S.heatLayer.close) S.heatLayer.close();
          S.heatLayer = document.createElement("canvas");
        }
        if (S.heatLayer.width !== w || S.heatLayer.height !== h) {
          S.heatLayer.width = w; S.heatLayer.height = h;
        }
        const layer = S.heatLayer.getContext("2d");
        layer.clearRect(0, 0, w, h);
        drawTrafficHeat(layer, heatMap, S.heatShapes, magnitude, quality);
        S.heatView = view;
        S.heatAggVersion = S.aggVersion;
        S.heatQuality = quality;
      }
      labelDX = 0;
      labelDY = 0;
    }
    // Crop the viewport out of the padded bitmap, shifted by the pan delta.
    if (drawHeat && !canZoomPreview && S.heatLayer) {
      ctx.drawImage(S.heatLayer, pad - shiftX, pad - shiftY, map.w, map.h,
                    0, 0, map.w, map.h);
    }

    // the venues people are heading to, sized by how many are on their way
    if (S.sortedVenuesVersion !== S.aggVersion) {
      S.sortedVenues = [...agg.venues.entries()].sort((a, b) => b[1] - a[1]);
      S.sortedVenuesVersion = S.aggVersion;
    }
    (S.sortedVenues || []).forEach(([id, people]) => {
      const v = S.venues[id];
      if (!v) return;
      const p = map.project(v.lat, v.lon);
      const r = Math.max(4, Math.min(13, Math.sqrt(people) / 9));
      ctx.beginPath(); ctx.arc(p.x, p.y, r + 3, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(255,255,255,.95)"; ctx.fill();
      ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
      ctx.fillStyle = "#4a0f08"; ctx.fill();
    });

    // district names only: the map answers where, not which gig
    const placed = [];
    const labelLimit = MOBILE ? 4 : 6;
    (S.labelShapes || []).forEach((s) => {
      const p = s.pts[0];
      const px = p.x * labelScale + labelDX;
      const py = p.y * labelScale + labelDY;
      if (placed.length >= labelLimit) return;
      if (px < -20 || px > map.w + 20 || py < -20 || py > map.h + 20) return;
      const text = s.name;
      ctx.font = "600 10px 'IBM Plex Mono', monospace";
      const wText = ctx.measureText(text).width;
      let by = py - 4;
      let box = { x: px + 6, y: by - 10, w: wText, h: 12 };
      const hits = (b) => placed.some((o) => b.x < o.x + o.w + 3 && b.x + b.w + 3 > o.x && b.y < o.y + o.h + 2 && b.y + b.h + 2 > o.y);
      let tries = 0;
      while (hits(box) && tries < 4) { by -= 13; box = { x: px + 6, y: by - 10, w: wText, h: 12 }; tries++; }
      if (hits(box)) return;
      placed.push(box);
      ctx.fillStyle = "rgba(26,18,14,.92)";
      ctx.strokeStyle = "rgba(255,255,255,.85)";
      ctx.lineWidth = 3;
      ctx.strokeText(text, px + 6, by);
      ctx.fillText(text, px + 6, by);
    });

    paintEventDots(ctx, map);
  }

  /* one dot per event on the chosen day: what is on, and where */
  const DOT_COLOURS = { gigs: "#cf3a1f", sports: "#1d4ed8", student: "#c07a12", stage: "#7c3aed", culture: "#0f766e", community: "#5b6470" };
  function paintEventDots(ctx, map) {
    S.dotHits = [];
    const taken = {};
    (S.dayList || []).forEach((ev) => {
      const flow = S.flows[ev.id];
      if (!flow) return;
      const v = S.venues[flow.venue_id];
      if (!v) return;
      const p = map.project(v.lat, v.lon);
      const n = taken[v.id] = (taken[v.id] || 0) + 1;
      if (n > 1) { const a = (n - 1) * 2.1; p.x += Math.cos(a) * 7; p.y += Math.sin(a) * 7; }
      const colour = DOT_COLOURS[ev.category] || "#4a0f08";
      const on = S.hoverId != null && ev.id === S.hoverId;
      if (on) {
        ctx.beginPath(); ctx.arc(p.x, p.y, 11, 0, Math.PI * 2);
        ctx.lineWidth = 3; ctx.strokeStyle = "rgba(250,247,241,.95)"; ctx.stroke();
      }
      ctx.beginPath(); ctx.arc(p.x, p.y, on ? 7.5 : 5.5, 0, Math.PI * 2);
      ctx.fillStyle = colour; ctx.fill();
      ctx.lineWidth = 2; ctx.strokeStyle = on ? "#171310" : "rgba(255,255,255,.95)"; ctx.stroke();
      S.dotHits.push({ x: p.x, y: p.y, ev, venue: v });
    });
  }

  function categoryLabel(cat) {
    return ({ gigs: "Gig", sports: "Sports", student: "Student party", stage: "Stage", culture: "Culture", community: "Community" })[cat] || "Event";
  }

  function showTipAt(x, y, knownHit) {
    const tip = $("eventTip");
    if (!tip) return;
    const hit = knownHit || S.dotHits.find((h) => Math.hypot(h.x - x, h.y - y) < 16);
    if (!hit) { tip.hidden = true; return; }
    tip.innerHTML = `<b>${esc(eventClock(hit.ev))} · ${esc(hit.ev.title)}</b>` +
      `<span>${esc(hit.venue.name)} · ${categoryLabel(hit.ev.category)}${hit.ev.seed ? " · sample" : ""}</span>`;
    tip.hidden = false;
    const wrap = $("mapWrap").getBoundingClientRect();
    const w = Math.min(260, wrap.width - 20);
    tip.style.width = w + "px";
    tip.style.left = Math.max(8, Math.min(wrap.width - w - 8, x - w / 2)) + "px";
    tip.style.top = Math.max(8, y - tip.offsetHeight - 12) + "px";
  }

  /* ------------------------------------------------------------ estimate */
  function renderEstimate() {
    const box = $("estimate");
    const agg = S.agg || { people: 0, events: 0 };
    const day = dayLabel(S.minutes >= 24 * 60 ? addDays(S.day, 1) : S.day);
    const time = clockLabel(S.minutes);
    if (!agg.people) {
      box.innerHTML = `
        <div class="e-title">${esc(day)} · ${esc(time)}</div>
        <div class="e-line">No estimated crowd on a route at this hour.</div>
        <div class="e-note">Estimate, not a measurement.</div>`;
      return;
    }
    box.innerHTML = `
      <div class="e-title">${esc(day)} · ${esc(time)}</div>
      <div class="e-num">≈ ${Math.round(agg.people).toLocaleString("fi-FI")}</div>
      <div class="e-line">people estimated on routes · ${agg.events} event${agg.events === 1 ? "" : "s"} feeding it</div>
      <div class="e-note">Estimate, not a measurement.</div>`;
  }

  function refresh() {
    S.dayList = S.events.filter((ev) => ev.date === S.day);
    S.agg = aggregate();
    S.aggVersion += 1;
    if (S.map) S.map.schedule();
    renderEstimate();
  }

  function setScrubbing(on) {
    if (S.scrubbing === on) return;
    S.scrubbing = on;
    S.heatView = null;
    S.heatAggVersion = -1;
    S.heatQuality = -1;
    if (S.map) {
      S.map.setLowRes(on);
      S.map.schedule();
    }
  }

  /* -------------------------------------------------------------- wiring */
  function wire() {
    const zi = $("zoomIn"), zo = $("zoomOut");
    if (zi) zi.onclick = () => { if (S.hideTip) S.hideTip(); if (S.map) S.map.zoomBy(1); };
    if (zo) zo.onclick = () => { if (S.hideTip) S.hideTip(); if (S.map) S.map.zoomBy(-1); };
    const attrib = $("attrib");
    if (attrib) attrib.innerHTML = `<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">${esc(CFG.TILE_ATTRIBUTION || "© OpenStreetMap contributors")}</a>`;
  }

  /* the hour that puts the most people on the street on this day */
  function peakMinute(day) {
    let best = 19 * 60, top = -1;
    for (let m = 6 * 60; m <= 30 * 60; m += 15) {
      const keep = S.minutes;
      S.day = day; S.minutes = m;
      const people = aggregate().people;
      S.minutes = keep;
      if (people > top) { top = people; best = m; }
    }
    return best;
  }

  function resetHeat() {
    S.heatView = null;
    S.heatAggVersion = -1;
    S.heatQuality = -1;
    S.heatRequestId += 1;
    S.heatPendingKey = null;
    S.heatRequestMeta = null;
    S.sortedLegs = null;
    S.sortedLegsVersion = -1;
    S.sortedVenues = null;
    S.sortedVenuesVersion = -1;
    S.shapes = [];
    S.labelShapes = [];
    S.heatShapes = null;
  }

  async function loadDay(day) {
    const res = await fetch(`./geo/days/${encodeURIComponent(day)}.json`);
    if (!res.ok) throw new Error(`day ${day}: HTTP ${res.status}`);
    const doc = await res.json();
    if (!doc || !Array.isArray(doc.events)) throw new Error(`day ${day}: bundle has no events`);
    S.flows = {};
    S.routes = doc.routes || {};
    (doc.events || []).forEach((flow) => { S.flows[flow.id] = flow; });
    resetHeat();
  }

  /* Compatibility path for an older deployment that has no per-day bundles yet. */
  async function loadAllFlows() {
    const [flows, routes] = await Promise.all([
      fetch("./geo/flows.json").then((r) => r.json()),
      fetch("./geo/routes.json").then((r) => r.json()).catch(() => ({ routes: {} }))
    ]);
    S.flows = {};
    S.routes = routes.routes || {};
    (flows.events || []).forEach((flow) => { S.flows[flow.id] = flow; });
    resetHeat();
  }

  /* One fallback path for both first load and later day changes. Once the full
     bundle is loaded, keep using it instead of retrying a missing day file. */
  async function loadFlows(day) {
    if (S.fullFlows) return true;
    try {
      await loadDay(day);
      return true;
    } catch (err) {
      console.warn("per-day flow data unavailable, using full bundle", err);
    }
    try {
      await loadAllFlows();
      S.fullFlows = true;
      return true;
    } catch (err) {
      console.error("flow data failed", err);
      return false;
    }
  }

  async function init(events) {
    S.events = events || [];
    wire();
    const days = [...new Set(S.events.map((e) => e.date))].sort();
    S.day = days[0] || null;
    try {
      const venues = await fetch("./geo/venues.json").then((r) => r.json());
      (venues.venues || []).forEach((v) => { S.venues[v.id] = v; });
    } catch (err) {
      console.error("venue data failed", err);
    }
    if (S.day) await loadFlows(S.day);

    S.map = new TileMap($("mapCanvas"));
    S.map.paint = paintFlow;
    S.map.onTap = (e) => {
      const r = $("mapCanvas").getBoundingClientRect();
      const mx = e.clientX - r.left, my = e.clientY - r.top;
      const hit = S.map.hitAt(mx, my);
      showTipAt(mx, my, hit);
      // tapping a dot names it in the panel too, for phones without hover
      const id = hit ? hit.ev.id : null;
      if (id !== S.hoverId) { S.hoverId = id; if (S.onHover) S.onHover(id); S.map.schedule(); }
    };
    S.hideTip = () => { const t = $("eventTip"); if (t) t.hidden = true; };
    S.map.setCenter(61.4978, 23.7610, 13.2);
    S.map.schedule();

    S.minutes = 19 * 60;
    if (S.day) S.minutes = peakMinute(S.day);
    refresh();
  }

  window.KMap = {
    init,
    onHover(cb) { S.onHover = cb; },
    currentDay() { return S.day; },
    now() { return S.minutes; },
    renderer() { return S.worker ? "worker" : "main"; },
    venue(id) { return S.venues[id] || null; },
    /* every event on the chosen day, with the minutes the map uses */
    dayEvents() {
      return (S.dayList || []).map((ev) => {
        const f = S.flows[ev.id] || {};
        const v = S.venues[f.venue_id] || {};
        return {
          id: ev.id, time: eventClock(ev), timeKnown: ev.timeKnown !== false,
          title: ev.title, category: ev.category, sub: ev.sub, venueId: f.venue_id,
          venue: (v.name && f.venue_id !== "tampere_muu") ? v.name : (v.name || ev.venue || ""),
          // a TBA row has no precise start to mark "occurring now" against
          start: ev.timeKnown === false || f.start == null ? null : f.start,
          end: f.end == null ? null : f.end,
          mid: f.attendance ? f.attendance.mid : null,
          attendance: f.attendance || null,
          interest: f.interest || null,
          basis: f.basis || null,
          seed: !!ev.seed,
        };
      }).sort((a, b) => (a.start == null ? 1e9 : a.start) - (b.start == null ? 1e9 : b.start));
    },
    focusEvent(id) {
      const next = id || null;
      if (next === S.hoverId) return;
      S.hoverId = next;
      if (S.map) S.map.schedule();
    },
    refresh() { refresh(); },
    setScrubbing,
    async setDay(day) {
      if (!day) return null;
      if (S.hideTip) S.hideTip();
      S.hoverId = null;
      if (S.onHover) S.onHover(null);
      if (!(await loadFlows(day))) return null;
      S.day = day;
      S.minutes = peakMinute(day);
      refresh();
      return S.minutes;
    },
    setTime(min) {
      if (S.hideTip) S.hideTip();
      S.minutes = min;
      refresh();
    },
    /* test/debug hook: one event's estimated people on a route at a minute */
    eventPeople(id, minute) {
      const flow = S.flows[id];
      if (!flow) return 0;
      return enRoute(flow, minute, flow.start != null ? flow.start : 19 * 60);
    },
    clockLabel,
    dayLabel
  };
})();
