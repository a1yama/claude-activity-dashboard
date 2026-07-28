import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { useQuery } from '../hooks/useQuery';
import type { DailyActivity } from '../types/api';
import { ChartCard } from './ChartCard';

export function DailyActivityChart() {
  const { data, loading, error } = useQuery<DailyActivity>('daily-activity');
  const chartData = [...data].reverse().slice(-30);

  return (
    <ChartCard
      title="日別アクティビティ（直近30日）"
      loading={loading}
      error={error}
      isEmpty={chartData.length === 0}
    >
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11 }}
            tickFormatter={(v) => v.slice(5)}
          />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip
            contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb' }}
          />
          <Legend />
          <Bar dataKey="user_messages" name="ユーザー" fill="#6366f1" radius={[4, 4, 0, 0]} />
          <Bar dataKey="assistant_messages" name="アシスタント" fill="#a5b4fc" radius={[4, 4, 0, 0]} />
          <Bar dataKey="tool_uses" name="ツール使用" fill="#c7d2fe" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
