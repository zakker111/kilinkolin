import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

// Rows are pointer targets that can move: the detail card above the list once
// grew on hover, and the list is rebuilt when a day's bundle arrives, so a
// scroll-then-click across protocol round trips could hit a neighbour ("element
// is not stable") or a row that had already been replaced ("element is not
// attached to the DOM"). Rows are buttons (tabindex=0, Enter/Space), so select
// one by id, scrolling and focusing it in a single page call where a rebuild
// simply means the next poll tries again. The pointer paths stay covered by the
// map-dot and phone tap tests.
const rowTops = (page) => page.evaluate(() => [...document.querySelectorAll("#panelList .panelRow[data-id]")]
  .map((row) => Math.round(row.getBoundingClientRect().top)));

async function activateRow(page, id) {
  await page.waitForFunction((rowId) => {
    const row = document.querySelector(`#panelList .panelRow[data-id="${rowId}"]`);
    if (!row) return false;
    row.scrollIntoView({ block: "nearest" });
    row.focus();
    return document.activeElement === row && row.classList.contains("sel");
  }, id);
}

async function openHockeyWithCalibration(page, mutate) {
  await page.route("**/data.json", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    mutate(data.calibration.liiga);
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(data) });
  });
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#dayStrip .day").first()).toBeVisible();
  await page.waitForFunction(() => window.KMap && window.KMap.dayEvents().length > 0);

  const hockey = await page.evaluate(async () => {
    const data = await fetch("./data.json").then((r) => r.json());
    const event = (data.events || []).find((row) => row[9] === "sports" && row[10] === "hockey");
    return event ? { date: event[0], id: event[7] } : null;
  });
  expect(hockey).not.toBeNull();
  await page.locator(`.day[data-day="${hockey.date}"]`).click();
  await activateRow(page, hockey.id);
  await page.locator("#panelDetail .pd-why-btn").click();
  await expect(page.locator("#panelDetail .pd-why")).toBeVisible();
}

