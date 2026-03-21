import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '@/auth/useAuth';
import { getStatTicker } from '@/api/stats';

interface UseTickerReturn {
  tickerUrl: string | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/**
 * Hook that fetches the OBS stat ticker URL for a given player.
 * Automatically re-fetches on a configurable interval so the WebView
 * always shows the most recent ticker endpoint.
 *
 * @param playerName  - Player to fetch ticker for
 * @param intervalMs  - How often to refresh the URL (default: 30s)
 */
export function useTicker(playerName: string, intervalMs = 30_000): UseTickerReturn {
  const { token } = useAuth();
  const [tickerUrl, setTickerUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchTicker = useCallback(async () => {
    if (!token || !playerName) return;
    setLoading(true);
    setError(null);
    try {
      const { ticker_url } = await getStatTicker(token, playerName);
      setTickerUrl(ticker_url);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to fetch ticker');
    } finally {
      setLoading(false);
    }
  }, [token, playerName]);

  useEffect(() => {
    fetchTicker();
    intervalRef.current = setInterval(fetchTicker, intervalMs);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchTicker, intervalMs]);

  return { tickerUrl, loading, error, refresh: fetchTicker };
}
