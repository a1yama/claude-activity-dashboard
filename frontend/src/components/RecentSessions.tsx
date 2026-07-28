import { Link } from 'react-router-dom';
import { useQuery } from '../hooks/useQuery';
import type { RecentSession } from '../types/api';
import { ChartCard } from './ChartCard';

function parseDate(iso: string): Date {
  // DB の時刻は UTC。オフセットなしの文字列はブラウザがローカル時刻と解釈するため UTC を明示する
  const hasOffset = /Z$|[+-]\d{2}:?\d{2}$/.test(iso);
  return new Date(hasOffset ? iso : iso.replace(' ', 'T') + 'Z');
}

function formatDateTime(iso: string | null): string {
  if (!iso) return '-';
  const d = parseDate(iso);
  return d.toLocaleString('ja-JP', {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    timeZone: 'Asia/Tokyo',
  });
}

// 最初〜最後の実時間は放置で桁違いに膨らむため、放置を除いた作業時間を出す
function activeTime(minutes: number): string {
  if (!minutes) return '-';
  if (minutes < 60) return `${minutes}分`;
  return `${Math.floor(minutes / 60)}時間${minutes % 60}分`;
}

export function RecentSessions() {
  const { data, loading, error } = useQuery<RecentSession>('recent-sessions');

  return (
    <ChartCard
      title="最近のセッション"
      loading={loading}
      error={error}
      isEmpty={data.length === 0}
    >
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100">
              <th className="text-left py-3 px-2 font-medium text-gray-500">プロジェクト / 概要</th>
              <th className="text-right py-3 px-2 font-medium text-gray-500">開始</th>
              <th className="text-right py-3 px-2 font-medium text-gray-500">作業時間</th>
              <th className="text-right py-3 px-2 font-medium text-gray-500">メッセージ</th>
              <th className="text-right py-3 px-2 font-medium text-gray-500">ツール</th>
            </tr>
          </thead>
          <tbody>
            {data.map((s) => (
              <Link
                key={s.session_id}
                to={`/sessions/${s.session_id}`}
                className="contents"
              >
                <tr className="border-b border-gray-50 hover:bg-indigo-50 transition-colors cursor-pointer">
                  <td className="py-3 px-2 max-w-[420px]">
                    <div className="font-mono text-xs text-indigo-700 truncate">{s.project_name}</div>
                    {s.summary && (
                      <div className="text-xs text-gray-500 truncate mt-0.5">{s.summary}</div>
                    )}
                  </td>
                  <td className="text-right py-3 px-2 text-gray-500 whitespace-nowrap">{formatDateTime(s.started)}</td>
                  <td className="text-right py-3 px-2 tabular-nums whitespace-nowrap">{activeTime(s.active_minutes)}</td>
                  <td className="text-right py-3 px-2 tabular-nums">{s.message_count}</td>
                  <td className="text-right py-3 px-2 tabular-nums">{s.tool_use_count}</td>
                </tr>
              </Link>
            ))}
          </tbody>
        </table>
      </div>
    </ChartCard>
  );
}