test.describe("Kilinkolin smoke", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.locator("#dayStrip .day").first()).toBeVisible();
    await expect(page.locator("#panelList")).toBeVisible();
    await page.waitForFunction(() => window.KMap && window.KMap.dayEvents().length > 0);
  });

  test("switching days changes the active day and the panel", async ({ page }) => {
    const openDay = await page.evaluate(() => window.KMap.currentDay());
    await expect(page.locator(`.day[data-day="${openDay}"]`)).toHaveClass(/on/);
    const firstTitle = await page.locator("#panelTitle").innerText();

    const targetDay = await page.evaluate((day) =>
      [...document.querySelectorAll(".day")].map((b) => b.dataset.day).find((d) => d !== day), openDay);
    const target = page.locator(`.day[data-day="${targetDay}"]`);
    await target.click();

    await expect(target).toHaveClass(/on/);
    await expect(page.locator(".day.on")).toHaveCount(1);
    await expect(page.locator("#panelTitle")).not.toHaveText(firstTitle);
    await expect(page.locator("#panelTitle")).toContainText("What's on");
    await expect(page.locator("#panelList .panelRow").first()).toBeVisible();
    expect(await page.evaluate(() => window.KMap.currentDay())).toBe(targetDay);
  });

  test("opens on today in the 15-minute slot in progress and ranks it against the week", async ({ page }) => {
    // Today in Tampere, in the page's 06:00–06:00 day window.
    const now = await page.evaluate(() => {
      const parts = {};
      new Intl.DateTimeFormat("en-GB", {
        timeZone: "Europe/Helsinki", hour12: false,
        year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
      }).formatToParts(new Date()).forEach((part) => { parts[part.type] = part.value; });
      const minutes = (+parts.hour % 24) * 60 + +parts.minute;
      const d = new Date(`${parts.year}-${parts.month}-${parts.day}T00:00:00`);
      if (minutes < 360) d.setDate(d.getDate() - 1);
      const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      const raw = minutes < 360 ? minutes + 1440 : minutes;
      // 360 is on the 15-minute grid: the slot in progress, never the next one
      return { day: iso, minutes: Math.floor(raw / 15) * 15 };
    });
    const days = await page.evaluate(() => [...document.querySelectorAll(".day")].map((b) => b.dataset.day));
    if (days.includes(now.day)) {
      expect(await page.evaluate(() => window.KMap.currentDay())).toBe(now.day);
      const opened = await page.evaluate(() => window.KMap.now());
      expect(opened).toBe(now.minutes);
      // the label, the slider and the chip tooltip all name that same slot
      const view = await page.evaluate(() => ({
        label: document.getElementById("timeLabel").textContent,
        slider: Number(document.getElementById("timeSlider").value),
        chip: document.getElementById("weekChip").title,
      }));
      const clock = String(Math.floor(opened / 60) % 24).padStart(2, "0") +
        ":" + String(opened % 60).padStart(2, "0");
      expect(view.label).toBe(opened >= 1440 ? `${clock} +1` : clock);
      expect(view.slider).toBe(opened);
      expect(view.chip).toContain(`at ${clock}`);
    }
    await expect(page.locator(".day.on")).toHaveCount(1);
    await expect(page.locator("#weekChip")).toBeVisible();
    await expect(page.locator("#weekChip")).toContainText(/busier than \d+% of this week's minutes/);
    await expect(page.locator("#weekChip")).toHaveAttribute("title", /published 15-minute slots/);
  });

  test("every day bundle's build-time people curve matches the browser model", async ({ page }) => {
    // `build.py` and `map.js` carry the same enRoute rule in two languages: Python
    // writes each day's `people[]` curve, the browser recomputes it for the sparkline
    // and the estimate. Recompute every published slot here so a change to one side
    // that the other did not follow fails the build instead of shipping a heat map
    // that disagrees with its own bundle.
    test.setTimeout(300_000);
    const report = await page.evaluate(async () => {
      // The build rounds each slot to 0.1; anything this far off is a real drift,
      // not the rounding of two equally ordered sums.
      const tolerance = 0.06;
      const days = [...document.querySelectorAll(".day")].map((b) => b.dataset.day);
      const problems = [];
      let checkedDays = 0, checkedSlots = 0, worst = 0;
      for (const day of days) {
        const bundle = await fetch(`./geo/days/${day}.json`, { cache: "no-store" }).then((r) => r.json());
        const curve = Array.isArray(bundle.people) ? bundle.people : null;
        if (!curve) { problems.push(`${day}: bundle has no people curve`); continue; }
        if (curve.length !== 97) { problems.push(`${day}: curve has ${curve.length} slots, expected 97`); continue; }
        const week = bundle.week || {};
        const start = week.start_minute == null ? 360 : week.start_minute;
        const step = week.slot_minutes || 15;
        // load this bundle into the browser before asking it for the same slots
        if (await window.KMap.setDay(day) == null) {
          problems.push(`${day}: browser could not load the day bundle`);
          continue;
        }
        curve.forEach((people, i) => {
          const slot = start + i * step;
          const browser = window.KMap.dayPeople(slot);
          const diff = Math.abs(browser - people);
          if (diff > worst) worst = diff;
          if (diff > tolerance) problems.push(`${day} ${slot}: bundle ${people}, browser ${browser.toFixed(3)}`);
          checkedSlots += 1;
        });
        checkedDays += 1;
      }
      return { days: days.length, checkedDays, checkedSlots,
               worst: Number(worst.toFixed(3)),
               problemCount: problems.length, problems: problems.slice(0, 15) };
    });
    expect(report.problemCount, JSON.stringify(report.problems)).toBe(0);
    expect(report.checkedDays).toBe(report.days);
    expect(report.checkedSlots).toBe(report.days * 97);
  });

  test("the hour slider handles both 06:00 extremes", async ({ page }) => {
    const slider = page.locator("#timeSlider");
    await expect(slider).toHaveAttribute("min", "360");
    await expect(slider).toHaveAttribute("max", "1800");

    await slider.evaluate((el) => {
      el.value = el.min;
      el.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await expect(page.locator("#timeLabel")).toHaveText("06:00");
    await expect(page.locator("#estimate .e-title")).toContainText("06:00");

    await slider.evaluate((el) => {
      el.value = el.max;
      el.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await expect(page.locator("#timeLabel")).toHaveText("06:00 +1");
    await expect(page.locator("#estimate .e-title")).toContainText("06:00");
  });

  test("the event panel explains the estimate", async ({ page }) => {
    const row = page.locator("#panelList .panelRow[data-id]").first();
    await activateRow(page, await row.getAttribute("data-id"));

    const button = page.locator("#panelDetail .pd-why-btn");
    await expect(button).toBeVisible();
    await expect(button).toHaveText("Why this number?");
    const why = page.locator("#panelDetail .pd-why");
    await expect(why).toBeHidden();

    await button.click();
    await expect(why).toBeVisible();
    await expect(button).toHaveText("Hide the working");
    await expect(button).toHaveAttribute("aria-expanded", "true");
    await expect(why).toContainText("Capacity");
    await expect(why).toContainText("Fill");
    await expect(why).toContainText("Band");
    await expect(why).toContainText("City calendar");
  });

  test("hovering a row keeps the list under the pointer", async ({ page }) => {
    // The detail card used to grow above the list on hover (a 52px hint to a
    // 130-164px card), sliding the rows down so the pointer ended over a
    // neighbour. Hover a row and check that the rows do not move.
    const rows = page.locator("#panelList .panelRow[data-id]");
    await expect(rows.first()).toBeVisible();
    expect(await rows.count()).toBeGreaterThan(1);

    const before = await rowTops(page);

    const target = rows.nth(1);
    const id = await target.getAttribute("data-id");
    const title = (await target.locator(".pr-title").innerText()).trim();
    const box = await target.boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);

    await expect(page.locator("#panelList .panelRow.sel")).toHaveAttribute("data-id", id);
    expect((await page.locator("#panelDetail .pd-title").innerText()).trim()).toBe(title);
    expect(await rowTops(page)).toEqual(before);

    // the pointer is still over the row it selected, not a neighbour
    const under = await page.evaluate(() => {
      const row = document.querySelector("#panelList .panelRow.sel");
      const rect = row.getBoundingClientRect();
      const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
      return !!hit && hit.closest(".panelRow") === row;
    });
    expect(under).toBe(true);
  });

  test("published events have no exact duplicate listings", async ({ page }) => {    const duplicates = await page.evaluate(async () => {
      const data = await fetch("./data.json").then((r) => r.json());
      const seen = new Map();
      for (const row of data.events || []) {
        const title = (row[2] || "").toLowerCase()
          .replace(/[^\p{L}\p{N}\s]+/gu, "").trim().replace(/\s+/g, " ");
        const key = [row[0], row[14], row[1] || "", title].join("|");
        seen.set(key, (seen.get(key) || 0) + 1);
      }
      return [...seen].filter(([, count]) => count > 1);
    });
    expect(duplicates).toEqual([]);
  });

  test("an event without a published start is labelled TBA", async ({ page }) => {
    const missing = await page.evaluate(async () => {
      const [data, flows] = await Promise.all([
        fetch("./data.json").then((r) => r.json()),
        fetch("./geo/flows.json").then((r) => r.json()),
      ]);
      const row = (data.events || []).find((event) => !event[1]);
      const flow = row && (flows.events || []).find((item) => item.id === row[7]);
      return row && flow ? {
        date: row[0], id: row[7], title: row[2],
        options: flow.start_options, window: flow.start_window,
      } : null;
    });
    expect(missing, "the feed should include at least one event without a start").not.toBeNull();
    expect(missing.options).toEqual([18 * 60, 19 * 60, 20 * 60]);
    expect(missing.window).toBe("18:00–20:00");

    await page.locator(`.day[data-day="${missing.date}"]`).click();
    await page.waitForFunction((day) => window.KMap.currentDay() === day, missing.date);
    const spread = await page.evaluate(async (id) => {
      const flows = await fetch("./geo/flows.json").then((r) => r.json());
      const flow = (flows.events || []).find((item) => item.id === id);
      return flow ? {
        mid: flow.attendance.mid,
        values: [18 * 60, 19 * 60, 20 * 60].map((minute) => window.KMap.eventPeople(id, minute)),
      } : null;
    }, missing.id);
    expect(spread).not.toBeNull();
    expect(spread.values.every((value) => value > 0)).toBe(true);
    expect(spread.values[1]).toBeLessThan(spread.mid);

    const row = page.locator(`#panelList .panelRow[data-id="${missing.id}"]`);
    await expect(row).toBeVisible();
    await expect(row.locator(".pr-time")).toHaveText("TBA");
    await activateRow(page, missing.id);
    await expect(page.locator("#panelDetail .pd-meta").first()).toContainText("Start TBA");
    await expect(page.locator("#panelDetail .pd-note").first()).toContainText("spread over 18:00–20:00");
    // no invented start: a TBA row gets directions, never a calendar entry
    await expect(page.locator("#panelDetail a.pd-act")).toHaveText("Directions");
    await expect(page.locator("#panelDetail [data-ics]")).toHaveCount(0);
  });

  test("a TBA event's heat is spread across its documented window", async ({ page }) => {
    // Redundant with the spread assertion in the TBA label test; kept as a
    // focused regression once the day's flow has been loaded.
    const target = await page.evaluate(async () => {
      const [data, flows] = await Promise.all([
        fetch("./data.json").then((r) => r.json()),
        fetch("./geo/flows.json").then((r) => r.json()),
      ]);
      const row = (data.events || []).find((event) => !event[1]);
      const flow = row && (flows.events || []).find((item) => item.id === row[7]);
      return row && flow ? { date: row[0], id: flow.id, mid: flow.attendance.mid } : null;
    });
    expect(target).not.toBeNull();
    await page.locator(`.day[data-day="${target.date}"]`).click();
    await page.waitForFunction((day) => window.KMap.currentDay() === day, target.date);
    const values = await page.evaluate((id) => [18 * 60, 19 * 60, 20 * 60]
      .map((minute) => window.KMap.eventPeople(id, minute)), target.id);
    expect(values.every((value) => value > 0)).toBe(true);
    expect(values[1]).toBeLessThan(target.mid);
  });

  test("a discounted event explains its competition factor", async ({ page }) => {
    const target = await page.evaluate(async () => {
      const [data, flows] = await Promise.all([
        fetch("./data.json").then((r) => r.json()),
        fetch("./geo/flows.json").then((r) => r.json()),
      ]);
      const byId = new Map((flows.events || []).map((flow) => [flow.id, flow]));
      const row = (data.events || []).find((event) => {
        const comp = (((byId.get(event[7]) || {}).basis || {}).competition) || {};
        return comp.peers > 0 && comp.factor < 0.999;
      });
      return row ? { date: row[0], id: row[7] } : null;
    });
    expect(target, "the build should discount at least one concurrent event").not.toBeNull();

    await page.locator(`.day[data-day="${target.date}"]`).click();
    // The day button is disabled while its bundle loads and the panel is
    // rebuilt afterwards; wait for the switch so the row locator is not
    // detached by that re-render.
    await page.waitForFunction((day) => window.KMap.currentDay() === day, target.date);
    await activateRow(page, target.id);
    await page.locator("#panelDetail .pd-why-btn").click();
    const why = page.locator("#panelDetail .pd-why");
    await expect(why).toContainText("Competition");
    await expect(why).toContainText("concurrent event(s) sharing a catchment");
  });

  test("same-venue events share a capped building estimate", async ({ page }) => {
    const target = await page.evaluate(async () => {
      const [data, flows] = await Promise.all([
        fetch("./data.json").then((r) => r.json()),
        fetch("./geo/flows.json").then((r) => r.json()),
      ]);
      const flow = (flows.events || []).find((item) =>
        item.basis && item.basis.venue_collision && item.basis.venue_collision.group_size > 1);
      if (!flow) return null;
      const row = (data.events || []).find((event) => event[7] === flow.id);
      return row ? {
        date: row[0], id: flow.id,
        collision: flow.basis.venue_collision,
      } : null;
    });
    expect(target, "the build should flag a same-venue collision").not.toBeNull();
    expect(target.collision.combined_mid_after).toBeLessThanOrEqual(target.collision.venue_capacity);
    expect(target.collision.room_split).toBe("UNRESOLVED");

    await page.locator(`.day[data-day="${target.date}"]`).click();
    // The day button is disabled while its bundle loads and the panel is
    // rebuilt afterwards; wait for the switch so the row locator is not
    // detached by that re-render.
    await page.waitForFunction((day) => window.KMap.currentDay() === day, target.date);
    await activateRow(page, target.id);
    await page.locator("#panelDetail .pd-why-btn").click();
    const why = page.locator("#panelDetail .pd-why");
    await expect(why).toContainText("Venue split");
    if (target.collision.room_split === "UNRESOLVED") {
      await expect(why).toContainText("room split not published");
    }
  });

  test("published capacity caps are not exceeded", async ({ page }) => {
    const result = await page.evaluate(async () => {
      const [data, flows] = await Promise.all([
        fetch("./data.json").then((r) => r.json()),
        fetch("./geo/flows.json").then((r) => r.json()),
      ]);
      const bad = [];
      for (const flow of flows.events || []) {
        const basis = flow.basis || {};
        const cap = basis.published_max_participants;
        if (cap == null) continue;
        if (basis.capacity > cap || flow.attendance.mid > cap) {
          bad.push({ id: flow.id, cap, capacity: basis.capacity, mid: flow.attendance.mid });
        }
      }
      return bad;
    });
    expect(result).toEqual([]);
  });

  test("a Liiga hockey event shows the fitted fill and backtest", async ({ page }) => {
    const hockey = await page.evaluate(async () => {
      const data = await fetch("./data.json").then((r) => r.json());
      const event = (data.events || []).find((row) => row[9] === "sports" && row[10] === "hockey");
      return event ? { date: event[0], title: event[2], calibration: (data.calibration || {}).liiga || null } : null;
    });
    expect(hockey, "the feed should publish at least one Liiga hockey game").not.toBeNull();
    expect(hockey.calibration, "the build should publish Liiga calibration").not.toBeNull();
    expect(hockey.calibration.status).toBe("FITTED");
    expect(hockey.calibration.sample).toBeGreaterThanOrEqual(8);

    await page.locator(`.day[data-day="${hockey.date}"]`).click();
    await page.waitForFunction((day) => window.KMap.currentDay() === day, hockey.date);
    const row = page.locator("#panelList .panelRow[data-id]").filter({ hasText: hockey.title }).first();
    await expect(row).toBeVisible();
    await activateRow(page, await row.getAttribute("data-id"));

    const button = page.locator("#panelDetail .pd-why-btn");
    await expect(button).toBeVisible();
    await button.click();

    const why = page.locator("#panelDetail .pd-why");
    await expect(why).toBeVisible();
    const cal = hockey.calibration;
    const bias = Math.round(cal.bias * 100);
    await expect(why).toContainText(`fitted on ${cal.sample} Liiga games with reported attendance`);
    await expect(why).toContainText(`Backtest: ${cal.sample} completed Liiga games with reported spectators`);
    await expect(why).toContainText(`leave-one-out median error ${Math.round(cal.median_ape * 100)}%`);
    await expect(why).toContainText(`bias ${bias >= 0 ? "+" : ""}${bias}%`);
    await expect(why).toContainText(`${Math.round(cal.within_20pct * 100)}% within ±20%`);
  });

  test("tapping a painted map dot opens its event", async ({ page }) => {
    await page.waitForTimeout(400);
    const hit = await page.evaluate(async () => {
      const venuesDoc = await fetch("./geo/venues.json").then((r) => r.json());
      const venues = new Map((venuesDoc.venues || []).map((v) => [v.id, v]));
      const canvas = document.querySelector("#mapCanvas");
      const rect = canvas.getBoundingClientRect();
      const TILE = 256;
      const zoom = 13.2;
      const z = Math.round(zoom);
      const scale = Math.pow(2, zoom - z);
      const worldX = (lon) => (lon + 180) / 360 * TILE * Math.pow(2, z);
      const worldY = (lat) => {
        const s = Math.sin(Math.max(-85, Math.min(85, lat)) * Math.PI / 180);
        return (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * TILE * Math.pow(2, z);
      };
      // The map starts at this centre and zoom in map.js's init().
      const ox = worldX(23.7610) * scale - rect.width / 2;
      const oy = worldY(61.4978) * scale - rect.height / 2;
      for (const event of window.KMap.dayEvents()) {
        const venue = venues.get(event.venueId);
        if (!venue || !Number.isFinite(venue.lat) || !Number.isFinite(venue.lon)) continue;
        const x = worldX(venue.lon) * scale - ox;
        const y = worldY(venue.lat) * scale - oy;
        if (x < 8 || y < 8 || x > rect.width - 8 || y > rect.height - 8) continue;
        // Ignore points under the estimate card or legend; only a dot whose pixel is the
        // canvas is a real tap target.
        if (document.elementFromPoint(rect.left + x, rect.top + y) !== canvas) continue;
        return { x, y, title: event.title };
      }
      return null;
    });
    expect(hit, "the chosen day should have a visible, tappable dot").not.toBeNull();

    const box = await page.locator("#mapCanvas").boundingBox();
    await page.mouse.click(box.x + hit.x, box.y + hit.y);

    await expect(page.locator("#eventTip")).toBeVisible();
    const shown = (await page.locator("#eventTip b").textContent()) || "";
    const title = shown.split(" · ").slice(1).join(" · ");
    expect(title).not.toBe("");
    expect((await page.locator("#panelDetail .pd-title").textContent()) || "").toBe(title);
  });
});

// Wider than the phone layout, narrower than the desktop grid, so the panel has
// no fixed height here. This is the width the 0.16.7 fixed slot never covered,
// and hovering a row slid every row 84px under the pointer.
test.describe("a pointer window narrower than the desktop grid", () => {
  test.use({ viewport: { width: 800, height: 900 } });

  test("hovering a row at 800x900 keeps the list under the pointer", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.locator("#dayStrip .day").first()).toBeVisible();
    await page.waitForFunction(() => window.KMap && window.KMap.dayEvents().length > 0);

    const rows = page.locator("#panelList .panelRow[data-id]");
    await expect(rows.first()).toBeVisible();
    expect(await rows.count()).toBeGreaterThan(1);

    // the panel sits under the map at this width, so bring the row into view
    // before measuring; scrolling after the measurement would fake a move
    const target = rows.nth(1);
    await target.scrollIntoViewIfNeeded();
    const id = await target.getAttribute("data-id");
    const before = await rowTops(page);

    const box = await target.boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);

    await expect(page.locator("#panelList .panelRow.sel")).toHaveAttribute("data-id", id);
    expect(await rowTops(page)).toEqual(before);

    // and the card that appeared is inside the panel, below the list
    const geometry = await page.evaluate(() => {
      const card = document.getElementById("panelDetail").getBoundingClientRect();
      const panel = document.getElementById("eventPanel").getBoundingClientRect();
      const list = document.getElementById("panelList").getBoundingClientRect();
      return { cardBelowList: card.top >= list.bottom - 1, cardInsidePanel: card.bottom <= panel.bottom + 1 };
    });
    expect(geometry.cardBelowList).toBe(true);
    expect(geometry.cardInsidePanel).toBe(true);
  });
});

