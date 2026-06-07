import { useState, useEffect, useRef, useCallback } from 'react';
import { getOmniviewV2Shell } from '../../../services/api';

export function useOmniviewV2Shell(sourceSystem = 'CT_TRIPS_2026', grain = 'day', dateFrom = null, dateTo = null) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const abortRef = useRef(null);
  const mountedRef = useRef(true);

  const fetchShell = useCallback(async () => {
    if (abortRef.current) {
      abortRef.current.abort();
    }

    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    try {
      const params = { source_system: sourceSystem, grain };
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;

      const result = await getOmniviewV2Shell(params, { signal: controller.signal });

      if (mountedRef.current && !controller.signal.aborted) {
        setData(result);
        setLoading(false);
      }
    } catch (err) {
      if (mountedRef.current && err.name !== 'AbortError' && err.name !== 'CanceledError') {
        setError(err.message || 'Failed to load shell data');
        setLoading(false);
      }
    }
  }, [sourceSystem, grain, dateFrom, dateTo]);

  useEffect(() => {
    mountedRef.current = true;
    fetchShell();
    return () => {
      mountedRef.current = false;
    };
  }, [fetchShell]);

  const refetch = useCallback(() => {
    fetchShell();
  }, [fetchShell]);

  return { data, loading, error, refetch };
}

export default useOmniviewV2Shell;
