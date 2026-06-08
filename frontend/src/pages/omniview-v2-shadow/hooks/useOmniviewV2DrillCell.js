import { useState, useEffect, useRef, useCallback } from 'react';
import { getOmniviewV2DrillCell } from '../../../services/api';

export function useOmniviewV2DrillCell(cell, grain = 'day') {
  const [drillData, setDrillData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const abortRef = useRef(null);
  const mountedRef = useRef(true);

  const fetchDrill = useCallback(async () => {
    if (!cell || !cell.period || !cell.slice_label) return;
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);
    try {
      const params = {
        period: cell.period,
        business_slice_name: cell.slice_label || cell.label || '',
        grain: grain,
        metric_id: cell.metric_id || 'trips',
      };
      const result = await getOmniviewV2DrillCell(params, { signal: controller.signal });
      if (mountedRef.current && !controller.signal.aborted) {
        setDrillData(result);
        setLoading(false);
      }
    } catch (err) {
      if (mountedRef.current && err.name !== 'AbortError' && err.name !== 'CanceledError') {
        setError(err.message || 'Drill failed');
        setLoading(false);
      }
    }
  }, [cell?.period, cell?.slice_label, cell?.metric_id, grain]);

  useEffect(() => {
    mountedRef.current = true;
    fetchDrill();
    return () => { mountedRef.current = false; };
  }, [fetchDrill]);

  return { drillData, loading, error, refetch: fetchDrill };
}
