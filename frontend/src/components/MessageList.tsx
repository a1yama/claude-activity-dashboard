import type { SessionMessage, ToolDetail } from '../types/api';

function parseToolDetails(json: string): ToolDetail[] {
  if (!json) return [];
  try {
    return JSON.parse(json) as ToolDetail[];
  } catch {
    return [];
  }
}

function formatTime(timestampJst: string): string {
  const d = new Date(timestampJst);
  return d.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function ToolBadge({ detail }: { detail: ToolDetail }) {
  return (
    <div className="flex items-start gap-1.5 text-xs">
      <span className="px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-700 font-mono font-medium shrink-0">
        {detail.name}
      </span>
      {detail.input && (
        <span className="text-gray-500 font-mono break-all">
          {detail.input}
        </span>
      )}
    </div>
  );
}

function UserMessage({ message }: { message: SessionMessage }) {
  const isMeta = message.is_meta === 1;
  return (
    <div className={`flex justify-end ${isMeta ? 'opacity-50' : ''}`}>
      <div className="max-w-[80%]">
        <div className="flex items-center justify-end gap-2 mb-1">
          <span className="text-xs text-gray-400">{formatTime(message.timestamp_jst)}</span>
          <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-600 text-white">
            User
          </span>
        </div>
        <div className="bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-3">
          {message.content_preview && (
            <p className="text-sm whitespace-pre-wrap break-words">
              {message.content_preview}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function AssistantMessage({ message }: { message: SessionMessage }) {
  const isMeta = message.is_meta === 1;
  const toolDetails = parseToolDetails(message.tool_details);

  return (
    <div className={`flex justify-start ${isMeta ? 'opacity-50' : ''}`}>
      <div className="max-w-[80%]">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-gray-700 text-white">
            Assistant
          </span>
          <span className="text-xs text-gray-400">{formatTime(message.timestamp_jst)}</span>
        </div>
        <div className="bg-gray-100 text-gray-900 rounded-2xl rounded-tl-sm px-4 py-3">
          {message.content_preview && (
            <p className="text-sm whitespace-pre-wrap break-words">
              {message.content_preview}
            </p>
          )}
          {toolDetails.length > 0 && (
            <div className={`flex flex-col gap-1 ${message.content_preview ? 'mt-2 pt-2 border-t border-gray-200' : ''}`}>
              {toolDetails.map((detail, i) => (
                <ToolBadge key={i} detail={detail} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function hasContent(msg: SessionMessage): boolean {
  if (msg.content_preview) return true;
  if (msg.tool_details && msg.tool_details !== '[]') return true;
  if (msg.tool_names && msg.tool_names !== '[]') return true;
  return false;
}

/** Group messages into rallies: each rally starts with a user message */
function groupRallies(messages: SessionMessage[]): SessionMessage[][] {
  const filtered = messages.filter(hasContent);
  const rallies: SessionMessage[][] = [];
  let current: SessionMessage[] = [];

  for (const msg of filtered) {
    if (msg.type === 'user' && current.length > 0) {
      rallies.push(current);
      current = [];
    }
    current.push(msg);
  }
  if (current.length > 0) {
    rallies.push(current);
  }
  return rallies;
}

export function MessageList({ messages }: { messages: SessionMessage[] }) {
  const rallies = groupRallies(messages);

  return (
    <div className="space-y-6">
      {rallies.map((rally, ri) => (
        <div key={ri} className="space-y-3">
          {rally.map((msg) =>
            msg.type === 'user' ? (
              <UserMessage key={msg.uuid} message={msg} />
            ) : (
              <AssistantMessage key={msg.uuid} message={msg} />
            )
          )}
          {ri < rallies.length - 1 && (
            <div className="border-t border-gray-200 my-2" />
          )}
        </div>
      ))}
    </div>
  );
}