// The heat is rasterised in a worker and the main thread draws none while it waits for
// the reply, so a raster per slider tick queued a minute of superseded work behind the
// newest view and the map stayed without heat after a drag.
const heatPixels = (page) => page.evaluate(() => {
  const canvas = document.getElementById("mapCanvas");
  const data = canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height).data;
  let hot = 0;
  for (let i = 0; i < data.length; i += 4 * 9) {
    const r = data[i], g = data[i + 1], b = data[i + 2];
    if (r > 140 && r - g > 35 && g - b > 0 && b < 120) hot += 1;
  }
  return hot;
});

test.describe("the heat layer", () => {
  test("dragging the hour slider brings the heat back at once", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.locator("#dayStrip .day").first()).toBeVisible();
    await page.waitForFunction(() => window.KMap && window.KMap.dayEvents().length > 0);
    // the page opens on today's minute now, so scan the day for its own peak
    // instead of assuming the opening view already sits on it
    const peak = await page.evaluate(() => {
      let best = 19 * 60, top = -1;
      for (let m = 360; m <= 1800; m += 15) {
        const people = window.KMap.dayPeople(m);
        if (people > top) { top = people; best = m; }
      }
      return best;
    });
    await page.evaluate((m) => window.KMap.setTime(m), peak);
    await expect.poll(() => heatPixels(page), { timeout: 15000 }).toBeGreaterThan(300);

    // a quiet hour first, so "heat is back" cannot pass on the previous frame
    await page.evaluate(() => window.KMap.setTime(6 * 60));
    await expect.poll(() => heatPixels(page), { timeout: 10000 }).toBeLessThan(100);

    for (let minute = 12 * 60; minute <= 22 * 60; minute += 15) {
      await page.evaluate((m) => window.KMap.setTime(m), minute);
      await page.waitForTimeout(25);
    }

    // the raster for the restored hour must not sit behind ~40 superseded ones
    const started = Date.now();
    await page.evaluate((m) => window.KMap.setTime(m), peak);
    await expect.poll(() => heatPixels(page), { timeout: 15000, intervals: [100] }).toBeGreaterThan(300);
    expect(Date.now() - started).toBeLessThan(3000);
  });

  test("a heat worker that never answers still shows the heat", async ({ page }) => {
    await page.route("**/heat-worker.js", (route) => route.fulfill({
      contentType: "application/javascript",
      body: "self.onmessage = function () {};",
    }));
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => window.KMap && window.KMap.dayEvents().length > 0);
    // the day's peak, because the opening minute can be a quiet afternoon
    await page.evaluate(() => {
      let best = 19 * 60, top = -1;
      for (let m = 360; m <= 1800; m += 15) {
        const people = window.KMap.dayPeople(m);
        if (people > top) { top = people; best = m; }
      }
      window.KMap.setTime(best);
    });
    await expect.poll(() => heatPixels(page), { timeout: 20000, intervals: [250] }).toBeGreaterThan(300);
    expect(await page.evaluate(() => window.KMap.renderer())).toBe("main");
  });
});

