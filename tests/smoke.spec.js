import { test, expect } from "@playwright/test";

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
    const shown = await page.locator("#eventTip b").innerText();
    const title = shown.split(" · ").slice(1).join(" · ");
    expect(title).not.toBe("");
    await expect(page.locator("#panelDetail .pd-title")).toHaveText(title);
  });
});
