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

// The web build carries no API URL: the browser gets QANOUN_PUBLIC_API_URL at runtime.
test("the browser calls the API at the URL configured at runtime", async ({ page }) => {
  const expected = process.env.E2E_PUBLIC_API_URL;
  test.skip(!expected, "set E2E_PUBLIC_API_URL to the web server's QANOUN_PUBLIC_API_URL");
  const providers = page.waitForResponse((r) => r.url() === `${expected}/api/llm/providers`);
  await page.goto("/ar/settings");
  expect(await page.evaluate(() => window.__QANOUN_API_URL__)).toBe(expected);
  expect((await providers).ok()).toBe(true);
});

test("cross-references link both ways within the law", async ({ page }) => {
  await page.goto(`/ar/laws/${LAW}`);
  const citing = page.locator("#article-19");
  await expect(citing.getByText("يحيل على")).toBeVisible();
  await citing.getByRole("link", { name: "المادة 4" }).click();
  await expect(page).toHaveURL(/#article-4$/);
  const cited = page.locator("#article-4");
  await expect(cited.getByText("محال عليها في")).toBeVisible();
  await expect(cited.getByRole("link", { name: "المادة 19" })).toHaveAttribute("href", "#article-19");
});

test("an amended article shows its history, and the reader filters by year", async ({ page }) => {
  await page.goto(`/ar/laws/${LAW}`);
  const history = page.locator("#article-4").getByTestId("amendment-history");
  await expect(history).toContainText("2021");
  await expect(history).toContainText("102.21");
  await expect(history).toContainText("تغيير، تتميم");
  await page.getByRole("combobox").selectOption("2021");
  await expect(page.locator("article.article-card")).toHaveCount(1);
  await expect(page.locator("#article-4")).toBeVisible();
});

test("a law lists its implementing decrees, and a decree links back", async ({ page }) => {
  await page.goto(`/ar/laws/${LAW}`);
  const decrees = page.getByRole("region", { name: /المراسيم التطبيقية/ });
  await decrees.getByRole("link", { name: "مرسوم تطبيقي (نص تجريبي)" }).click();
  await expect(page).toHaveURL(/\/ar\/laws\/fixture-decree-ar/);
  await page.getByRole("link", { name: TITLE }).click();
  await expect(page).toHaveURL(new RegExp(`/ar/laws/${LAW}$`));
});
