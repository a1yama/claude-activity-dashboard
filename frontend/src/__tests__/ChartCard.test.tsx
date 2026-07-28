import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ChartCard } from '../components/ChartCard';

function renderCard(props: Partial<React.ComponentProps<typeof ChartCard>> = {}) {
  return render(
    <ChartCard title="タイトル" {...props}>
      <p>本体</p>
    </ChartCard>,
  );
}

describe('ChartCard', () => {
  it('renders children when there is data', () => {
    renderCard();
    expect(screen.queryByText('本体')).not.toBeNull();
    expect(screen.queryByText('タイトル')).not.toBeNull();
  });

  it('shows the error message instead of the empty state', () => {
    renderCard({ error: 'HTTP 500', isEmpty: true });
    expect(screen.queryByText(/データを取得できませんでした/)).not.toBeNull();
    expect(screen.queryByText(/データがありません/)).toBeNull();
    expect(screen.queryByText('本体')).toBeNull();
  });

  it('shows the empty message when there is no data', () => {
    renderCard({ isEmpty: true, emptyMessage: 'まだありません。' });
    expect(screen.queryByText('まだありません。')).not.toBeNull();
    expect(screen.queryByText('本体')).toBeNull();
  });

  it('keeps the title visible while loading', () => {
    renderCard({ loading: true });
    expect(screen.queryByText('タイトル')).not.toBeNull();
    expect(screen.queryByText('本体')).toBeNull();
  });
});
