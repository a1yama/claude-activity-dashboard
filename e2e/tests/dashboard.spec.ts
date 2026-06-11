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

  test("トークン使用量チャートが表示される", async ({ page }) => {
    await expect(page.getByText("トークン使用量（直近30日）")).toBeVisible();
  });

  test("モデル別利用状況にモデル名とトークン数が表示される", async ({ page }) => {
    await expect(page.getByText("モデル別利用状況")).toBeVisible();
    await expect(page.getByText("claude-fable-5")).toBeVisible();
  });

  test("スラッシュコマンド使用ランキングが表示される", async ({ page }) => {
    await expect(
      page.getByText("スラッシュコマンド使用ランキング")
    ).toBeVisible();
  });

  test("セッション開始時刻がJSTで表示される", async ({ page }) => {
    // fixture: 2026-03-01T01:00:00+00:00 = JST 3月1日 10:00
    await expect(page.getByText("3月1日 10:00")).toBeVisible();
    // fixture: 2026-03-02T05:00:00+00:00 = JST 3月2日 14:00
    await expect(page.getByText("3月2日 14:00")).toBeVisible();
  });
});
