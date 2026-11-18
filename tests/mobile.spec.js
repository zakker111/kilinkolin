import { test, expect } from "@playwright/test";

test.use({ viewport: { width: 390, height: 844 }, hasTouch: true });

// The map starts at this centre and zoom in map.js's init().
async function firstVisibleDot(page) {
  return page.evaluate(async () => {
    const venuesDoc = await fetch("./geo/venues.json").then((r) => r.json());
    const venues = new Map((venuesDoc.venues || []).map((v) => [v.id, v]));
    const canvas = document.getElementById("mapCanvas");
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
    const ox = worldX(23.7610) * scale - rect.width / 2;
    const oy = worldY(61.4978) * scale - rect.height / 2;
    for (const event of window.KMap.dayEvents()) {
      const venue = venues.get(event.venueId);
      if (!venue || !Number.isFinite(venue.lat) || !Number.isFinite(venue.lon)) continue;
      const x = worldX(venue.lon) * scale - ox;
      const y = worldY(venue.lat) * scale - oy;
      if (x < 12 || y < 12 || x > rect.width - 12 || y > rect.height - 12) continue;
      // ignore points under the estimate card or legend
      if (document.elementFromPoint(rect.left + x, rect.top + y) !== canvas) continue;
      return { x: rect.left + x, y: rect.top + y };
    }
    return null;
  });
}

test("tapping a map dot on a phone names that event and keeps it", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#dayStrip .day").first()).toBeVisible();
  await page.waitForFunction(() => window.KMap && window.KMap.dayEvents().length > 0);
  await page.waitForTimeout(600);

  const dot = await firstVisibleDot(page);
  expect(dot, "the chosen day should have a dot on the phone map").not.toBeNull();

  await page.touchscreen.tap(dot.x, dot.y);
  // the finger lift fires pointerleave right after the tap, so wait it out
  await page.waitForTimeout(250);

  const tip = page.locator("#eventTip");
  await expect(tip).toBeVisible();
  const title = ((await tip.locator("b").textContent()) || "").split(" · ").slice(1).join(" · ");
  expect(title).not.toBe("");
  await expect(page.locator("#panelDetail .pd-title")).toHaveText(title);
  await expect(page.locator("#panelList .panelRow.sel")).toHaveCount(1);
});

test("tapping an event row shows that event while the list is scrolled", async ({ page }) => {
  // The phone panel is one scroll area with the detail card inside it, so a
  // card for a tapped row used to render above the panel's own viewport and the
  // tap looked like it did nothing. The card is pinned to the panel top.
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#dayStrip .day").first()).toBeVisible();
  await page.waitForFunction(() => window.KMap && window.KMap.dayEvents().length > 0);

  const panel = page.locator("#eventPanel");
  const rows = page.locator("#panelList .panelRow[data-id]");
  await expect(rows.first()).toBeVisible();
  await panel.scrollIntoViewIfNeeded();

  // select one event so the card is showing, then scroll the panel like a thumb
  await rows.first().tap();
  await expect(page.locator("#panelDetail .pd-title")).not.toBeEmpty();
  await panel.evaluate((el) => { el.scrollTop = 300; });

  // tap a row that is visible below the pinned card, by coordinates
  const hit = await page.evaluate(() => {
    const panelRect = document.getElementById("eventPanel").getBoundingClientRect();
    const card = document.getElementById("panelDetail").getBoundingClientRect();
    const bottom = Math.min(panelRect.bottom, window.innerHeight);
    for (const row of document.querySelectorAll("#panelList .panelRow[data-id]")) {
      const rect = row.getBoundingClientRect();
      if (rect.top > card.bottom + 4 && rect.bottom < bottom - 4) {
        return {
          id: row.dataset.id,
          title: row.querySelector(".pr-title").textContent.trim(),
          x: rect.left + rect.width / 2,
          y: rect.top + rect.height / 2,
        };
      }
    }
    return null;
  });
  expect(hit, "a row should be reachable below the card").not.toBeNull();
  await page.touchscreen.tap(hit.x, hit.y);

  await expect(page.locator("#panelList .panelRow.sel")).toHaveAttribute("data-id", hit.id);
  await expect(page.locator("#panelDetail .pd-title")).toHaveText(hit.title);

  const box = await page.evaluate(() => {
    const card = document.getElementById("panelDetail").getBoundingClientRect();
    const panelRect = document.getElementById("eventPanel").getBoundingClientRect();
    return { cardTop: card.top, cardBottom: card.bottom, panelTop: panelRect.top, panelBottom: panelRect.bottom };
  });
  expect(box.cardTop).toBeGreaterThanOrEqual(box.panelTop - 1);
  expect(box.cardBottom).toBeLessThanOrEqual(box.panelBottom + 1);
});

