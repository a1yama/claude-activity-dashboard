import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { useQuery } from '../hooks/useQuery';
import type { HourlyDistribution } from '../types/api';
import { ChartCard } from './ChartCard';

export function HourlyDistributionChart() {
  const { data, loading, error } = useQuery<HourlyDistribution>('hourly-distribution');

  return (
    <ChartCard
      title="時間帯別メッセージ分布"
      loading={loading}
      error={error}
      isEmpty={data.length === 0}
    >
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis
            dataKey="hour"
            tick={{ fontSize: 11 }}
            tickFormatter={(v) => `${v}時`}
          />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip
            labelFormatter={(v) => `${v}時`}
            contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb' }}
          />
          <Area
            type="monotone"
            dataKey="message_count"
            name="全メッセージ"
            stroke="#6366f1"
            fill="#eef2ff"
            strokeWidth={2}
          />
          <Area
            type="monotone"
            dataKey="user_messages"
            name="ユーザー"
            stroke="#8b5cf6"
            fill="#f5f3ff"
            strokeWidth={2}
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
