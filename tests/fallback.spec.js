import { test, expect } from "@playwright/test";

/* One broken per-day bundle must never blank the map: the app falls back to the
   full flows.json + routes.json pair, which carries every day, and it must keep
   showing one day at a time from that full bundle. */
const BROKEN_BUNDLES = [
  {
    name: "a missing day bundle",
    serve: (route) => route.fulfill({ status: 404, contentType: "text/plain", body: "not found" }),
  },
  {
    name: "a malformed day bundle",
    serve: (route) => route.fulfill({
      status: 200, contentType: "application/json", body: '{"routes": {}, "events": [',
    }),
  },
  {
    name: "a day bundle without events",
    serve: (route) => route.fulfill({
      status: 200, contentType: "application/json", body: '{"routes": {}}',
    }),
  },
];

/* event ids published for each day, straight from the feed the app reads */
function idsByDay(page) {
  return page.evaluate(async () => {
    const data = await fetch("./data.json").then((r) => r.json());
    const byDay = {};
    for (const row of data.events || []) {
      if (!row[7]) continue;
      (byDay[row[0]] = byDay[row[0]] || []).push(row[7]);
    }
    return byDay;
  });
}

async function panelIds(page) {
  return page.locator("#panelList .panelRow[data-id]").evaluateAll((rows) => rows.map((row) => row.dataset.id));
}

for (const bundle of BROKEN_BUNDLES) {
  test(`the full flows fallback covers ${bundle.name} without mixing days`, async ({ page }) => {
    const dayRequests = [];
    const fullBundle = [];
    const notes = [];
    page.on("console", (msg) => notes.push(msg.text()));
    page.on("request", (req) => {
      if (/\/geo\/days\/[^/]+\.json$/.test(new URL(req.url()).pathname)) dayRequests.push(req.url());
    });
    page.on("response", (res) => {
      const path = new URL(res.url()).pathname;
      if (path === "/geo/flows.json" || path === "/geo/routes.json") fullBundle.push({ path, status: res.status() });
    });

    await page.route("**/geo/days/*.json", bundle.serve);

    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.locator("#dayStrip .day").first()).toBeVisible();
    await page.waitForFunction(() => window.KMap && window.KMap.dayEvents().length > 0);

    // The day bundle was asked for once, failed, and both halves of the full
    // bundle answered instead.
    expect(dayRequests).toHaveLength(1);
    expect(fullBundle.map((r) => r.path).sort()).toEqual(["/geo/flows.json", "/geo/routes.json"]);
    expect(fullBundle.every((r) => r.status === 200)).toBe(true);
    expect(notes.join("\n")).toContain("per-day flow data unavailable, using full bundle");

    const byDay = await idsByDay(page);
    const days = Object.keys(byDay).sort();
    const firstDay = await page.evaluate(() => window.KMap.currentDay());
    expect(firstDay).toBe(days[0]);
    const firstIds = byDay[firstDay];
    expect(firstIds.length).toBeGreaterThan(0);

    // The first day is shown whole, and only the first day.
    expect([...(await panelIds(page))].sort()).toEqual([...firstIds].sort());
    const firstLabel = await page.evaluate((day) => window.KMap.dayLabel(day), firstDay);
    await expect(page.locator("#panelTitle")).toContainText(firstLabel);
    await expect(page.locator("#estimate .e-num")).toContainText("≈");
    const feeding = await page.locator("#estimate .e-line").textContent();
    const fed = Number((feeding.match(/(\d+) event/) || [])[1]);
    expect(fed).toBeGreaterThan(0);
    expect(fed).toBeLessThanOrEqual(firstIds.length);

    // The full bundle really is flows plus the route geometry those legs need.
    const wiring = await page.evaluate(async (id) => {
      const [flows, routes] = await Promise.all([
        fetch("./geo/flows.json").then((r) => r.json()),
        fetch("./geo/routes.json").then((r) => r.json()),
      ]);
      const flow = (flows.events || []).find((item) => item.id === id);
      const legs = (flow && flow.legs) || [];
      const routeMap = routes.routes || {};
      return {
        legs: legs.length,
        unresolved: legs.filter((leg) => !routeMap[leg.key]).length,
        routeCount: Object.keys(routeMap).length,
      };
    }, firstIds[0]);
    expect(wiring.legs).toBeGreaterThan(0);
    expect(wiring.unresolved).toBe(0);
    expect(wiring.routeCount).toBeGreaterThan(0);

    // A later day comes from the same full bundle: no retry of the broken day
    // file, and the panel holds that day's events, not a mix of both.
    const second = days.find((day) => day !== firstDay);
    const bundleFetches = fullBundle.length;
    await page.locator(`.day[data-day="${second}"]`).click();
    await page.waitForFunction((day) => window.KMap.currentDay() === day, second);
    expect([...(await panelIds(page))].sort()).toEqual([...byDay[second]].sort());
    expect((await panelIds(page)).some((id) => firstIds.includes(id))).toBe(false);
    const secondLabel = await page.evaluate((day) => window.KMap.dayLabel(day), second);
    await expect(page.locator("#panelTitle")).toContainText(secondLabel);
    expect(dayRequests).toHaveLength(1);
    expect(fullBundle).toHaveLength(bundleFetches);
  });
}
