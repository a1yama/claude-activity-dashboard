import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useQuery } from '../hooks/useQuery';

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('useQuery', () => {
  it('fetches data and returns rows', async () => {
    const mockData = [{ id: 1, name: 'test' }];
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ rows: mockData }),
    } as Response);

    const { result } = renderHook(() => useQuery<{ id: number; name: string }>('test-query'));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.data).toEqual(mockData);
    expect(result.current.error).toBeNull();
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/claude_activity/test-query.json?_shape=objects',
    );
  });

  it('appends params to URL', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ([]),
    } as Response);

    const { result } = renderHook(() =>
      useQuery<unknown>('session-detail', { session_id: 'abc-123' }),
    );

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/claude_activity/session-detail.json?_shape=objects&session_id=abc-123',
    );
  });

  it('sets error on HTTP failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 404,
    } as Response);

    const { result } = renderHook(() => useQuery<unknown>('not-found'));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('HTTP 404');
    expect(result.current.data).toEqual([]);
  });

  it('handles array response format', async () => {
    const mockData = [{ id: 1 }];
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => mockData,
    } as Response);

    const { result } = renderHook(() => useQuery<{ id: number }>('array-query'));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.data).toEqual(mockData);
  });
});
