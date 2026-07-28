import { useState, useEffect } from 'react';

// dev: Vite が /api を Datasette にプロキシ
// prod: Caddy が /api を Datasette にプロキシ（strip_prefix）
const API_PREFIX = '/api';

function buildUrl(queryName: string, params?: Record<string, string>): string {
  const base = `${API_PREFIX}/claude_activity/${queryName}.json?_shape=objects`;
  if (!params) return base;
  const searchParams = new URLSearchParams(params);
  return `${base}&${searchParams.toString()}`;
}

export function useQuery<T>(queryName: string, params?: Record<string, string>) {
  const [data, setData] = useState<T[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const paramsKey = params ? JSON.stringify(params) : '';

  useEffect(() => {
    // 先行リクエストが後から解決して新しい結果を上書きするのを防ぐ
    let stale = false;

    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(buildUrl(queryName, params));
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (stale) return;
        if (json.rows) {
          setData(json.rows as T[]);
        } else if (Array.isArray(json)) {
          setData(json as T[]);
        } else {
          // Datasette は SQL エラーを 200 + エラーオブジェクトで返すことがある。
          // 「0件」と誤読させないよう、データを空にしたうえでエラー扱いにする
          setData([]);
          throw new Error(
            typeof json.error === 'string' ? json.error : 'Unexpected response shape',
          );
        }
      } catch (e) {
        if (stale) return;
        setError(e instanceof Error ? e.message : 'Unknown error');
      } finally {
        if (!stale) setLoading(false);
      }
    };
    fetchData();

    return () => {
      stale = true;
    };
    // params はレンダー毎に新しい参照になるため、内容を表す paramsKey を依存に使う
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryName, paramsKey]);

  return { data, loading, error };
}