test.describe("share links", () => {
  test("a link opens its day, hour, zoom and centre, and the address bar follows the view", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.locator("#dayStrip .day").first()).toBeVisible();
    await page.waitForFunction(() => window.KMap && window.KMap.dayEvents().length > 0);

    const days = await page.evaluate(() => [...document.querySelectorAll(".day")].map((b) => b.dataset.day));
    expect(days.length).toBeGreaterThan(2);
    const day = days[2];

    await page.goto(`/#d=${day}&t=1380&z=14.60&c=61.49230,23.77120`, { waitUntil: "domcontentloaded" });
    await page.waitForFunction((d) => window.KMap && window.KMap.currentDay() === d, day);

    const opened = await page.evaluate(() => ({
      ...window.KMap.view(),
      slider: document.getElementById("timeSlider").value,
      label: document.getElementById("timeLabel").textContent,
      chip: (document.querySelector(".day.on") || {}).dataset && document.querySelector(".day.on").dataset.day,
    }));
    expect(opened.minutes).toBe(1380);
    expect(opened.slider).toBe("1380");
    expect(opened.label).toBe("23:00");
    expect(opened.chip).toBe(day);
    expect(opened.zoom).toBeCloseTo(14.6, 2);
    expect(opened.lat).toBeCloseTo(61.4923, 4);
    expect(opened.lon).toBeCloseTo(23.7712, 4);

    // the address bar tracks what is on screen, so any moment is shareable
    await page.evaluate(() => window.KMap.setTime(19 * 60 + 15));
    await expect.poll(() => page.evaluate(() => location.hash)).toContain("t=1155");

    // and a pan is written as the centre moving
    const before = await page.evaluate(() => window.KMap.view());
    const box = await page.locator("#mapCanvas").boundingBox();
    const from = { x: box.x + box.width * 0.5, y: box.y + box.height * 0.6 };
    await page.mouse.move(from.x, from.y);
    await page.mouse.down();
    await page.mouse.move(from.x - 80, from.y - 50, { steps: 6 });
    await page.mouse.up();
    await page.waitForFunction((lat) => Math.abs(window.KMap.view().lat - lat) > 1e-4, before.lat);

    const moved = await page.evaluate(() => window.KMap.view());
    const expected = `d=${day}&t=1155&z=${moved.zoom.toFixed(2)}&c=${moved.lat.toFixed(5)},${moved.lon.toFixed(5)}`;
    await expect.poll(() => page.evaluate(() => location.hash)).toBe(`#${expected}`);

    // reopening that link lands on the same panned view
    await page.goto(`/#${expected}`, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => window.KMap && window.KMap.dayEvents().length > 0);
    const again = await page.evaluate(() => window.KMap.view());
    expect(again.minutes).toBe(1155);
    expect(again.zoom).toBeCloseTo(moved.zoom, 2);
    expect(again.lat).toBeCloseTo(moved.lat, 4);
    expect(again.lon).toBeCloseTo(moved.lon, 4);
  });
});

