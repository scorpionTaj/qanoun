import { expect, test } from "@playwright/test";

// Runs against the fixture law from scripts/seed_fixture.py.
const LAW = "fixture-family-code-ar";
const TITLE = "مدونة الأسرة (نص تجريبي)";

// The root follows the browser's language; Arabic is the default for any other language.
for (const browserLocale of ["ar-MA", "de-DE"]) {
  test.describe(`browser in ${browserLocale}`, () => {
    test.use({ locale: browserLocale });

    test("home opens in Arabic, right to left", async ({ page }) => {
      const response = await page.goto("/");
      expect(response?.ok()).toBe(true);
      await expect(page).toHaveURL(/\/ar\/?$/);
      await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
      await expect(page.locator("html")).toHaveAttribute("lang", "ar");
    });
  });
}

test("a French browser gets French", async ({ browser }) => {
  const page = await (await browser.newContext({ locale: "fr-FR" })).newPage();
  await page.goto("/");
  await expect(page).toHaveURL(/\/fr\/?$/);
});

test("French and English switch to left to right", async ({ page }) => {
  for (const locale of ["fr", "en"]) {
    await page.goto(`/${locale}`);
    await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  }
});

test("the laws page lists the seeded law and opens its reader", async ({ page }) => {
  await page.goto("/ar/laws");
  const link = page.locator(`a[href*="/laws/${LAW}"]`).first();
  await expect(link).toBeVisible();
  await link.click();
  await expect(page).toHaveURL(new RegExp(`/ar/laws/${LAW}`));
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(TITLE);
});

test("a deep link lands on the article", async ({ page }) => {
  await page.goto(`/ar/laws/${LAW}#article-19`);
  const article = page.locator("#article-19");
  await expect(article).toBeVisible();
  await expect(article).toContainText("ثمان عشرة سنة");
  await expect(article).toBeInViewport();
});

test("an unknown law is a 404, not a crash", async ({ page }) => {
  const response = await page.goto("/ar/laws/no-such-law");
  expect(response?.status()).toBe(404);
});
