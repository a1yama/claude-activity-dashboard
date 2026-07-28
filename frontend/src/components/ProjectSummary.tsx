import { useQuery } from '../hooks/useQuery';
import type { ProjectSummary as ProjectSummaryType } from '../types/api';
import { ChartCard } from './ChartCard';

function formatDate(iso: string | null): string {
  if (!iso) return '-';
  const d = new Date(iso);
  return d.toLocaleDateString('ja-JP', { month: 'short', day: 'numeric', timeZone: 'Asia/Tokyo' });
}

function formatTokens(v: number): string {
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}k`;
  return String(v);
}

// 詰まっているプロジェクトを見つけるための指標なので、多い側だけ色を付ける
function errorStyle(v: number): string {
  if (v >= 10) return 'text-red-600 font-medium';
  if (v >= 5) return 'text-amber-600';
  return 'text-gray-500';
}

export function ProjectSummary() {
  const { data, loading, error } = useQuery<ProjectSummaryType>('project-summary');

  return (
    <ChartCard
      title="プロジェクト別サマリー"
      subtitle="直近30日 / 作業時間は放置（15分以上の間隔）を除いた実時間"
      loading={loading}
      error={error}
      isEmpty={data.length === 0}
      emptyMessage="直近30日の活動はありません。"
    >
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100">
              <th className="text-left py-3 px-2 font-medium text-gray-500">プロジェクト</th>
              <th className="text-right py-3 px-2 font-medium text-gray-500">セッション</th>
              <th className="text-right py-3 px-2 font-medium text-gray-500">作業時間</th>
              <th className="text-right py-3 px-2 font-medium text-gray-500">トークン</th>
              <th className="text-right py-3 px-2 font-medium text-gray-500">エラー/回</th>
              <th className="text-right py-3 px-2 font-medium text-gray-500">最終利用</th>
            </tr>
          </thead>
          <tbody>
            {data.map((p) => (
              <tr key={p.project_name} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                <td className="py-3 px-2 font-mono text-xs text-gray-700 max-w-[280px] truncate">{p.project_name}</td>
                <td className="text-right py-3 px-2 tabular-nums">{p.sessions}</td>
                <td className="text-right py-3 px-2 tabular-nums">{p.active_hours.toFixed(1)}h</td>
                <td className="text-right py-3 px-2 tabular-nums">{formatTokens(p.tokens)}</td>
                <td className={`text-right py-3 px-2 tabular-nums ${errorStyle(p.errors_per_session)}`}>
                  {p.errors_per_session.toFixed(1)}
                </td>
                <td className="text-right py-3 px-2 text-gray-500">{formatDate(p.last_used)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ChartCard>
  );
}