test.describe("event card actions", () => {
  test("a timed event links walking directions and downloads a calendar file", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.locator("#dayStrip .day").first()).toBeVisible();
    await page.waitForFunction(() => window.KMap && window.KMap.dayEvents().length > 0);

    const ev = await page.evaluate(() => {
      const event = window.KMap.dayEvents().find((e) => e.start != null && e.venueId);
      const venue = window.KMap.venue(event.venueId) || {};
      return { id: event.id, title: event.title, time: event.time, venue: event.venue,
               address: venue.address || "", lat: Number(venue.lat), lon: Number(venue.lon),
               day: window.KMap.currentDay() };
    });
    await activateRow(page, ev.id);

    const dir = page.locator("#panelDetail a.pd-act");
    await expect(dir).toHaveText("Directions");

    // the model's arrival/egress slices surface as one honest timing line
    const arrival = page.locator("#panelDetail .pd-arrival");
    await expect(arrival).toBeVisible();
    await expect(arrival).toContainText(/Quietest arrival ≈ \d{2}:\d{2}/);
    await expect(arrival).toContainText(/most arrive ≈ \d{2}:\d{2}/);
    expect(await dir.getAttribute("target")).toBe("_blank");
    const href = await dir.getAttribute("href");
    expect(href).toContain("travelmode=walking");
    expect(href).toContain(`destination=${ev.lat.toFixed(6)},${ev.lon.toFixed(6)}`);

    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.locator("#panelDetail [data-ics]").click(),
    ]);
    expect(download.suggestedFilename()).toMatch(/^kilinkolin-\d{4}-\d{2}-\d{2}-[a-z0-9-]+\.ics$/);

    const body = (await readFile(await download.path(), "utf8"));
    const plain = body.replace(/\\,/g, ",").replace(/\\;/g, ";");
    expect(body).toContain("BEGIN:VCALENDAR");
    expect(body).toContain("VERSION:2.0");
    expect(body).toContain("BEGIN:VEVENT");
    expect(body).toContain("END:VCALENDAR");
    expect(plain).toContain(`SUMMARY:${ev.title}`);
    expect(plain).toContain(`LOCATION:${ev.venue}`);
    expect(plain).toContain(ev.address);

    // the stamp is UTC; read it back in Helsinki and it must be the card's hour
    const start = body.match(/DTSTART:(\d{8})T(\d{2})(\d{2})(\d{2})Z/);
    const end = body.match(/DTEND:(\d{8})T(\d{2})(\d{2})(\d{2})Z/);
    expect(start, "DTSTART must be a UTC stamp").not.toBeNull();
    expect(end, "DTEND must be a UTC stamp").not.toBeNull();
    expect(start[1]).toBe(ev.day.replace(/-/g, ""));
    const toIso = (m) => `${m[1].slice(0, 4)}-${m[1].slice(4, 6)}-${m[1].slice(6, 8)}T${m[2]}:${m[3]}:00Z`;
    const clock = (iso) => new Intl.DateTimeFormat("en-GB", {
      timeZone: "Europe/Helsinki", hour: "2-digit", minute: "2-digit", hour12: false,
    }).format(new Date(iso));
    expect(clock(toIso(start))).toBe(ev.time);
    expect(new Date(toIso(end)).getTime()).toBeGreaterThan(new Date(toIso(start)).getTime());
  });
});

