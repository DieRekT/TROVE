import { useState, useEffect, useCallback } from 'react';

export interface Article {
  trove_id: string;
  title: string;
  date: string;
  source: string;
  url: string;
  snippet: string;
  pinned?: boolean;
}

export interface ContextData {
  ok: boolean;
  sid: string;
  items: Article[];
}

export function useContextStore() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchContext = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/context');
      const data: ContextData = await res.json();
      if (data.ok) {
        setArticles(data.items || []);
      } else {
        setError('Failed to fetch context');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      console.error('Failed to fetch context:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const pinArticle = useCallback(async (troveId: string) => {
    try {
      await fetch(`/api/context/pin/${troveId}`, { method: 'POST' });
      await fetchContext();
    } catch (err) {
      console.error('Failed to pin article:', err);
      throw err;
    }
  }, [fetchContext]);

  const unpinArticle = useCallback(async (troveId: string) => {
    try {
      await fetch(`/api/context/unpin/${troveId}`, { method: 'POST' });
      await fetchContext();
    } catch (err) {
      console.error('Failed to unpin article:', err);
      throw err;
    }
  }, [fetchContext]);

  const clearContext = useCallback(async () => {
    try {
      await fetch('/api/context', { method: 'DELETE' });
      await fetchContext();
    } catch (err) {
      console.error('Failed to clear context:', err);
      throw err;
    }
  }, [fetchContext]);

  const trackArticle = useCallback(async (article: Omit<Article, 'pinned'>) => {
    try {
      await fetch('/api/context/track', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(article),
      });
      await fetchContext();
    } catch (err) {
      console.error('Failed to track article:', err);
      throw err;
    }
  }, [fetchContext]);

  useEffect(() => {
    fetchContext();
  }, [fetchContext]);

  return {
    articles,
    loading,
    error,
    fetchContext,
    pinArticle,
    unpinArticle,
    clearContext,
    trackArticle,
  };
}

