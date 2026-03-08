import { test, expect } from "@playwright/test";

test.describe("ダッシュボードページ", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForSelector("h1");
  });

  test("ページタイトルが表示される", async ({ page }) => {
    await expect(
      page.getByRole("heading", { name: "Claude Activity Dashboard" })
    ).toBeVisible();
  });

  test("統計カードが4つ表示される", async ({ page }) => {
    const statTitles = [
      "総セッション数",
      "総メッセージ数",
      "総ツール使用数",
      "今日のメッセージ",
    ];
    for (const title of statTitles) {
      await expect(page.getByText(title)).toBeVisible();
    }
  });

  test("統計カードに正しい値が表示される", async ({ page }) => {
    // 2 sessions total (session1: 2 user msgs, session2: 1 user msg → total 3)
    // tool_use_count: session1=4, session2=2 → total 6
    await expect(page.getByText("2").first()).toBeVisible(); // 総セッション数
    await expect(page.getByText("3").first()).toBeVisible(); // 総メッセージ数 (user messages)
    await expect(page.getByText("6").first()).toBeVisible(); // 総ツール使用数
  });

  test("最近のセッションテーブルにセッションが表示される", async ({
    page,
  }) => {
    // Wait for RecentSessions to load
    await expect(page.getByText("最近のセッション")).toBeVisible();
    // Project names appear in both ProjectSummary and RecentSessions, use .first()
    await expect(
      page.getByText("ghq/github.com/test/my-project").first()
    ).toBeVisible();
    await expect(
      page.getByText("ghq/github.com/test/other-project").first()
    ).toBeVisible();
  });

  test("チャートセクションが表示される", async ({ page }) => {
    await expect(
      page.getByText("日別アクティビティ（直近30日）")
    ).toBeVisible();
    await expect(page.getByText("時間帯別メッセージ分布")).toBeVisible();
  });

  test("データ更新ボタンをクリックすると更新完了が表示される", async ({
    page,
  }) => {
    const button = page.getByRole("button", { name: "データ更新" });
    await expect(button).toBeVisible();
    await button.click();
    await expect(page.getByText("更新中...")).toBeVisible();
    await expect(page.getByText("更新完了")).toBeVisible({ timeout: 15_000 });
  });
});
