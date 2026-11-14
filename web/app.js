/* Kilinkolin — pick a day, pick an hour, see the estimated crowd on its routes. */
(() => {
  const CFG = window.KILINKOLIN || {};
  const $ = (id) => document.getElementById(id);
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

  function stamp(raw) {
    const m = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}) UTC$/.exec(raw || "");
    if (!m) return raw || "unknown";
    const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]));
    return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" }) + `, ${m[4]}:${m[5]} UTC`;
  }

  const dayLabel = (iso) => {
    const p = (iso || "").split("-");
    if (p.length !== 3) return iso || "";
    const d = new Date(+p[0], +p[1] - 1, +p[2]);
    return `${DOW[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]}`;
  };

  function toEvents(rows) {
    return rows.map((r) => ({
      date: r[0], time: r[1] || "", title: r[2], venue: r[3],
      id: r[7], seed: !!r[13]
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
        markDay(btn.dataset.day);
        setTime(min, true);
      };
    });
    return days;
  }

  function markDay(day) {
    document.querySelectorAll(".day").forEach((b) => b.classList.toggle("on", b.dataset.day === day));
  }

  function setTime(min, moveSlider) {
    if (moveSlider) $("timeSlider").value = String(min);
    $("timeLabel").textContent = window.KMap.clockLabel(min);
  }

  function renderStatus(meta) {
    const pill = $("updatedBadge");
    const age = meta.generated ? (Date.now() - Date.parse(meta.generated.replace(" UTC", "Z"))) / 86400000 : 99;
    pill.classList.add(age > 8 ? "stale" : "live");
    pill.querySelector(".status-text").textContent = meta.generated
      ? `Estimated flow model · rebuilt ${stamp(meta.generated)}`
      : "Bundled snapshot";
  }

  function renderFoot(meta) {
    $("roadNote").textContent =
      `Close districts walk; farther ones ride tram, bus or train, so their corridor follows the main road. ` +
      `Model ${meta.model_version || CFG.MODEL_VERSION}.`;
    $("footNote").innerHTML =
      `Every number is an <b>estimate</b> from a population model — not measured attendance, not tracking. ` +
      `Basemap © OpenStreetMap contributors. Music data from ` +
      `<a href="https://github.com/zakker111/tampere-keikat" target="_blank" rel="noopener">Tampere Keikat</a> (MIT); ` +
      `rows marked SAMPLE are placeholders.`;
  }

  async function load() {
    let data = { events: [], coverage: {} };
    try {
      const r = await fetch("./data.json", { cache: "no-store" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      data = await r.json();
    } catch (err) {
      console.warn("data.json unavailable", err);
    }
    renderStatus(data);
    renderFoot(data);
    const events = toEvents(data.events || []);
    const days = buildDays(events);
    await window.KMap.init(events);

    if (days.length) {
      const first = days[0];
      const min = window.KMap.setDay(first);
      markDay(first);
      setTime(min, true);
    } else {
      $("estimate").innerHTML = `<div class="e-line">No events in the feed right now.</div>`;
    }

    $("timeSlider").addEventListener("input", (e) => {
      const min = +e.target.value;
      setTime(min, false);
      window.KMap.setTime(min);
    });
  }

  document.addEventListener("DOMContentLoaded", load);
})();
