import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { useQuery } from '../hooks/useQuery';
import type { CommandUsage } from '../types/api';
import { ChartCard } from './ChartCard';

export function CommandUsageChart() {
  const { data, loading, error } = useQuery<CommandUsage>('command-usage');
  const chartData = data.slice(0, 15);

  return (
    <ChartCard
      title="カスタムコマンド使用ランキング"
      loading={loading}
      error={error}
      isEmpty={chartData.length === 0}
      emptyMessage="カスタムコマンドの利用はまだありません（/exit などのビルトインは除外しています）。"
      testId="command-usage-card"
    >
      <ResponsiveContainer width="100%" height={400}>
        <BarChart data={chartData} layout="vertical" margin={{ left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} />
          <YAxis
            type="category"
            dataKey="command_name"
            tick={{ fontSize: 12 }}
            width={120}
          />
          <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb' }} />
          <Bar dataKey="usage_count" name="使用回数" fill="#10b981" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
