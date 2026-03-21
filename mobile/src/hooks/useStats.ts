import { useState, useCallback } from 'react';
import { useAuth } from '@/auth/useAuth';
import { getStats, addStats, StatHistoryPoint, AddStatsPayload } from '@/api/stats';

interface UseStatsOptions {
  playerName: string;
  gameName: string;
  gameInstallment?: string;
  gameMode?: string;
}

interface UseStatsReturn {
  history: StatHistoryPoint[];
  loading: boolean;
  error: string | null;
  fetch: () => Promise<void>;
  submit: (payload: AddStatsPayload) => Promise<void>;
  submitting: boolean;
}

/**
 * Hook that manages fetching and submitting stats for a given player + game.
 * Keeps loading/error state so screens stay thin.
 */
export function useStats({
  playerName,
  gameName,
  gameInstallment,
  gameMode,
}: UseStatsOptions): UseStatsReturn {
  const { token } = useAuth();
  const [history, setHistory] = useState<StatHistoryPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    if (!token || !playerName || !gameName) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getStats(token, playerName, gameName, gameInstallment, gameMode);
      setHistory(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load stats');
    } finally {
      setLoading(false);
    }
  }, [token, playerName, gameName, gameInstallment, gameMode]);

  const submit = useCallback(async (payload: AddStatsPayload) => {
    if (!token) return;
    setSubmitting(true);
    setError(null);
    try {
      await addStats(token, payload);
      // Refresh history after a successful submission
      await fetch();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to submit stats');
      throw e; // re-throw so the screen can show an Alert if needed
    } finally {
      setSubmitting(false);
    }
  }, [token, fetch]);

  return { history, loading, error, fetch, submit, submitting };
}
