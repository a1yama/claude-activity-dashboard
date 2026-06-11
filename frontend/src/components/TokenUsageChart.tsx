import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { useQuery } from '../hooks/useQuery';
import type { TokenUsageDaily } from '../types/api';
import { LoadingSpinner } from './LoadingSpinner';

function formatTokens(v: number): string {
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}k`;
  return String(v);
}

export function TokenUsageChart() {
  const { data, loading } = useQuery<TokenUsageDaily>('token-usage-daily');

  if (loading) return <LoadingSpinner />;

  const chartData = [...data].reverse().slice(-30);

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-1">トークン使用量（直近30日）</h2>
      <p className="text-xs text-gray-400 mb-4">サブエージェント分を含む。キャッシュ読込は右軸</p>
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v) => v.slice(5)} />
          <YAxis yAxisId="left" tick={{ fontSize: 11 }} tickFormatter={formatTokens} />
          <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} tickFormatter={formatTokens} />
          <Tooltip
            contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb' }}
            formatter={(value) => (typeof value === 'number' ? value.toLocaleString() : value)}
          />
          <Legend />
          <Bar yAxisId="left" dataKey="output_tokens" name="出力" stackId="t" fill="#6366f1" />
          <Bar yAxisId="left" dataKey="input_tokens" name="入力" stackId="t" fill="#a5b4fc" />
          <Bar yAxisId="left" dataKey="cache_creation_tokens" name="キャッシュ書込" stackId="t" fill="#c7d2fe" radius={[4, 4, 0, 0]} />
          <Line yAxisId="right" type="monotone" dataKey="cache_read_tokens" name="キャッシュ読込" stroke="#f59e0b" strokeWidth={2} dot={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
