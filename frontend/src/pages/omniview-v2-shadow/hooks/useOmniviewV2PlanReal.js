import { useState, useEffect, useRef, useCallback } from 'react';
import { getOmniviewV2PlanRealMonthly } from '../../../services/api';

export function useOmniviewV2PlanReal(metricId = 'trips', dateFrom = null, dateTo = null) {
  const [planData, setPlanData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const abortRef = useRef(null);
  const mountedRef = useRef(true);

  const fetchPlanReal = useCallback(async () => {
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);

    try {
      const params = { metric_id: metricId };
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const result = await getOmniviewV2PlanRealMonthly(params, { signal: controller.signal });
      if (mountedRef.current && !controller.signal.aborted) {
        setPlanData(result);
        setLoading(false);
      }
    } catch (err) {
      if (mountedRef.current && err.name !== 'AbortError' && err.name !== 'CanceledError') {
        setError(err.message || 'Failed to load plan data');
        setLoading(false);
      }
    }
  }, [metricId, dateFrom, dateTo]);

  useEffect(() => {
    mountedRef.current = true;
    fetchPlanReal();
    return () => { mountedRef.current = false; };
  }, [fetchPlanReal]);

  return { planData, loading, error, refetch: fetchPlanReal };
}
