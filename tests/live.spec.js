import { test, expect } from "@playwright/test";

/**
 * Runs against the deployed Pages origin, not the local static server.  This
 * catches base-path, Pages-artifact and live asset failures that the local
 * smoke suite cannot see.
 */
test.describe("live Pages smoke", () => {
  test("serves the app, data and time controls from the deployed origin", async ({ page }) => {
    const pageErrors = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    const response = await page.goto("./", { waitUntil: "domcontentloaded" });
    expect(response?.status()).toBe(200);
    await expect(page).toHaveTitle(/Kilinkolin/);
    await expect(page.locator("#mapCanvas")).toBeVisible();
    await expect(page.locator("#dayStrip .day").first()).toBeVisible();
    await expect(page.locator("#panelList")).toBeVisible();

    await page.waitForFunction(() => window.KMap && window.KMap.dayEvents().length > 0);

    const data = await page.evaluate(async () => {
      const result = await fetch("./data.json");
      return { ok: result.ok, body: await result.json() };
    });
    expect(data.ok).toBe(true);
    expect(data.body.events.length).toBeGreaterThan(0);
    expect(data.body.source_status).toBeTruthy();

    const slider = page.locator("#timeSlider");
    await slider.evaluate((element) => {
      element.value = element.max;
      element.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await expect(page.locator("#timeLabel")).toHaveText("06:00 +1");
    await expect(page.locator("#estimate .e-title")).toContainText("06:00");

    expect(pageErrors).toEqual([]);
  });
});
