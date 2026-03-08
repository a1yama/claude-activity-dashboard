import { test, expect } from "@playwright/test";

const SESSION_1_ID = "e2e-test-session-001";

test.describe("セッション詳細ページ", () => {
  test("プロジェクト名が表示される", async ({ page }) => {
    await page.goto(`/#/sessions/${SESSION_1_ID}`);
    await expect(
      page.getByRole("heading", { name: "ghq/github.com/test/my-project" })
    ).toBeVisible();
  });

  test("メッセージ数・ツール使用数の統計が表示される", async ({ page }) => {
    await page.goto(`/#/sessions/${SESSION_1_ID}`);
    // Wait for session data to load
    await expect(
      page.getByRole("heading", { name: "ghq/github.com/test/my-project" })
    ).toBeVisible();

    // session1: message_count=5, user=2, assistant=3, tool=4
    await expect(page.getByText("メッセージ").first()).toBeVisible();
    await expect(page.getByText("ユーザー")).toBeVisible();
    await expect(page.getByText("アシスタント")).toBeVisible();
    await expect(page.getByText("ツール使用")).toBeVisible();
  });

  test("メッセージ一覧にuser/assistantメッセージが表示される", async ({
    page,
  }) => {
    await page.goto(`/#/sessions/${SESSION_1_ID}`);
    await expect(
      page.getByRole("heading", { name: "ghq/github.com/test/my-project" })
    ).toBeVisible();

    await expect(page.getByText("バグを修正してください")).toBeVisible();
    await expect(page.getByText("ファイルを確認します")).toBeVisible();
    await expect(
      page.getByText("ありがとう、テストも追加してください")
    ).toBeVisible();
  });

  test("ダッシュボードへ戻るリンクが機能する", async ({ page }) => {
    await page.goto(`/#/sessions/${SESSION_1_ID}`);
    await expect(
      page.getByRole("heading", { name: "ghq/github.com/test/my-project" })
    ).toBeVisible();

    const backLink = page.getByText("← ダッシュボード");
    await expect(backLink).toBeVisible();
    await backLink.click();
    await expect(
      page.getByRole("heading", { name: "Claude Activity Dashboard" })
    ).toBeVisible();
  });

  test("存在しないセッションIDでエラーメッセージが表示される", async ({
    page,
  }) => {
    await page.goto("/#/sessions/nonexistent-session-id");
    await expect(page.getByText("セッションが見つかりません")).toBeVisible();
  });
});
