import type { SessionMessage, ToolDetail } from '../types/api';

function parseToolDetails(json: string): ToolDetail[] {
  if (!json) return [];
  try {
    return JSON.parse(json) as ToolDetail[];
  } catch {
    return [];
  }
}

function shortenPath(path: string): string {
  const parts = path.split('/');
  if (parts.length <= 3) return path;
  return '.../' + parts.slice(-3).join('/');
}

function formatTime(timestampJst: string): string {
  const d = new Date(timestampJst);
  return d.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

const MESSAGE_STYLES: Record<string, { bg: string; label: string; text: string }> = {
  user: { bg: 'bg-blue-50 border-blue-200', label: 'User', text: 'text-blue-900' },
  assistant: { bg: 'bg-gray-50 border-gray-200', label: 'Assistant', text: 'text-gray-900' },
};

function ToolBadge({ detail }: { detail: ToolDetail }) {
  const summary = detail.input ? shortenPath(detail.input) : '';
  return (
    <div className="flex items-center gap-1.5 text-xs">
      <span className="px-2 py-0.5 rounded bg-indigo-100 text-indigo-700 font-mono font-medium shrink-0">
        {detail.name}
      </span>
      {summary && (
        <span className="text-gray-500 font-mono truncate max-w-[400px]" title={detail.input}>
          {summary}
        </span>
      )}
    </div>
  );
}

function MessageItem({ message }: { message: SessionMessage }) {
  const isMeta = message.is_meta === 1;
  const style = MESSAGE_STYLES[message.type] ?? { bg: 'bg-white border-gray-200', label: message.type, text: 'text-gray-900' };
  const toolDetails = parseToolDetails(message.tool_details);

  return (
    <div className={`rounded-lg border p-4 ${style.bg} ${isMeta ? 'opacity-50' : ''}`}>
      <div className="flex items-center gap-2 mb-2">
        <span className={`text-xs font-semibold px-2 py-0.5 rounded ${
          message.type === 'user' ? 'bg-blue-200 text-blue-800' : 'bg-gray-200 text-gray-700'
        }`}>
          {style.label}
        </span>
        <span className="text-xs text-gray-500">{formatTime(message.timestamp_jst)}</span>
        {message.subtype && (
          <span className="text-xs text-gray-400">{message.subtype}</span>
        )}
      </div>
      {message.content_preview && (
        <p className={`text-sm whitespace-pre-wrap break-words ${style.text}`}>
          {message.content_preview}
        </p>
      )}
      {toolDetails.length > 0 && (
        <div className="flex flex-col gap-1 mt-2">
          {toolDetails.map((detail, i) => (
            <ToolBadge key={i} detail={detail} />
          ))}
        </div>
      )}
    </div>
  );
}

function hasContent(msg: SessionMessage): boolean {
  if (msg.content_preview) return true;
  if (msg.tool_details && msg.tool_details !== '[]') return true;
  if (msg.tool_names && msg.tool_names !== '[]') return true;
  return false;
}

export function MessageList({ messages }: { messages: SessionMessage[] }) {
  return (
    <div className="space-y-3">
      {messages.filter(hasContent).map((msg) => (
        <MessageItem key={msg.uuid} message={msg} />
      ))}
    </div>
  );
}
