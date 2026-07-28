import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { CommandUsageChart } from '../components/CommandUsageChart';

function mockRows(rows: unknown[]) {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: true,
    json: async () => ({ rows }),
  } as Response);
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('CommandUsageChart', () => {
  it('shows an empty state when no custom command was used', async () => {
    mockRows([]);

    render(<CommandUsageChart />);

    await waitFor(() =>
      expect(screen.queryByText(/カスタムコマンドの利用はまだありません/)).not.toBeNull(),
    );
  });

  it('renders the ranking when custom commands exist', async () => {
    mockRows([
      { command_name: '/analyze-usage', usage_count: 3, last_used: '2026-03-02' },
    ]);

    const { container } = render(<CommandUsageChart />);

    // jsdom は幅0なのでチャート本体のSVGは描画されない。分岐内にしか無いコンテナで判定する
    await waitFor(() =>
      expect(container.querySelector('.recharts-responsive-container')).not.toBeNull(),
    );
    expect(screen.queryByText(/カスタムコマンドの利用はまだありません/)).toBeNull();
  });

  it('distinguishes a fetch failure from zero usage', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 500,
    } as Response);

    render(<CommandUsageChart />);

    await waitFor(() => expect(screen.queryByText(/データを取得できませんでした/)).not.toBeNull());
    expect(screen.queryByText(/カスタムコマンドの利用はまだありません/)).toBeNull();
  });
});
