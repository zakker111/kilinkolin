import { test, expect } from "@playwright/test";

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
  await page.locator(`#panelList .panelRow[data-id="${hockey.id}"]`).click();
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
    const days = page.locator("#dayStrip .day");
    await expect(days.first()).toHaveClass(/on/);
    const firstTitle = await page.locator("#panelTitle").innerText();

    const target = days.nth(1);
    const targetDay = await target.getAttribute("data-day");
    await target.click();

    await expect(target).toHaveClass(/on/);
    await expect(days.first()).not.toHaveClass(/on/);
    await expect(page.locator("#panelTitle")).not.toHaveText(firstTitle);
    await expect(page.locator("#panelTitle")).toContainText("What's on");
    await expect(page.locator("#panelList .panelRow").first()).toBeVisible();
    expect(await page.evaluate(() => window.KMap.currentDay())).toBe(targetDay);
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
    await row.click();

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

  test("published events have no exact duplicate listings", async ({ page }) => {
    const duplicates = await page.evaluate(async () => {
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
    const row = page.locator(`#panelList .panelRow[data-id="${missing.id}"]`);
    await expect(row).toBeVisible();
    await expect(row.locator(".pr-time")).toHaveText("TBA");
    await row.click();
    await expect(page.locator("#panelDetail .pd-meta").first()).toContainText("Start TBA");
    await expect(page.locator("#panelDetail .pd-note").first()).toContainText("spread over 18:00–20:00");
  });

  test("a TBA event's heat is spread across its documented window", async ({ page }) => {
    const spread = await page.evaluate(async () => {
      const flows = await fetch("./geo/flows.json").then((r) => r.json());
      const flow = (flows.events || []).find((item) =>
        item.start_options && item.start_options.length > 1 && item.attendance.mid > 0);
      if (!flow) return null;
      const at = (minute) => window.KMap.eventPeople(flow.id, minute);
      return { mid: flow.attendance.mid, values: [at(18 * 60), at(19 * 60), at(20 * 60)] };
    });
    expect(spread, "the build should publish a TBA flow with demand").not.toBeNull();
    expect(spread.values.every((value) => value > 0)).toBe(true);
    expect(spread.values[1]).toBeLessThan(spread.mid);
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
    await page.locator(`#panelList .panelRow[data-id="${target.id}"]`).click();
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
    await page.locator(`#panelList .panelRow[data-id="${target.id}"]`).click();
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
    const row = page.locator("#panelList .panelRow[data-id]").filter({ hasText: hockey.title }).first();
    await expect(row).toBeVisible();
    await row.click();

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
