/* Kilinkolin — one estimated heat map: where the crowd comes from, or how it arrives.
   OpenStreetMap tiles on a canvas, our own projection, our own heat. No SDK, no key. */
(() => {
  "use strict";
  const CFG = window.KILINKOLIN || {};
  /* least likely -> most likely: yellow, amber, orange, red, deep red */
  const HEAT = ["#f4c20d", "#ee9f18", "#e66f1a", "#d13319", "#960d0a"]; // legend swatches only
  const TILE = 256;
  const MOBILE = window.matchMedia("(max-width: 700px), (pointer: coarse) and (max-width: 1024px), (max-width: 1000px) and (max-height: 520px)").matches;
  document.documentElement.classList.toggle("is-mobile", MOBILE);
  document.documentElement.dataset.mobile = MOBILE ? "true" : "false";

  const S = { events: [], flows: {}, venues: {}, zoneMeta: null, routes: {}, map: null, dotHits: [],
              hoverId: null, onHover: null, day: null, minutes: 19 * 60 };
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
      this.paint = null;
      this._z = 12; this._scale = 1; this._ox = 0; this._oy = 0;
      this._bind();
      this.resize();
    }
    resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, MOBILE ? 1.75 : 2);
      const w = this.canvas.clientWidth || 800;
      const h = this.canvas.clientHeight || 520;
      this.w = w; this.h = h; this.dpr = dpr;
      this.canvas.width = Math.round(w * dpr);
      this.canvas.height = Math.round(h * dpr);
      this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      this.schedule();
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
        if (hit) showTipAt(mx, my); else if (S.hideTip) S.hideTip();
        return;
      }
      S.hoverId = id;
      if (hit) showTipAt(mx, my);
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
      ctx.fillStyle = "#e7e2d6";
      ctx.fillRect(0, 0, this.w, this.h);

      const n = Math.pow(2, z);
      const x0 = Math.floor(ox / ts), x1 = Math.floor((ox + this.w) / ts);
      const y0 = Math.floor(oy / ts), y1 = Math.floor((oy + this.h) / ts);
      let painted = 0;
      for (let x = x0; x <= x1; x++) {
        for (let y = y0; y <= y1; y++) {
          if (y < 0 || y >= n) continue;
          const tx = ((x % n) + n) % n;
          const img = this.tile(z, tx, y);
          if (!img) continue;
          ctx.drawImage(img, Math.round(x * ts - ox), Math.round(y * ts - oy), Math.ceil(ts) + 1, Math.ceil(ts) + 1);
          painted++;
        }
      }
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
        img.addEventListener("load", () => this.schedule());
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
      const step = (now) => {
        const k = Math.min(1, (now - t0) / 240);
        const eased = 1 - Math.pow(1 - k, 3);
        this.zoom = start + (end - start) * eased;
        this.draw();
        if (k < 1) this._zoomRaf = requestAnimationFrame(step);
        else this._zoomRaf = null;
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
        if (wasTap && this.onTap) this.onTap(e);
      };
      c.addEventListener("pointerup", end);
      c.addEventListener("pointercancel", () => end(null));
      c.addEventListener("pointerleave", () => {
        if (drag) return;
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
        this.zoom = Math.max(this.minZoom, Math.min(this.maxZoom, this.zoom - e.deltaY * 0.0025));
        this.draw();
        const after = this.unproject(mx, my);
        this.center = { lat: this.center.lat + (before.lat - after.lat), lon: this.center.lon + (before.lon - after.lon) };
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

  function rampAt(t) {
    const v = Math.min(1, Math.max(0, t));
    for (let i = 1; i < RAMP.length; i++) {
      if (v <= RAMP[i][0]) {
        const [t0, c0] = RAMP[i - 1];
        const [t1, c1] = RAMP[i];
        const f = (v - t0) / (t1 - t0 || 1);
        return [0, 1, 2].map((k) => Math.round(c0[k] + (c1[k] - c0[k]) * f));
      }
    }
    return RAMP[RAMP.length - 1][1];
  }

  function lengthOf(pts) {
    let len = 0;
    for (let i = 1; i < pts.length; i++) len += Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y);
    return len;
  }

  function pointOn(pts, target) {
    let run = 0;
    for (let i = 1; i < pts.length; i++) {
      const a = pts[i - 1], b = pts[i];
      const seg = Math.hypot(b.x - a.x, b.y - a.y);
      if (run + seg >= target || i === pts.length - 1) {
        const f = seg ? Math.min(1, Math.max(0, (target - run) / seg)) : 0;
        return { x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f };
      }
      run += seg;
    }
    return pts[0];
  }

  /* half-resolution buffer: smooth heat, cheap to colourise every frame */
  function ensureHalf(map) {
    const w = Math.max(1, Math.round(map.w / 2));
    const h = Math.max(1, Math.round(map.h / 2));
    if (!S.half) S.half = document.createElement("canvas");
    if (S.half.width !== w || S.half.height !== h) { S.half.width = w; S.half.height = h; }
    const c = S.half.getContext("2d");
    c.setTransform(1, 0, 0, 1, 0, 0);
    c.clearRect(0, 0, w, h);
    c.globalCompositeOperation = "lighter";
    c.scale(0.5, 0.5);
    return S.half;
  }

  function deposit(half, shapes, topDensity, zoom) {
    const c = half.getContext("2d");
    // traffic concentration: people per metre of street, not per route
    const density = shapes.map((s) => Math.max(1, s.people) / Math.max(80, lengthOf(s.pts)));
    const top = topDensity || Math.max.apply(null, density.concat([1e-6]));
    const topPeople = Math.max.apply(null, shapes.map((s) => Math.max(1, s.people)).concat([1]));
    shapes.forEach((s, i) => {
      const len = lengthOf(s.pts);
      // sqrt-ish: a long approach with few people still needs to be seen
      const weight = Math.pow(Math.min(1, density[i] / top), 0.6);
      const n = Math.max(6, Math.min(MOBILE ? 140 : 320, Math.round(len / 4)));
      // wider kernels when zoomed out, so long approaches read as heat and not as hairlines
      const zoomBoost = Math.min(2.4, Math.max(0.6, Math.pow(2, 13.2 - zoom)));
      const radius = (4 + 7.5 * weight) * zoomBoost;
      const alpha = 0.10 + 0.27 * weight;
      // origin patch: where this part of the crowd comes from. Sized by people, not by
      // walk length, so a distant district still reads as a source area.
      const home = s.pts[0];
      const share = Math.pow(Math.max(1, s.people) / topPeople, 0.6);
      const homeRadius = (7 + 12 * share) * zoomBoost;
      const g0 = c.createRadialGradient(home.x, home.y, 0, home.x, home.y, homeRadius);
      g0.addColorStop(0, `rgba(255,255,255,${0.1 + 0.3 * share})`);
      g0.addColorStop(0.55, `rgba(255,255,255,${0.05 + 0.15 * share})`);
      g0.addColorStop(1, "rgba(255,255,255,0)");
      c.fillStyle = g0;
      c.beginPath();
      c.arc(home.x, home.y, homeRadius, 0, Math.PI * 2);
      c.fill();

      for (let k = 0; k <= n; k++) {
        const p = pointOn(s.pts, (len * k) / n);
        const g = c.createRadialGradient(p.x, p.y, 0, p.x, p.y, radius);
        g.addColorStop(0, `rgba(255,255,255,${alpha})`);
        g.addColorStop(0.45, `rgba(255,255,255,${alpha * 0.5})`);
        g.addColorStop(1, "rgba(255,255,255,0)");
        c.fillStyle = g;
        c.beginPath();
        c.arc(p.x, p.y, radius, 0, Math.PI * 2);
        c.fill();
      }
    });
  }

  function colourise(half, ctx, map, colourAt, maxAlpha, magnitude) {
    const c = half.getContext("2d");
    const img = c.getImageData(0, 0, half.width, half.height);
    const d = img.data;
    // normalise against a high percentile, not the maximum: one saturated core would
    // otherwise flatten every approach street to nothing
    const sample = [];
    for (let i = 3; i < d.length; i += 4 * 7) if (d[i]) sample.push(d[i]);
    if (!sample.length) return;
    sample.sort((a, b) => a - b);
    const top = Math.max(28, sample[Math.floor(sample.length * 0.97)]);
    for (let i = 0; i < d.length; i += 4) {
      const a = d[i + 3];
      if (!a) continue;
      const t = Math.min(1, Math.pow(a / top, 0.8));
      const rgb = colourAt(t);
      d[i] = rgb[0]; d[i + 1] = rgb[1]; d[i + 2] = rgb[2];
      // magnitude keeps a quiet hour quiet: three people should not paint the whole city
      d[i + 3] = Math.min(255, Math.round(t * maxAlpha * (magnitude == null ? 1 : magnitude)));
    }
    c.putImageData(img, 0, 0);
    ctx.save();
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(half, 0, 0, map.w, map.h);
    ctx.restore();
  }

  function topDensity(shapes) {
    return Math.max.apply(null, shapes.map((s) => Math.max(1, s.people) / Math.max(80, lengthOf(s.pts))).concat([1e-6]));
  }

  function drawTrafficHeat(ctx, map, shapes, magnitude) {
    if (!shapes.length) return;
    const half = ensureHalf(map);
    deposit(half, shapes, topDensity(shapes), map.zoom);
    colourise(half, ctx, map, rampAt, 235, magnitude);
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
     or heading home after the estimated end */
  function enRoute(flow, now, startMin) {
    const mid = Math.max(0, flow.attendance.mid);
    const arrive = sliceShare(flow.arrival, now - startMin - 15, now - startMin);
    // old cached flows have no end; they simply count arrivals until the next build
    let leave = 0;
    if (flow.end != null) leave = sliceShare(flow.egress, now - flow.end - 15, now - flow.end);
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
  function paintFlow(ctx, map) {
    ctx.fillStyle = "rgba(250,247,241,.34)";
    ctx.fillRect(0, 0, map.w, map.h);

    const agg = S.agg || { legs: new Map(), venues: new Map(), people: 0 };
    const legs = [...agg.legs.values()].sort((a, b) => b.people - a.people);
    if (!legs.length) { paintEventDots(ctx, map); return; }
    const total = legs.reduce((sum, l) => sum + l.people, 0) || 1;
    const P = (lat, lon) => map.project(lat, lon);
    const shapes = legs.map((leg) => ({
      pts: S.routes[leg.key].geometry.map((pt) => P(pt[0], pt[1])),
      people: Math.max(1, leg.people), share: leg.people / total, mode: leg.mode, name: leg.name,
    })).filter((s) => s.pts.length > 1);

    // a touch more presence: quiet hours stay faint, busy ones fill the streets
    const magnitude = Math.min(1, Math.max(0.14, Math.log10(total + 1) / 3.1));
    drawTrafficHeat(ctx, map, shapes, magnitude);

    // the venues people are heading to, sized by how many are on their way
    [...agg.venues.entries()].sort((a, b) => b[1] - a[1]).forEach(([id, people]) => {
      const v = S.venues[id];
      if (!v) return;
      const p = P(v.lat, v.lon);
      const r = Math.max(4, Math.min(13, Math.sqrt(people) / 9));
      ctx.beginPath(); ctx.arc(p.x, p.y, r + 3, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(255,255,255,.95)"; ctx.fill();
      ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
      ctx.fillStyle = "#4a0f08"; ctx.fill();
    });

    // district names only: the map answers where, not which gig
    const placed = [];
    shapes.sort((a, b) => b.share - a.share).slice(0, MOBILE ? 4 : 6).forEach((s) => {
      const p = s.pts[0];
      const text = s.name;
      ctx.font = "600 10px 'IBM Plex Mono', monospace";
      const wText = ctx.measureText(text).width;
      let by = p.y - 4;
      let box = { x: p.x + 6, y: by - 10, w: wText, h: 12 };
      const hits = (b) => placed.some((o) => b.x < o.x + o.w + 3 && b.x + b.w + 3 > o.x && b.y < o.y + o.h + 2 && b.y + b.h + 2 > o.y);
      let tries = 0;
      while (hits(box) && tries < 4) { by -= 13; box = { x: p.x + 6, y: by - 10, w: wText, h: 12 }; tries++; }
      if (hits(box)) return;
      placed.push(box);
      ctx.fillStyle = "rgba(26,18,14,.92)";
      ctx.strokeStyle = "rgba(255,255,255,.85)";
      ctx.lineWidth = 3;
      ctx.strokeText(text, p.x + 6, by);
      ctx.fillText(text, p.x + 6, by);
    });

    paintEventDots(ctx, map);
  }

  /* one dot per event on the chosen day: what is on, and where */
  const DOT_COLOURS = { gigs: "#cf3a1f", sports: "#1d4ed8", student: "#c07a12", stage: "#7c3aed", culture: "#0f766e", community: "#5b6470" };
  function paintEventDots(ctx, map) {
    S.dotHits = [];
    const taken = {};
    S.events.filter((ev) => ev.date === S.day).forEach((ev) => {
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

  function showTipAt(x, y) {
    const tip = $("eventTip");
    if (!tip) return;
    const hit = S.dotHits.find((h) => Math.hypot(h.x - x, h.y - y) < 16);
    if (!hit) { tip.hidden = true; return; }
    tip.innerHTML = `<b>${esc(hit.ev.time)} · ${esc(hit.ev.title)}</b>` +
      `<span>${esc(hit.venue.name)} · ${categoryLabel(hit.ev.category)}${hit.ev.seed ? " · sample" : ""}</span>`;
    tip.hidden = false;
    const wrap = $("mapWrap").getBoundingClientRect();
    const w = Math.min(260, wrap.width - 20);
    tip.style.width = w + "px";
    tip.style.left = Math.max(8, Math.min(wrap.width - w - 8, x - w / 2)) + "px";
    tip.style.top = Math.max(8, y - tip.offsetHeight - 12) + "px";
    S.tipOpen = true;
  }

  /* ------------------------------------------------------------ estimate */
  function renderEstimate() {
    const box = $("estimate");
    const agg = S.agg || { people: 0, events: 0 };
    const day = dayLabel(S.day);
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
    S.agg = aggregate();
    if (S.map) S.map.schedule();
    renderEstimate();
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

  async function init(events) {
    S.events = events || [];
    wire();
    try {
      const [flows, venues, zones, routes] = await Promise.all([
        fetch("./geo/flows.json").then((r) => r.json()),
        fetch("./geo/venues.json").then((r) => r.json()),
        fetch("./geo/zones.json").then((r) => r.json()),
        fetch("./geo/routes.json").then((r) => r.json()).catch(() => ({ routes: {} }))
      ]);
      S.routes = routes.routes || {};
      (flows.events || []).forEach((f) => { S.flows[f.id] = f; });
      (venues.venues || []).forEach((v) => { S.venues[v.id] = v; });
      S.zoneMeta = {};
      (zones.zones || []).forEach((z) => { S.zoneMeta[z.id] = z; });
    } catch (err) {
      console.error("flow data failed", err);
    }

    S.map = new TileMap($("mapCanvas"));
    S.map.paint = paintFlow;
    S.map.onTap = (e) => {
      const r = $("mapCanvas").getBoundingClientRect();
      const mx = e.clientX - r.left, my = e.clientY - r.top;
      const hit = S.map.hitAt(mx, my);
      showTipAt(mx, my);
      // tapping a dot names it in the panel too, for phones without hover
      const id = hit ? hit.ev.id : null;
      if (id !== S.hoverId) { S.hoverId = id; if (S.onHover) S.onHover(id); S.map.schedule(); }
    };
    S.hideTip = () => { const t = $("eventTip"); if (t) t.hidden = true; };
    S.map.setCenter(61.4978, 23.7610, 13.2);
    S.map.schedule();

    const days = [...new Set(S.events.map((e) => e.date))].sort();
    S.day = days[0] || null;
    S.minutes = 19 * 60;
    if (S.day) S.minutes = peakMinute(S.day);
    refresh();
  }

  window.KMap = {
    init,
    onHover(cb) { S.onHover = cb; },
    currentDay() { return S.day; },
    now() { return S.minutes; },
    /* every event on the chosen day, with the minutes the map uses */
    dayEvents() {
      return S.events.filter((ev) => ev.date === S.day).map((ev) => {
        const f = S.flows[ev.id] || {};
        const v = S.venues[f.venue_id] || {};
        return {
          id: ev.id, time: ev.time, title: ev.title, category: ev.category,
          venue: (v.name && f.venue_id !== "tampere_muu") ? v.name : (v.name || ev.venue || ""),
          start: f.start == null ? null : f.start,
          end: f.end == null ? null : f.end,
          mid: f.attendance ? f.attendance.mid : null,
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
    setDay(day) {
      if (!day) return;
      if (S.hideTip) S.hideTip();
      S.hoverId = null;
      if (S.onHover) S.onHover(null);
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
    clockLabel,
    dayLabel
  };
})();
