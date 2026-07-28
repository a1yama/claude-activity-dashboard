import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
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

  it('clears a previous error when refetching', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({ ok: false, status: 500 } as Response)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ rows: [{ id: 1 }] }) } as Response);

    const { result, rerender } = renderHook(
      ({ name }) => useQuery<{ id: number }>(name),
      { initialProps: { name: 'first-query' } },
    );

    await waitFor(() => expect(result.current.error).toBe('HTTP 500'));

    rerender({ name: 'second-query' });

    await waitFor(() => expect(result.current.data).toEqual([{ id: 1 }]));
    expect(result.current.error).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('treats an unexpected response shape as an error', async () => {
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce({ ok: true, json: async () => ({ rows: [{ id: 1 }] }) } as Response)
      .mockResolvedValueOnce({ ok: true, json: async () => ({ ok: false }) } as Response);

    const { result, rerender } = renderHook(
      ({ name }) => useQuery<{ id: number }>(name),
      { initialProps: { name: 'first-query' } },
    );

    await waitFor(() => expect(result.current.data).toEqual([{ id: 1 }]));

    rerender({ name: 'second-query' });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual([]);
    expect(result.current.error).toBe('Unexpected response shape');
  });

  it('surfaces the error message from a 200 error payload', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ ok: false, error: 'no such column: foo' }),
    } as Response);

    const { result } = renderHook(() => useQuery<unknown>('broken-query'));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe('no such column: foo');
  });

  it('ignores a stale response that resolves after the query changed', async () => {
    let resolveFirst!: (res: Response) => void;
    const firstResponse = new Promise<Response>((resolve) => {
      resolveFirst = resolve;
    });

    vi.spyOn(globalThis, 'fetch')
      .mockReturnValueOnce(firstResponse)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ rows: [{ id: 2 }] }),
      } as Response);

    const { result, rerender } = renderHook(
      ({ name }) => useQuery<{ id: number }>(name),
      { initialProps: { name: 'slow-query' } },
    );

    rerender({ name: 'fast-query' });
    await waitFor(() => expect(result.current.data).toEqual([{ id: 2 }]));

    resolveFirst({ ok: true, json: async () => ({ rows: [{ id: 1 }] }) } as Response);
    // 遅れて解決した fetch が state に反映されうるまでイベントループを回す
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(result.current.data).toEqual([{ id: 2 }]);
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
