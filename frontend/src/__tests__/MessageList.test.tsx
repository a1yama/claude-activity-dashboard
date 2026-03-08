import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MessageList } from '../components/MessageList';
import type { SessionMessage } from '../types/api';

function makeMessage(overrides: Partial<SessionMessage> = {}): SessionMessage {
  return {
    uuid: 'msg-1',
    type: 'user',
    subtype: null,
    timestamp_jst: '2026-03-08T10:00:00',
    content_preview: 'Hello',
    tool_count: 0,
    tool_names: '',
    tool_details: '',
    is_meta: 0,
    ...overrides,
  };
}

describe('MessageList', () => {
  it('renders user and assistant messages with correct labels', () => {
    const messages = [
      makeMessage({ uuid: 'u1', type: 'user', content_preview: 'ユーザーの質問' }),
      makeMessage({ uuid: 'a1', type: 'assistant', content_preview: 'アシスタントの回答' }),
    ];

    render(<MessageList messages={messages} />);

    expect(screen.getByText('User')).toBeDefined();
    expect(screen.getByText('Assistant')).toBeDefined();
    expect(screen.getByText('ユーザーの質問')).toBeDefined();
    expect(screen.getByText('アシスタントの回答')).toBeDefined();
  });

  it('renders tool details with input info', () => {
    const messages = [
      makeMessage({
        uuid: 'a2',
        type: 'assistant',
        content_preview: 'ツール使用',
        tool_count: 2,
        tool_names: '["Bash","Read"]',
        tool_details: '[{"name":"Bash","input":"ls -la"},{"name":"Read","input":"/src/App.tsx"}]',
      }),
    ];

    render(<MessageList messages={messages} />);

    expect(screen.getByText('Bash')).toBeDefined();
    expect(screen.getByText('Read')).toBeDefined();
    expect(screen.getByText('ls -la')).toBeDefined();
  });

  it('renders meta messages with reduced opacity', () => {
    const messages = [
      makeMessage({ uuid: 'm1', type: 'user', content_preview: 'メタ', is_meta: 1 }),
    ];

    const { container } = render(<MessageList messages={messages} />);
    const messageDiv = container.querySelector('.opacity-50');
    expect(messageDiv).not.toBeNull();
  });

  it('handles empty tool_names gracefully', () => {
    const messages = [
      makeMessage({ uuid: 'e1', tool_names: '' }),
      makeMessage({ uuid: 'e2', tool_names: 'invalid-json' }),
    ];

    render(<MessageList messages={messages} />);

    expect(screen.getAllByText('User')).toHaveLength(2);
  });

  it('renders empty list without errors', () => {
    const { container } = render(<MessageList messages={[]} />);
    expect(container.querySelector('.space-y-3')).not.toBeNull();
  });
});
