import { useQuery } from '../hooks/useQuery';
import type { ProjectSummary as ProjectSummaryType } from '../types/api';
import { LoadingSpinner } from './LoadingSpinner';

function formatDate(iso: string | null): string {
  if (!iso) return '-';
  const d = new Date(iso);
  return d.toLocaleDateString('ja-JP', { month: 'short', day: 'numeric' });
}

export function ProjectSummary() {
  const { data, loading } = useQuery<ProjectSummaryType>('project-summary');

  if (loading) return <LoadingSpinner />;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">プロジェクト別サマリー</h2>
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
    </div>
  );
}
