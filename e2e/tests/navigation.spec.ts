import { test, expect } from "@playwright/test";

test.describe("ページ間ナビゲーション", () => {
  test("ダッシュボードからセッション詳細へ遷移できる", async ({ page }) => {
    await page.goto("/");
    // Wait for recent sessions to load
    await expect(page.getByText("最近のセッション")).toBeVisible();

    // Click on a session row in the recent sessions table (use link role to target the table row)
    const sessionLink = page.getByRole("link", {
      name: /ghq\/github\.com\/test\/my-project/,
    });
    await expect(sessionLink).toBeVisible();
    await sessionLink.click();

    // Should navigate to session detail page
    await expect(
      page.getByRole("heading", { name: "ghq/github.com/test/my-project" })
    ).toBeVisible();
    await expect(page.getByText("バグを修正してください")).toBeVisible();
  });

  test("セッション詳細からダッシュボードに戻れる", async ({ page }) => {
    await page.goto("/#/sessions/e2e-test-session-001");
    await expect(
      page.getByRole("heading", { name: "ghq/github.com/test/my-project" })
    ).toBeVisible();

    await page.getByText("← ダッシュボード").click();

    await expect(
      page.getByRole("heading", { name: "Claude Activity Dashboard" })
    ).toBeVisible();
    await expect(page.getByText("最近のセッション")).toBeVisible();
  });
});
