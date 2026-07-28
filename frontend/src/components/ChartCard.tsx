import type { ReactNode } from 'react';
import { LoadingSpinner } from './LoadingSpinner';

type ChartCardProps = {
  title: string;
  subtitle?: ReactNode;
  headerRight?: ReactNode;
  loading?: boolean;
  error?: string | null;
  isEmpty?: boolean;
  emptyMessage?: string;
  testId?: string;
  children: ReactNode;
};

/**
 * ダッシュボードのカード共通枠。
 * 取得失敗を「データ0件」と誤読させないため、error を空状態より先に出し分ける。
 */
export function ChartCard({
  title,
  subtitle,
  headerRight,
  loading = false,
  error = null,
  isEmpty = false,
  emptyMessage = 'データがありません。',
  testId,
  children,
}: ChartCardProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6" data-testid={testId}>
      <div className="flex items-baseline justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
          {subtitle && <p className="text-xs text-gray-400 mt-1">{subtitle}</p>}
        </div>
        {headerRight}
      </div>

      {loading ? (
        <LoadingSpinner />
      ) : error ? (
        <p className="text-sm text-red-600">データを取得できませんでした（{error}）。</p>
      ) : isEmpty ? (
        <p className="text-sm text-gray-500">{emptyMessage}</p>
      ) : (
        children
      )}
    </div>
  );
}
