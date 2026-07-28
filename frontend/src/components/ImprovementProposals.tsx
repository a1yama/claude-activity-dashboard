import { useQuery } from '../hooks/useQuery';
import type { ImprovementProposal } from '../types/api';
import { ChartCard } from './ChartCard';

const CATEGORY_LABEL: Record<ImprovementProposal['category'], string> = {
  claude_md: 'CLAUDE.md',
  skill: 'スキル化',
  prompt: 'プロンプト',
};

const CATEGORY_STYLE: Record<ImprovementProposal['category'], string> = {
  claude_md: 'bg-blue-50 text-blue-700',
  skill: 'bg-green-50 text-green-700',
  prompt: 'bg-amber-50 text-amber-700',
};

const STATUS_LABEL: Record<ImprovementProposal['status'], string> = {
  open: '未対応',
  adopted: '採用',
  rejected: '却下',
};

const STATUS_STYLE: Record<ImprovementProposal['status'], string> = {
  open: 'bg-gray-100 text-gray-600',
  adopted: 'bg-emerald-50 text-emerald-700',
  rejected: 'bg-gray-100 text-gray-400',
};

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString('ja-JP', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Tokyo',
  });
}

export function ImprovementProposals() {
  const { data, loading, error } = useQuery<ImprovementProposal>('improvement-proposals');

  const generatedAt = data.length > 0 ? data[0].generated_at : null;
  const periodDays = data.length > 0 ? data[0].period_days : null;

  return (
    <ChartCard
      title="今週の改善候補"
      loading={loading}
      error={error}
      isEmpty={data.length === 0}
      emptyMessage="改善候補はまだありません（週次で自動生成されます）。"
      headerRight={
        generatedAt && (
          <span className="text-xs text-gray-400">
            直近{periodDays}日 / {formatDateTime(generatedAt)} 生成
          </span>
        )
      }
    >
      <ul className="space-y-4">
        {data.map((p) => (
          <li
            key={p.id}
            className={`border border-gray-100 rounded-lg p-4 ${p.status === 'open' ? '' : 'opacity-60'}`}
          >
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-xs font-medium px-2 py-0.5 rounded ${STATUS_STYLE[p.status]}`}>
                {STATUS_LABEL[p.status]}
              </span>
              <span
                className={`text-xs font-medium px-2 py-0.5 rounded ${CATEGORY_STYLE[p.category]}`}
              >
                {CATEGORY_LABEL[p.category]}
              </span>
              <span className="font-medium text-gray-900">{p.title}</span>
              <span className="text-xs text-gray-400 font-mono ml-auto">#{p.id}</span>
            </div>
            <p className="text-sm text-gray-600 mb-2">{p.rationale}</p>
            <pre className="text-xs bg-gray-50 text-gray-700 rounded p-3 whitespace-pre-wrap break-words">
              {p.suggestion}
            </pre>
            {p.target_file && (
              <p className="text-xs text-gray-400 mt-2 font-mono">{p.target_file}</p>
            )}
          </li>
        ))}
      </ul>
      <p className="text-xs text-gray-400 mt-4">
        採否の記録は Mac 側で <code className="font-mono">make proposal-adopt ID=1</code>
        {' / '}
        <code className="font-mono">make proposal-reject ID=1</code>（次回の同期で反映）
      </p>
    </ChartCard>
  );
}
