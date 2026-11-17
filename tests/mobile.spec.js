import { test, expect } from "@playwright/test";

test.use({ viewport: { width: 390, height: 844 }, hasTouch: true });

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
  await expect(whyButton).toBeFocused();

  await whyButton.click();
  await expect(sheet).toBeVisible();
  await page.mouse.click(5, 5);
  await expect(sheet).toBeHidden();
  await expect(whyButton).toBeFocused();

  await whyButton.click();
  await expect(sheet).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(sheet).toBeHidden();
  await expect(whyButton).toBeFocused();
});
