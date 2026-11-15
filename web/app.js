/* Kilinkolin — pick a day, pick an hour, see the estimated crowd on its routes. */
(() => {
  const CFG = window.KILINKOLIN || {};
  const $ = (id) => document.getElementById(id);
  const IS_MOBILE = document.documentElement.classList.contains("is-mobile");
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const CAT_LABEL = {
    gigs: "Gig", sports: "Sports", student: "Student", stage: "Stage",
    culture: "Culture", community: "Community", other: "Event"
  };

  let curDay = null;
  let dayEvents = [];
  let dayIndex = new Map();
  let selectedId = null;
  let VENUES = {};

  const esc = (s) => String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

  /* the venue's street address, unless the label already is one (calendar venues) */
  function addrOf(ev) {
    const v = VENUES[ev.venueId];
    const a = v && v.address ? String(v.address).trim() : "";
    const label = String(ev.venue || "").trim();
    if (!a) return "";
    const al = a.toLowerCase(), ll = label.toLowerCase();
    if (al === ll) return "";
    // calendar places arrive as "Venue, street, postcode"; keep only the part the label lacks
    if (ll && al.startsWith(ll + ",")) {
      if (/\d/.test(label)) return "";
      const rest = a.slice(label.length + 1).trim();
      return rest && rest.toLowerCase() !== ll ? rest : "";
    }
    return a;
  }

  function stamp(raw) {
    const m = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}) UTC$/.exec(raw || "");
    if (!m) return raw || "unknown";
    const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]));
    // the stamp is UTC; format it in UTC so a 00:16 rebuild does not show yesterday
    return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" }) + `, ${m[4]}:${m[5]} UTC`;
  }

  const dayLabel = (iso) => {
    const p = (iso || "").split("-");
    if (p.length !== 3) return iso || "";
    const d = new Date(+p[0], +p[1] - 1, +p[2]);
    return `${DOW[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]}`;
  };

  function toEvents(rows) {
    return rows.map((r) => ({
      // the feed omits a start time for a few events; count those at a typical 19:00 start
      date: r[0], time: r[1] || "19:00", title: r[2], venue: r[3],
      id: r[7], category: r[9], venueId: r[14], seed: !!r[13]
    })).filter((e) => e.id);
  }

  function buildDays(events) {
    const strip = $("dayStrip");
    const days = [...new Set(events.map((e) => e.date))].sort();
    strip.innerHTML = days.map((day) => {
      const p = day.split("-");
      const d = new Date(+p[0], +p[1] - 1, +p[2]);
      return `<button class="day" data-day="${day}" type="button">` +
        `<span class="day-dow">${DOW[d.getDay()]}</span>` +
        `<span class="day-num">${d.getDate()}</span>` +
        `<span class="day-mon">${MONTHS[d.getMonth()]}</span></button>`;
    }).join("");
    strip.querySelectorAll(".day").forEach((btn) => {
      btn.onclick = () => {
        const min = window.KMap.setDay(btn.dataset.day);
        curDay = btn.dataset.day;
        markDay(btn.dataset.day);
        revealDay(btn);
        setTime(min, true);
        renderPanel();
      };
    });
    return days;
  }

  function markDay(day) {
    document.querySelectorAll(".day").forEach((b) => b.classList.toggle("on", b.dataset.day === day));
  }

  function revealDay(btn) {
    if (!btn) return;
    const smooth = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    btn.scrollIntoView({ inline: "center", block: "nearest", behavior: smooth ? "smooth" : "auto" });
  }

  function paintSlider() {
    const el = $("timeSlider");
    const min = +el.min, max = +el.max;
    el.style.setProperty("--fill", ((+el.value - min) / (max - min) * 100).toFixed(2) + "%");
  }

  function setTime(min, moveSlider) {
    if (moveSlider) $("timeSlider").value = String(min);
    const nextDay = +min >= 24 * 60;
    const label = window.KMap.clockLabel(min);
    $("timeLabel").textContent = nextDay ? label + " +1" : label;
    $("timeLabel").title = nextDay ? label + " the next morning" : "";
    paintSlider();
  }

  /* ------------------------------------------------------- right-hand panel
     What is on today, and the details of the dot under the pointer. */
  function renderDetail(id) {
    const box = $("panelDetail");
    if (!box) return;
    const ev = dayEvents.find((e) => e.id === id);
    if (!ev) {
      box.className = "panel-detail";
      box.innerHTML = `<span class="pd-hint">${IS_MOBILE ? "Tap a dot on the map, or a row below, for that event." : "Hover a dot on the map, or a row below, for that event."}</span>`;
      return;
    }
    const end = ev.end != null ? "–" + window.KMap.clockLabel(ev.end) + (ev.end >= 24 * 60 ? " +1" : "") : "";
    box.className = "panel-detail on";
    box.innerHTML =
      `<div class="pd-title">${esc(ev.title)}</div>` +
      `<div class="pd-meta">${esc(ev.time)}${esc(end)} · ${esc(ev.venue)}` +
      `${addrOf(ev) ? " · " + esc(addrOf(ev)) : ""}</div>` +
      `<div class="pd-meta"><span class="cat cat-${esc(ev.category)}">${esc(CAT_LABEL[ev.category] || "Event")}</span>` +
      `${ev.mid != null ? `<span class="pd-est">≈ ${ev.mid.toLocaleString("fi-FI")} people, estimated</span>` : ""}</div>` +
      `<div class="pd-note">Estimate, not a measurement.</div>`;
  }

  function markRow(id) {
    document.querySelectorAll("#panelList .panelRow").forEach((row) => {
      row.classList.toggle("sel", id != null && row.dataset.id === id);
    });
  }

  function select(id) {
    selectedId = id || null;
    renderDetail(selectedId);
    markRow(selectedId);
  }

  function renderPanel() {
    const list = $("panelList");
    if (!list) return;
    dayEvents = window.KMap.dayEvents();
    dayIndex = new Map(dayEvents.map((e) => [e.id, e]));
    $("panelTitle").textContent = curDay ? `What's on · ${dayLabel(curDay)}` : "What's on";
    $("panelCount").textContent = dayEvents.length
      ? `${dayEvents.length} event${dayEvents.length === 1 ? "" : "s"}`
      : "";
    if (!dayEvents.length) {
      list.innerHTML = `<li class="panelRow empty">No events on this day.</li>`;
      renderDetail(null);
      return;
    }
    const now = +$("timeSlider").value;
    list.innerHTML = dayEvents.map((e) => {
      const occurring = e.start != null && e.end != null && now >= e.start && now < e.end;
      const soon = e.start != null && !occurring && now >= e.start - 120 && now < e.start;
      return `<li class="panelRow${occurring ? " on" : ""}${soon ? " soon" : ""}" data-id="${esc(e.id)}">` +
        `<span class="pr-time">${esc(e.time || "—")}</span>` +
        `<span class="pr-body"><span class="pr-title">${esc(e.title)}</span>` +
        `<span class="pr-venue">${esc(e.venue)}${addrOf(e) ? " · " + esc(addrOf(e)) : ""}</span></span>` +
        `<span class="cat cat-${esc(e.category)}">${esc(CAT_LABEL[e.category] || "Event")}</span></li>`;
    }).join("");
    list.querySelectorAll(".panelRow[data-id]").forEach((row) => {
      const id = row.dataset.id;
      row.addEventListener("mouseenter", () => { select(id); window.KMap.focusEvent(id); });
      row.addEventListener("mouseleave", () => { if (selectedId === id) window.KMap.focusEvent(null); });
      row.addEventListener("click", () => { select(id); window.KMap.focusEvent(id); });
      row.addEventListener("focus", () => { select(id); window.KMap.focusEvent(id); });
    });
    renderDetail(selectedId && dayEvents.some((e) => e.id === selectedId) ? selectedId : null);
  }

  /* time moves do not change any row text, only its on/soon state */
  function updatePanelNow() {
    const now = +$("timeSlider").value;
    document.querySelectorAll("#panelList .panelRow[data-id]").forEach((row) => {
      const e = dayIndex.get(row.dataset.id);
      if (!e) return;
      const occurring = e.start != null && e.end != null && now >= e.start && now < e.end;
      const soon = e.start != null && !occurring && now >= e.start - 120 && now < e.start;
      row.classList.toggle("on", occurring);
      row.classList.toggle("soon", soon);
    });
  }

  function renderStatus(meta) {
    const pill = $("updatedBadge");
    const age = meta.generated ? (Date.now() - Date.parse(meta.generated.replace(" UTC", "Z"))) / 86400000 : 99;
    pill.classList.add(age > 8 ? "stale" : "live");
    pill.querySelector(".status-text").textContent = meta.generated
      ? `Estimated flow model · rebuilt ${stamp(meta.generated)}`
      : "Bundled snapshot";
    const badge = $("buildBadge");
    if (badge) {
      badge.textContent = `v${CFG.APP_VERSION || "?"} · updated ${meta.generated ? stamp(meta.generated) : "bundled"}`;
    }
  }

  function renderFoot(meta) {
    $("roadNote").textContent =
      `Close districts walk; farther ones ride tram, bus or train, so their corridor follows the main road. ` +
      `Model ${meta.model_version || CFG.MODEL_VERSION}.`;
    $("footNote").innerHTML =
      `Every number is an <b>estimate</b> from a population model — not measured attendance, not tracking. ` +
      `Basemap © OpenStreetMap contributors. Music data from ` +
      `<a href="https://github.com/zakker111/tampere-keikat" target="_blank" rel="noopener">Tampere Keikat</a> (MIT); ` +
      `hockey fixtures from the Liiga game list. Every event shown comes from a published feed — ` +
      `placeholder rows are not published. Events without a listed start are counted at 19:00. ` +
      `The heat counts people travelling in before a start and heading home after an estimated end.`;
  }

  async function load() {
    let data = { events: [], coverage: {} };
    try {
      const r = await fetch("./data.json");
      if (!r.ok) throw new Error("HTTP " + r.status);
      data = await r.json();
    } catch (err) {
      console.warn("data.json unavailable", err);
    }
    renderStatus(data);
    renderFoot(data);
    try {
      const vr = await fetch("./geo/venues.json");
      if (vr.ok) (await vr.json()).venues.forEach((v) => { VENUES[v.id] = v; });
    } catch (err) {
      console.warn("venues.json unavailable", err);
    }
    const events = toEvents(data.events || []);
    const days = buildDays(events);

    window.KMap.onHover(select);
    await window.KMap.init(events);

    if (days.length) {
      const first = days[0];
      const min = window.KMap.setDay(first);
      curDay = first;
      markDay(first);
      revealDay(document.querySelector(`.day[data-day="${first}"]`));
      setTime(min, true);
    } else {
      $("estimate").innerHTML = `<div class="e-line">No events in the feed right now.</div>`;
    }
    renderPanel();

    let queued = 0;
    $("timeSlider").addEventListener("input", (e) => {
      setTime(+e.target.value, false);
      if (queued) cancelAnimationFrame(queued);
      queued = requestAnimationFrame(() => {
        queued = 0;
        window.KMap.setTime(+$("timeSlider").value);
        updatePanelNow();
      });
    });
  }

  document.addEventListener("DOMContentLoaded", load);
})();
