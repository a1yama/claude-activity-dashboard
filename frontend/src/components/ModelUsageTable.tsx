import { useQuery } from '../hooks/useQuery';
import type { ModelUsage } from '../types/api';
import { LoadingSpinner } from './LoadingSpinner';

function formatTokens(v: number): string {
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}k`;
  return String(v);
}

export function ModelUsageTable() {
  const { data, loading } = useQuery<ModelUsage>('model-usage');

  if (loading) return <LoadingSpinner />;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-1">モデル別利用状況</h2>
      <p className="text-xs text-gray-400 mb-4">サブエージェント分を含む</p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100">
              <th className="text-left py-3 px-2 font-medium text-gray-500">モデル</th>
              <th className="text-right py-3 px-2 font-medium text-gray-500">メッセージ</th>
              <th className="text-right py-3 px-2 font-medium text-gray-500">入力(キャッシュ込)</th>
              <th className="text-right py-3 px-2 font-medium text-gray-500">出力</th>
            </tr>
          </thead>
          <tbody>
            {data.map((m) => (
              <tr key={m.model} className="border-b border-gray-50">
                <td className="py-3 px-2 font-mono text-xs text-indigo-700">{m.model}</td>
                <td className="text-right py-3 px-2 tabular-nums">{m.messages.toLocaleString()}</td>
                <td className="text-right py-3 px-2 tabular-nums">{formatTokens(m.total_input_tokens)}</td>
                <td className="text-right py-3 px-2 tabular-nums">{formatTokens(m.output_tokens)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
