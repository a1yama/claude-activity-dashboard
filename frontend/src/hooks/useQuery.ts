import { useState, useEffect } from 'react';

function buildUrl(queryName: string, params?: Record<string, string>): string {
  const base = `/api/claude_activity/${queryName}.json?_shape=objects`;
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
    const fetchData = async () => {
      setLoading(true);
      try {
        const res = await fetch(buildUrl(queryName, params));
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (json.rows) {
          setData(json.rows as T[]);
        } else if (Array.isArray(json)) {
          setData(json as T[]);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [queryName, paramsKey]);

  return { data, loading, error };
}
