import { useState } from 'react';
import { StatCard } from '../components/StatCard';
import { DailyActivityChart } from '../components/DailyActivityChart';
import { HourlyDistributionChart } from '../components/HourlyDistributionChart';
import { ToolUsageChart } from '../components/ToolUsageChart';
import { ProjectSummary } from '../components/ProjectSummary';
import { RecentSessions } from '../components/RecentSessions';
import { useQuery } from '../hooks/useQuery';
import type { DailyActivity, ProjectSummary as ProjectSummaryType } from '../types/api';

function RefreshButton() {
  const [refreshing, setRefreshing] = useState(false);
  const [message, setMessage] = useState('');

  const handleRefresh = async () => {
    setRefreshing(true);
    setMessage('');
    try {
      const res = await fetch('/api/refresh', { method: 'POST' });
      const text = await res.text();
      let json: { ok?: boolean; message?: string };
      try {
        json = JSON.parse(text);
      } catch {
        // Fallback: non-JSON response (e.g. HTML from old Datasette)
        if (res.ok && !text.includes('エラー')) {
          setMessage('更新完了');
          setTimeout(() => window.location.reload(), 1000);
          return;
        }
        setMessage(`更新エラー (レスポンス: ${text.slice(0, 100)})`);
        return;
      }
      if (json.ok) {
        setMessage('更新完了');
        setTimeout(() => window.location.reload(), 1000);
      } else {
        setMessage(`更新エラー: ${json.message}`);
      }
    } catch (e) {
      setMessage(`通信エラー: ${e instanceof Error ? e.message : e}`);
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div className="flex items-center gap-3">
      {message && <span className="text-sm text-gray-500">{message}</span>}
      <button
        onClick={handleRefresh}
        disabled={refreshing}
        className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
      >
        {refreshing ? '更新中...' : 'データ更新'}
      </button>
    </div>
  );
}

export function Dashboard() {
  const { data: daily } = useQuery<DailyActivity>('daily-activity');
  const { data: projects } = useQuery<ProjectSummaryType>('project-summary');

  const totalSessions = projects.reduce((sum, p) => sum + p.total_sessions, 0);
  const totalMessages = projects.reduce((sum, p) => sum + p.total_user_messages, 0);
  const totalTools = projects.reduce((sum, p) => sum + p.total_tool_uses, 0);
  const todayData = daily.length > 0 ? daily[0] : null;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Claude Activity Dashboard</h1>
            <p className="text-sm text-gray-500">Claude Code の活動ログビューア</p>
          </div>
          <RefreshButton />
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="総セッション数"
            value={totalSessions.toLocaleString()}
            icon={<svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>}
          />
          <StatCard
            title="総メッセージ数"
            value={totalMessages.toLocaleString()}
            icon={<svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>}
          />
          <StatCard
            title="総ツール使用数"
            value={totalTools.toLocaleString()}
            icon={<svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>}
          />
          <StatCard
            title="今日のメッセージ"
            value={todayData ? todayData.user_messages.toLocaleString() : '0'}
            subtitle={todayData ? `${todayData.sessions} セッション` : undefined}
            icon={<svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>}
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <DailyActivityChart />
          <HourlyDistributionChart />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <ToolUsageChart />
          <ProjectSummary />
        </div>

        <RecentSessions />
      </main>
    </div>
  );
}
