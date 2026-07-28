import { useParams, Link } from 'react-router-dom';
import { useQuery } from '../hooks/useQuery';
import { MessageList } from '../components/MessageList';
import { LoadingSpinner } from '../components/LoadingSpinner';
import type { SessionDetail as SessionDetailType, SessionMessage } from '../types/api';

function parseDate(iso: string): Date {
  // DB の時刻は UTC。オフセットなしの文字列はブラウザがローカル時刻と解釈するため UTC を明示する
  const hasOffset = /Z$|[+-]\d{2}:?\d{2}$/.test(iso);
  return new Date(hasOffset ? iso : iso.replace(' ', 'T') + 'Z');
}

function formatDateTime(iso: string): string {
  const d = parseDate(iso);
  return d.toLocaleString('ja-JP', {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
    timeZone: 'Asia/Tokyo',
  });
}

function duration(start: string, end: string): string {
  const ms = parseDate(end).getTime() - parseDate(start).getTime();
  const mins = Math.round(ms / 60000);
  if (mins < 60) return `${mins}分`;
  const hours = Math.floor(mins / 60);
  return `${hours}時間${mins % 60}分`;
}

function SessionUnavailable({ error }: { error: string | null }) {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-center">
        {error ? (
          <p className="text-red-600 mb-4">データを取得できませんでした（{error}）。</p>
        ) : (
          <p className="text-gray-500 mb-4">セッションが見つかりません</p>
        )}
        <Link to="/" className="text-indigo-600 hover:underline">← ダッシュボードに戻る</Link>
      </div>
    </div>
  );
}

export function SessionDetail() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const params = { session_id: sessionId! };
  const { data: sessions, loading: loadingDetail, error: detailError } = useQuery<SessionDetailType>('session-detail', params);
  const { data: messages, loading: loadingMessages, error: messagesError } = useQuery<SessionMessage>('session-messages', params);

  if (loadingDetail || loadingMessages) return <LoadingSpinner />;

  // 取得失敗を「セッションが見つかりません」と誤読させない
  const error = detailError ?? messagesError;
  const session = sessions[0];
  if (error || !session) return <SessionUnavailable error={error} />;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-6 py-4">
          <Link to="/" className="text-sm text-indigo-600 hover:underline mb-2 inline-block">← ダッシュボード</Link>
          <h1 className="text-lg font-bold text-gray-900 truncate">{session.project_name}</h1>
          <div className="flex flex-wrap gap-4 mt-2 text-sm text-gray-500">
            <span>{formatDateTime(session.first_message_at)} 〜 {formatDateTime(session.last_message_at)}</span>
            <span>{duration(session.first_message_at, session.last_message_at)}</span>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-6 space-y-6">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="bg-white rounded-lg border border-gray-200 p-4 text-center">
            <div className="text-2xl font-bold text-gray-900">{session.message_count}</div>
            <div className="text-xs text-gray-500">メッセージ</div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4 text-center">
            <div className="text-2xl font-bold text-blue-600">{session.user_message_count}</div>
            <div className="text-xs text-gray-500">ユーザー</div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4 text-center">
            <div className="text-2xl font-bold text-gray-600">{session.assistant_message_count}</div>
            <div className="text-xs text-gray-500">アシスタント</div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4 text-center">
            <div className="text-2xl font-bold text-indigo-600">{session.tool_use_count}</div>
            <div className="text-xs text-gray-500">ツール使用</div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">メッセージ ({messages.length})</h2>
          <MessageList messages={messages} />
        </div>
      </main>
    </div>
  );
}
