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
  let CALIBRATION = null;
  let sheetTrigger = null;

  const esc = (s) => String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

  /* the venue's street address, unless the label already is one (calendar venues) */
  function addrOf(ev) {
    const v = window.KMap.venue ? window.KMap.venue(ev.venueId) : null;
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
      // the feed omits a start time for a few events; model those at 19:00 but
      // keep the flag so the UI can say the start is unknown
      date: r[0], time: r[1] || "19:00", timeKnown: !!r[1], title: r[2], venue: r[3],
      id: r[7], category: r[9], sub: r[10], venueId: r[14], seed: !!r[13]
    })).filter((e) => e.id);
  }

  function buildDays(events) {
    const strip = $("dayStrip");
    const days = [...new Set(events.map((e) => e.date))].sort();
    strip.innerHTML = days.map((day) => {
      const p = day.split("-");
      const d = new Date(+p[0], +p[1] - 1, +p[2]);
      return `<button class="day" data-day="${esc(day)}" type="button">` +
        `<span class="day-dow">${DOW[d.getDay()]}</span>` +
        `<span class="day-num">${d.getDate()}</span>` +
        `<span class="day-mon">${MONTHS[d.getMonth()]}</span></button>`;
    }).join("");
    strip.querySelectorAll(".day").forEach((btn) => {
      btn.onclick = async () => {
        if (btn.disabled) return;
        btn.disabled = true;
        try {
          stopPlay();
          const min = await window.KMap.setDay(btn.dataset.day);
          if (min == null) return;
          curDay = btn.dataset.day;
          markDay(btn.dataset.day);
          revealDay(btn);
          setTime(min, true);
          renderPanel();
        } finally {
          btn.disabled = false;
        }
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
    updateSparkCursor();
  }

  /* ------------------------------------------------------- right-hand panel
     What is on today, and the details of the dot under the pointer. */
  function clockWithDay(min) {
    const day = Math.floor(min / (24 * 60));
    return window.KMap.clockLabel(min) + (day ? ` +${day}` : "");
  }

  /* ------------------------------------------------- directions and calendar
     Directions is a plain keyless maps link to the venue's own published point;
     walking, because the heat is people walking. The .ics is generated here, in
     UTC, so no VTIMEZONE block is needed and every calendar app reads it. */
  function directionsHref(ev) {
    const venue = window.KMap.venue ? window.KMap.venue(ev.venueId) : null;
    const lat = venue && Number(venue.lat), lon = venue && Number(venue.lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
    return "https://www.google.com/maps/dir/?api=1&travelmode=walking" +
      `&destination=${lat.toFixed(6)},${lon.toFixed(6)}`;
  }

  function icsEsc(value) {
    return String(value == null ? "" : value)
      .replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,")
      .replace(/\r?\n/g, "\\n");
  }

  /* milliseconds Europe/Helsinki is ahead of UTC at that instant */
  function helsinkiOffset(ms) {
    const fmt = new Intl.DateTimeFormat("en-US", {
      timeZone: "Europe/Helsinki", hour12: false,
      year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
    const parts = {};
    fmt.formatToParts(new Date(ms)).forEach((part) => { parts[part.type] = part.value; });
    // hour can read 24 for midnight in some engines
    return Date.UTC(+parts.year, +parts.month - 1, +parts.day, +parts.hour % 24, +parts.minute, +parts.second) - ms;
  }

  /* a wall-clock time on the shown day to the instant it happens; Date.UTC rolls
     minutes past midnight into the next morning, so a 00:30 start lands right */
  function helsinkiToUtc(day, minutes) {
    const [y, m, d] = day.split("-").map(Number);
    const guess = Date.UTC(y, m - 1, d, 0, minutes);
    return new Date(guess - helsinkiOffset(guess));
  }

  function icsStamp(date) {
    const pad = (n) => String(n).padStart(2, "0");
    return `${date.getUTCFullYear()}${pad(date.getUTCMonth() + 1)}${pad(date.getUTCDate())}T` +
      `${pad(date.getUTCHours())}${pad(date.getUTCMinutes())}00Z`;
  }

  function icsText(ev) {
    const venue = window.KMap.venue ? window.KMap.venue(ev.venueId) : null;
    const start = helsinkiToUtc(curDay, ev.start);
    const end = helsinkiToUtc(curDay, ev.end != null ? ev.end : ev.start + 120);
    const where = [ev.venue, venue && venue.address].filter(Boolean).join(", ");
    const estimate = ev.mid != null
      ? `Estimated crowd ≈ ${ev.mid.toLocaleString("fi-FI")} people on the routes to this event — a model estimate, not a measurement.`
      : "";
    const page = location.origin + location.pathname;
    return [
      "BEGIN:VCALENDAR",
      "VERSION:2.0",
      "PRODID:-//Kilinkolin//estimated crowd flow//EN",
      "CALSCALE:GREGORIAN",
      "BEGIN:VEVENT",
      `UID:kilinkolin-${icsEsc(ev.id)}-${curDay}@kilinkolin`,
      `DTSTAMP:${icsStamp(new Date())}`,
      `DTSTART:${icsStamp(start)}`,
      `DTEND:${icsStamp(end)}`,
      `SUMMARY:${icsEsc(ev.title)}`,
      `LOCATION:${icsEsc(where)}`,
      `DESCRIPTION:${icsEsc(estimate + " " + page)}`,
      `URL:${page}`,
      `CATEGORIES:${icsEsc(CAT_LABEL[ev.category] || "Event")}`,
      "END:VEVENT",
      "END:VCALENDAR",
      "",
    ].join("\r\n");
  }

  function downloadIcs(ev) {
    const slug = String(ev.title).normalize("NFD").replace(/[\u0300-\u036f]/g, "")
      .toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60) || "event";
    const url = URL.createObjectURL(new Blob([icsText(ev)], { type: "text/calendar;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `kilinkolin-${curDay}-${slug}.ics`;
    link.style.display = "none";
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  /* --------------------------------------------------------- arrival timing
     The model already ships per-event arrival slices (shares by 15-min window);
     surface the quietest and the peak as one honest line. No recomputation. */
  function arrivalTiming(ev) {
    if (ev.start == null || !ev.arrival?.length) return null;
    const quietest = ev.arrival.reduce((a, b) => (b.share < a.share ? b : a));
    const peak = ev.arrival.reduce((a, b) => (b.share > a.share ? b : a));
    const clock = window.KMap.clockLabel;
    return { quietest: clock(ev.start + quietest.t), peak: clock(ev.start + peak.t) };
  }

  function renderDetail(id) {
    const box = $("panelDetail");
    if (!box) return;
    const ev = dayEvents.find((e) => e.id === id);
    if (!ev) {
      box.className = "panel-detail";
      box.innerHTML = `<span class="pd-hint">${IS_MOBILE ? "Tap a dot on the map, or a row below, for that event." : "Hover a dot on the map, or a row above, for that event."}</span>`;
      return;
    }
    const timeUnknown = ev.timeKnown === false;
    const time = timeUnknown ? "Start TBA" : ev.time;
    const end = !timeUnknown && ev.end != null ? "–" + clockWithDay(ev.end) : "";
    const addr = addrOf(ev);
    const timeNote = timeUnknown
      ? "Start time not published; heat spread over 18:00–20:00. "
      : "";
    const whyId = "why-" + ev.id;
    const noCapacity = !!(ev.basis && ev.basis.capacity_unknown);
    const whyLabel = noCapacity ? "Why no estimate?" : "Why this number?";
    const why = ev.basis ? whyMarkup(ev) : "";
    const dir = directionsHref(ev);
    const actions = dir || ev.start != null
      ? `<div class="pd-actions">` +
        (dir ? `<a class="pd-act" href="${esc(dir)}" target="_blank" rel="noopener">Directions</a>` : "") +
        (ev.start != null ? `<button class="pd-act" type="button" data-ics="${esc(ev.id)}">Add to calendar</button>` : "") +
        `</div>`
      : "";
    const timing = arrivalTiming(ev);
    const timingLine = timing
      ? `<div class="pd-arrival">Quietest arrival ≈ ${esc(timing.quietest)}; most arrive ≈ ${esc(timing.peak)}.</div>`
      : "";
    box.className = "panel-detail on";
    box.innerHTML =
      `<div class="pd-title">${esc(ev.title)}</div>` +
      `<div class="pd-meta">${esc(time)}${esc(end)} · ${esc(ev.venue)}` +
      `${addr ? " · " + esc(addr) : ""}</div>` +
      `<div class="pd-meta"><span class="cat cat-${esc(ev.category)}">${esc(CAT_LABEL[ev.category] || "Event")}</span>` +
      `${ev.mid != null ? `<span class="pd-est">≈ ${ev.mid.toLocaleString("fi-FI")} people, estimated</span>` : noCapacity ? `<span class="pd-est">No crowd estimate · capacity unpublished</span>` : ""}</div>` +
      `<div class="pd-note">${timeNote}${noCapacity ? "Capacity is unpublished, so no crowd estimate is shown." : "Estimate, not a measurement."}</div>` +
      timingLine +
      actions +
      (ev.basis ? `<button class="pd-why-btn" type="button" aria-expanded="false" ${IS_MOBILE ? `aria-haspopup="dialog" aria-controls="whySheet"` : `aria-controls="${esc(whyId)}"`}>${whyLabel}</button>` +
        (IS_MOBILE ? "" : `<div class="pd-why" id="${esc(whyId)}" hidden>${why}</div>`) : "");
    const icsBtn = box.querySelector("[data-ics]");
    if (icsBtn) icsBtn.addEventListener("click", () => downloadIcs(ev));
    const whyBtn = box.querySelector(".pd-why-btn");
    if (whyBtn) {
      whyBtn.addEventListener("click", () => {
        if (IS_MOBILE) {
          openWhySheet(ev, why, whyBtn);
          return;
        }
        const panel = $(whyId);
        if (!panel) return;
        const open = panel.hidden;
        panel.hidden = !open;
        whyBtn.setAttribute("aria-expanded", String(open));
        whyBtn.textContent = open ? "Hide the working" : whyLabel;
      });
    }
  }

  function openWhySheet(ev, content, trigger) {
    const sheet = $("whySheet");
    if (!sheet) return;
    $("whySheetTitle").textContent = ev.basis && ev.basis.capacity_unknown ? "Why no estimate?" : "Why this number?";
    $("whySheetEvent").textContent = ev.title;
    $("whySheetBody").innerHTML = content;
    sheetTrigger = trigger;
    trigger.setAttribute("aria-expanded", "true");
    sheet.showModal();
    document.body.classList.add("sheet-open");
    $("whySheetClose").focus({ preventScroll: true });
  }

  function wireWhySheet() {
    const sheet = $("whySheet");
    if (!sheet) return;
    $("whySheetClose").addEventListener("click", () => sheet.close());
    sheet.addEventListener("click", (e) => { if (e.target === sheet) sheet.close(); });
    sheet.addEventListener("close", () => {
      document.body.classList.remove("sheet-open");
      if (!sheetTrigger) return;
      sheetTrigger.setAttribute("aria-expanded", "false");
      sheetTrigger.focus({ preventScroll: true });
      sheetTrigger = null;
    });
  }

  function whyMarkup(ev) {
    const b = ev.basis || {};
    const att = ev.attendance || {};
    const cal = CALIBRATION || {};
    const liiga = cal.liiga || {};
    const city = cal.city_capacity || {};
    const n = (v) => v == null ? "—" : Number(v).toLocaleString("fi-FI");
    const pct = (v) => v == null ? "—" : Math.round(v * 100) + "%";
    const signals = (ev.interest && ev.interest.signals || []).slice(0, 4)
      .map((s) => `${esc(s.name)} ${s.points > 0 ? "+" : ""}${s.points}`).join(" · ") || "baseline";
    const hockey = ev.category === "sports" && ev.sub === "hockey";
    let test = "";
    if (hockey) {
      if (liiga.status === "FITTED" && liiga.sample) {
        test = `Backtest: ${n(liiga.sample)} completed Liiga games with reported spectators; ` +
          `leave-one-out median error ${pct(liiga.median_ape)}, bias ${liiga.bias >= 0 ? "+" : ""}${pct(liiga.bias)}` +
          ` (${liiga.bias >= 0 ? "over" : "under"}estimates), ${pct(liiga.within_20pct)} within ±20%.`;
      } else if (liiga.status === "PRIOR" && liiga.sample) {
        test = `Calibration: ${n(liiga.sample)} completed Liiga games with reported spectators; ` +
          `the fitted factor did not beat the prior on the backtest, so the prior is kept.`;
      } else if (liiga.sample) {
        test = `Calibration: only ${n(liiga.sample)} completed Liiga game(s) with reported spectators; ` +
          `too few to fit, so the prior is kept.`;
      } else {
        test = "No completed Liiga game with reported attendance yet; the hockey fill is still a prior.";
      }
    } else {
      test = "Only Liiga hockey has reported attendance for a backtest; this event's fill is a category prior.";
    }
    const cityLine = city.events_with_published_capacity
      ? `City calendar: ${n(city.events_with_published_capacity)} event(s) in this build carry a published maxParticipants; ` +
        `capacity is the lower of it and the venue's own capacity. It is not measured attendance.`
      : "City calendar: no event in this build has a published maxParticipants.";
    const noCapacity = !!b.capacity_unknown;
    const collision = b.venue_collision || {};
    const collisionLine = collision.group_size > 1
      ? `<div class="why-row"><span>Venue split</span><span><b>${collision.factor < 1 ? "×" + Number(collision.factor).toFixed(2) : "shared"}</b><small>${n(collision.group_size)} events at this venue and start; room split not published; combined cap ${n(collision.venue_capacity)}</small></span></div>`
      : "";
    const comp = b.competition || {};
    const compLine = comp.factor != null && comp.factor < 0.999
      ? `<div class="why-row"><span>Competition</span><span><b>×${Number(comp.factor).toFixed(2)}</b><small>${n(comp.peers)} concurrent event(s) sharing a catchment; shared demand, not a measured split</small></span></div>`
      : "";
    const workingRows = noCapacity
      ? `<div class="why-note">No crowd estimate is published: the venue's capacity is unpublished.</div>`
      : `<div class="why-row"><span>Fill</span><span><b>${pct(b.fill)}</b><small>${esc(b.fill_source || "category prior")}</small></span></div>` +
        `<div class="why-row"><span>Interest</span><span><b>${n(b.interest)}/100</b><small>${signals}</small></span></div>` +
        `<div class="why-row"><span>Band</span><span><b>≈ ${n(att.low)}–${n(att.high)}</b><small>mid ${n(att.mid)}; ±${pct(b.spread)}</small></span></div>`;
    return `<div class="why-row"><span>Capacity</span><span><b>${noCapacity ? "not published" : n(b.capacity)}</b><small>${esc(b.capacity_source || "unknown")}</small></span></div>` +
      workingRows +
      collisionLine +
      compLine +
      `<div class="why-note">${noCapacity ? "No capacity means no attendance band; the event is listed but adds no heat." : test}</div>` +
      `<div class="why-note">${cityLine}</div>`;
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
    if (dayEvents.length) {
      const now = +$("timeSlider").value;
      list.innerHTML = dayEvents.map((e) => {
        const occurring = e.start != null && e.end != null && now >= e.start && now < e.end;
        const soon = e.start != null && !occurring && now >= e.start - 120 && now < e.start;
        const addr = addrOf(e);
        return `<li class="panelRow${occurring ? " on" : ""}${soon ? " soon" : ""}" data-id="${esc(e.id)}" tabindex="0" role="button">` +
          `<span class="pr-time">${esc(e.timeKnown === false ? "TBA" : (e.time || "—"))}</span>` +
          `<span class="pr-body"><span class="pr-title">${esc(e.title)}</span>` +
          `<span class="pr-venue">${esc(e.venue)}${addr ? " · " + esc(addr) : ""}</span></span>` +
          `<span class="cat cat-${esc(e.category)}">${esc(CAT_LABEL[e.category] || "Event")}</span></li>`;
      }).join("");
      list.querySelectorAll(".panelRow[data-id]").forEach((row) => {
        const id = row.dataset.id;
        row.addEventListener("mouseenter", () => { select(id); window.KMap.focusEvent(id); });
        row.addEventListener("mouseleave", () => { if (selectedId === id) window.KMap.focusEvent(null); });
        row.addEventListener("click", () => { select(id); window.KMap.focusEvent(id); });
        row.addEventListener("keydown", (e) => {
          if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
            e.preventDefault();
            select(id);
            window.KMap.focusEvent(id);
          }
        });
        row.addEventListener("focus", () => { select(id); window.KMap.focusEvent(id); });
      });
      renderDetail(selectedId && dayEvents.some((e) => e.id === selectedId) ? selectedId : null);
    } else {
      list.innerHTML = `<li class="panelRow empty">No events on this day.</li>`;
      renderDetail(null);
    }
    renderSpark();
  }

  /* -------------------------------------------------------------- day sparkline
     Total people on routes for each 15-minute slot of the day, read from the same
     per-event enRoute model the map uses. Shows the crush hour at a glance. */
  const SPARK = { start: 360, end: 1800, step: 15, w: 240, h: 32, pad: 2 };

  function renderSpark() {
    const row = $("sparkRow");
    const svg = $("daySpark");
    const peakEl = $("sparkPeak");
    if (!row || !svg) return;
    if (!dayEvents.length) {
      row.hidden = true;
      svg.innerHTML = "";
      if (peakEl) peakEl.textContent = "";
      return;
    }
    row.hidden = false;

    const totals = [];
    let maxP = 0, peakIdx = 0;
    for (let m = SPARK.start; m <= SPARK.end; m += SPARK.step) {
      const t = window.KMap.dayPeople(m);
      if (t > maxP) { maxP = t; peakIdx = totals.length; }
      totals.push(t);
    }

    const n = totals.length;
    const maxT = maxP || 1;
    const coords = totals.map((t, i) => {
      const x = (i / (n - 1)) * SPARK.w;
      const y = SPARK.h - SPARK.pad - (t / maxT) * (SPARK.h - 2 * SPARK.pad);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
    const line = coords.join(" ");
    const area = `0,${SPARK.h} ${line} ${SPARK.w},${SPARK.h}`;
    const curIdx = Math.max(0, Math.min(n - 1, Math.round((+$("timeSlider").value - SPARK.start) / SPARK.step)));
    const curX = ((curIdx / (n - 1)) * SPARK.w).toFixed(1);
    const peakMin = SPARK.start + peakIdx * SPARK.step;
    const peakLabel = window.KMap.clockLabel(peakMin) + (peakMin >= 24 * 60 ? " +1" : "");
    const [peakX, peakY] = coords[peakIdx].split(",");

    svg.innerHTML =
      `<polygon points="${area}" fill="rgba(209,51,25,.12)" />` +
      `<polyline points="${line}" fill="none" stroke="var(--brick)" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" />` +
      `<line id="sparkCursor" x1="${curX}" y1="0" x2="${curX}" y2="${SPARK.h}" stroke="var(--amber)" stroke-width="1" opacity=".8" />` +
      `<circle cx="${peakX}" cy="${peakY}" r="2.6" fill="var(--amber)" stroke="var(--ink-2)" stroke-width="1" />`;
    if (peakEl) peakEl.textContent = `peak ${peakLabel} · ≈ ${Math.round(maxP).toLocaleString("fi-FI")}`;
  }

  function updateSparkCursor() {
    const row = $("sparkRow");
    const cursor = $("sparkCursor");
    if (!row || row.hidden || !cursor) return;
    const n = (SPARK.end - SPARK.start) / SPARK.step + 1;
    const idx = Math.max(0, Math.min(n - 1, Math.round((+$("timeSlider").value - SPARK.start) / SPARK.step)));
    const x = ((idx / (n - 1)) * SPARK.w).toFixed(1);
    cursor.setAttribute("x1", x);
    cursor.setAttribute("x2", x);
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

  /* -------------------------------------------------------------- playback
     The ▶ button walks the hour from 06:00 to 06:00 so the arrival and egress
     curves can be watched. The map stays in scrubbing mode for the run. */
  let playTimer = null;
  let playing = false;

  function stopPlay() {
    if (playTimer) { clearInterval(playTimer); playTimer = null; }
    if (playing) { playing = false; window.KMap.setScrubbing(false); }
    const btn = $("timePlay");
    if (btn) {
      btn.textContent = "▶";
      btn.classList.remove("playing");
      btn.setAttribute("aria-label", "Play the day from 06:00 to 06:00");
    }
  }

  function startPlay() {
    if (playing) return;
    playing = true;
    window.KMap.setScrubbing(true);
    const btn = $("timePlay");
    if (btn) { btn.textContent = "⏸"; btn.classList.add("playing"); btn.setAttribute("aria-label", "Pause"); }
    // an hour at 06:00 the next morning is the end of the day, so start over
    let min = window.KMap.now() >= 1800 ? 360 : window.KMap.now();
    window.KMap.setTime(min);
    setTime(min, true);
    updatePanelNow();
    playTimer = setInterval(() => {
      min += 15;
      if (min > 1800) { stopPlay(); return; }
      window.KMap.setTime(min);
      setTime(min, true);
      updatePanelNow();
    }, 160);
  }

  function renderStatus(meta) {
    const pill = $("updatedBadge");
    const generated = meta.generated ? Date.parse(meta.generated.replace(" UTC", "Z").replace(" ", "T")) : NaN;
    const age = Number.isFinite(generated) ? (Date.now() - generated) / 86400000 : 99;
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
    const liiga = meta.calibration && meta.calibration.liiga;
    const calNote = $("calibrationNote");
    if (calNote) {
      const cityNote = " City maxParticipants is a cap, not measured attendance.";
      if (liiga && liiga.status === "FITTED" && liiga.sample) {
        const bias = Math.round((liiga.bias || 0) * 100);
        calNote.textContent =
          `Calibration: ${liiga.sample} completed Liiga games with reported attendance; ` +
          `leave-one-out median error ${Math.round(liiga.median_ape * 100)}%, ` +
          `bias ${bias >= 0 ? "+" : ""}${bias}%.` + cityNote;
      } else if (liiga && liiga.status === "PRIOR" && liiga.sample) {
        calNote.textContent =
          `Calibration: ${liiga.sample} completed Liiga games; the fitted factor did not beat the ` +
          `prior on the backtest, so the prior is kept.` + cityNote;
      } else if (liiga && liiga.sample) {
        calNote.textContent =
          `Calibration: only ${liiga.sample} completed Liiga game(s) with reported attendance; ` +
          `too few to fit, so the hockey fill is a prior.` + cityNote;
      } else {
        calNote.textContent =
          "Calibration: no completed Liiga games with reported attendance; the hockey fill is a prior." + cityNote;
      }
    }
    $("roadNote").textContent =
      `Close districts walk; farther ones ride tram, bus or train, so their corridor follows the main road. ` +
      `Model ${meta.model_version || CFG.MODEL_VERSION}.`;
    $("footNote").innerHTML =
      `Every number is an <b>estimate</b> from a population model — not measured attendance, not tracking. ` +
      `Basemap © OpenStreetMap contributors. Music data from ` +
      `<a href="https://github.com/zakker111/tampere-keikat" target="_blank" rel="noopener">Tampere Keikat</a> (MIT); ` +
      `hockey fixtures from the Liiga game list. Every event shown comes from a published feed — ` +
      `placeholder rows are not published. Events without a listed start are marked TBA and ` +
      `their heat is spread over 18:00–20:00. Concurrent events sharing a catchment share one demand pool. ` +
      `Multiple events at one venue and published start share one building cap; an unpublished ` +
      `room split is flagged. The heat counts people travelling in before a start and heading home ` +
      `after an estimated end.`;
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
    CALIBRATION = data.calibration || null;
    wireWhySheet();
    const events = toEvents(data.events || []);
    const days = buildDays(events);

    window.KMap.onHover(select);
    await window.KMap.init(events);

    if (days.length) {
      // init() already chose the day and its peak hour; don't repeat the whole
      // peak scan here just to arrive at the same minute.
      const first = window.KMap.currentDay() || days[0];
      const min = window.KMap.now();
      curDay = first;
      markDay(first);
      revealDay(document.querySelector(`.day[data-day="${first}"]`));
      setTime(min, true);
    } else {
      $("estimate").innerHTML = `<div class="e-line">No events in the feed right now.</div>`;
    }
    renderPanel();

    let queued = 0;
    let scrubTimer = 0;

    $("timePlay").addEventListener("click", () => (playing ? stopPlay() : startPlay()));

    $("timeSlider").addEventListener("input", (e) => {
      stopPlay();
      window.KMap.setScrubbing(true);
      setTime(+e.target.value, false);
      if (queued) cancelAnimationFrame(queued);
      queued = requestAnimationFrame(() => {
        queued = 0;
        window.KMap.setTime(+$("timeSlider").value);
        updatePanelNow();
      });
      clearTimeout(scrubTimer);
      scrubTimer = setTimeout(() => window.KMap.setScrubbing(false), 160);
    });

    // A pasted or edited #hash moves the map itself; bring the day strip, the
    // hour slider and the panel along with it instead of leaving them stale.
    window.addEventListener("kmap:view", () => {
      stopPlay();
      const day = window.KMap.currentDay();
      if (!day) return;
      curDay = day;
      markDay(day);
      revealDay(document.querySelector(`.day[data-day="${day}"]`));
      setTime(window.KMap.now(), true);
      renderPanel();
    });
  }

  document.addEventListener("DOMContentLoaded", load);
})();