test.describe("playback", () => {
  test("the play button walks the hour forward and pauses again", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.locator("#dayStrip .day").first()).toBeVisible();
    await page.waitForFunction(() => window.KMap && window.KMap.dayEvents().length > 0);

    const before = await page.evaluate(() => document.getElementById("timeSlider").value);
    await page.locator("#timePlay").click();
    await expect(page.locator("#timePlay")).toHaveText("⏸");
    await page.waitForTimeout(400);
    const during = await page.evaluate(() => document.getElementById("timeSlider").value);
    expect(Number(during)).toBeGreaterThan(Number(before));
    await page.locator("#timePlay").click();
    await expect(page.locator("#timePlay")).toHaveText("▶");
  });
});

test.describe("calibration states", () => {
  test("an insufficient sample says it is too small to fit", async ({ page }) => {
    await openHockeyWithCalibration(page, (cal) => {
      cal.status = "INSUFFICIENT";
      cal.sample = 3;
      cal.fitted_fill = cal.prior_fill;
      delete cal.mape;
      delete cal.median_ape;
      delete cal.bias;
      delete cal.within_20pct;
    });
    const why = page.locator("#panelDetail .pd-why");
    await expect(why).toContainText("only 3 completed Liiga game(s)");
    await expect(why).toContainText("too few to fit");
    await expect(why).not.toContainText("Backtest:");
    await expect(page.locator("#calibrationNote")).toContainText("only 3 completed Liiga game(s)");
  });

  test("an unavailable source says no completed games", async ({ page }) => {
    await openHockeyWithCalibration(page, (cal) => {
      cal.status = "UNAVAILABLE";
      cal.sample = 0;
      cal.fitted_fill = cal.prior_fill;
      delete cal.mape;
      delete cal.median_ape;
      delete cal.bias;
      delete cal.within_20pct;
    });
    const why = page.locator("#panelDetail .pd-why");
    await expect(why).toContainText("No completed Liiga game");
    await expect(why).not.toContainText("Backtest:");
    await expect(page.locator("#calibrationNote")).toContainText("no completed Liiga games");
  });

  test("a non-improving fit keeps the prior", async ({ page }) => {
    await openHockeyWithCalibration(page, (cal) => {
      cal.status = "PRIOR";
      cal.sample = 20;
      cal.fitted_fill = cal.prior_fill;
      delete cal.mape;
      delete cal.median_ape;
      delete cal.bias;
      delete cal.within_20pct;
    });
    const why = page.locator("#panelDetail .pd-why");
    await expect(why).toContainText("did not beat the prior on the backtest");
    await expect(why).not.toContainText("Backtest:");
    await expect(page.locator("#calibrationNote")).toContainText("did not beat the prior on the backtest");
  });
});
