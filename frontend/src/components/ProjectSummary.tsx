import { useQuery } from '../hooks/useQuery';
import type { ProjectSummary as ProjectSummaryType } from '../types/api';
import { ChartCard } from './ChartCard';

function formatDate(iso: string | null): string {
  if (!iso) return '-';
  const d = new Date(iso);
  return d.toLocaleDateString('ja-JP', { month: 'short', day: 'numeric', timeZone: 'Asia/Tokyo' });
}

export function ProjectSummary() {
  const { data, loading, error } = useQuery<ProjectSummaryType>('project-summary');

  return (
    <ChartCard
      title="プロジェクト別サマリー"
      loading={loading}
      error={error}
      isEmpty={data.length === 0}
    >
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100">
              <th className="text-left py-3 px-2 font-medium text-gray-500">プロジェクト</th>
              <th className="text-right py-3 px-2 font-medium text-gray-500">セッション</th>
              <th className="text-right py-3 px-2 font-medium text-gray-500">メッセージ</th>
              <th className="text-right py-3 px-2 font-medium text-gray-500">ツール使用</th>
              <th className="text-right py-3 px-2 font-medium text-gray-500">最終利用</th>
            </tr>
          </thead>
          <tbody>
            {data.map((p) => (
              <tr key={p.project_name} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                <td className="py-3 px-2 font-mono text-xs text-gray-700">{p.project_name}</td>
                <td className="text-right py-3 px-2 tabular-nums">{p.total_sessions}</td>
                <td className="text-right py-3 px-2 tabular-nums">{p.total_user_messages}</td>
                <td className="text-right py-3 px-2 tabular-nums">{p.total_tool_uses}</td>
                <td className="text-right py-3 px-2 text-gray-500">{formatDate(p.last_used)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ChartCard>
  );
}