test("the mobile Why sheet keeps the panel rows, scrolls, and dismisses", async ({ page }) => {
  // Make one real Why source long enough to overflow the sheet at this viewport.
  await page.route("**/geo/days/*.json", async (route) => {
    const response = await route.fetch();
    const doc = await response.json();
    for (const event of doc.events || []) {
      if (event.basis) event.basis.capacity_source = "Official source note ".repeat(120);
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(doc) });
  });

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await expect(page.locator("#dayStrip .day").first()).toBeVisible();
  await page.waitForFunction(() => window.KMap && window.KMap.dayEvents().length > 0);
  await page.waitForLoadState("networkidle");

  const rows = page.locator("#panelList .panelRow[data-id]");
  const rowCount = await rows.count();
  await rows.first().click();

  const whyButton = page.locator("#panelDetail .pd-why-btn");
  await expect(whyButton).toHaveAttribute("aria-haspopup", "dialog");
  await expect(whyButton).toHaveAttribute("aria-controls", "whySheet");
  await expect(page.locator("#panelDetail .pd-why")).toHaveCount(0);

  await whyButton.click();
  const sheet = page.locator("#whySheet");
  const body = page.locator("#whySheetBody");
  await expect(sheet).toBeVisible();
  await expect(page.locator("#whySheetEvent")).not.toBeEmpty();
  await expect(rows).toHaveCount(rowCount);
  await expect(body).toHaveCSS("overflow-y", "auto");

  const metrics = await body.evaluate((el) => ({
    clientHeight: el.clientHeight,
    scrollHeight: el.scrollHeight,
  }));
  expect(metrics.scrollHeight).toBeGreaterThan(metrics.clientHeight);
  await body.evaluate((el) => { el.scrollTop = 100; });
  expect(await body.evaluate((el) => el.scrollTop)).toBeGreaterThan(0);

  await page.locator("#whySheetClose").click();
  await expect(sheet).toBeHidden();
  await expect(whyButton).toHaveAttribute("aria-expanded", "false");
  await expect(whyButton).toBeFocused();

  await page.waitForTimeout(300);
  await expect(async () => {
    await whyButton.click();
    await expect(sheet).toBeVisible();
  }).toPass({ timeout: 10000 });
  await page.mouse.click(5, 5);
  await expect(sheet).toBeHidden();
  await expect(whyButton).toHaveAttribute("aria-expanded", "false");
  await expect(whyButton).toBeFocused({ timeout: 10000 });

  await page.waitForTimeout(300);
  await expect(async () => {
    await whyButton.click();
    await expect(sheet).toBeVisible();
  }).toPass({ timeout: 10000 });
  await page.keyboard.press("Escape");
  await expect(sheet).toBeHidden();
  await expect(whyButton).toHaveAttribute("aria-expanded", "false");
  await expect(whyButton).toBeFocused({ timeout: 10000 });
  await expect(sheet).toBeHidden();
  await expect(whyButton).toHaveAttribute("aria-expanded", "false");
  await expect(whyButton).toBeFocused();
});
