import { useState, useEffect, useRef, useCallback } from 'react';
import { getOmniviewV2Matrix } from '../../../services/api';
import shellToMatrixResponse from '../adapters/shellToMatrixResponse';

const FALLBACK_ENABLED = import.meta.env.VITE_OV2_ALLOW_MATRIX_FALLBACK === 'true';
let fallbackActivationCount = 0;

function logFallback(reason) {
  fallbackActivationCount++;
  console.warn("[OV2] MATRIX_FALLBACK_ACTIVE — DEBUG ONLY", {
    reason,
    count: fallbackActivationCount,
    timestamp: new Date().toISOString(),
  });
}

export function useOmniviewV2Matrix(sourceSystem = 'CT_TRIPS_2026', grain = 'day', metricId = 'orders', dateFrom = null, dateTo = null, shellData = null) {
  const [matrixData, setMatrixData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [usingFallback, setUsingFallback] = useState(false);
  const abortRef = useRef(null);
  const mountedRef = useRef(true);

  const fetchMatrix = useCallback(async () => {
    if (abortRef.current) {
      abortRef.current.abort();
    }

    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);
    setUsingFallback(false);

    try {
      const params = { source_system: sourceSystem, grain, metric_id: metricId };
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;

      const result = await getOmniviewV2Matrix(params, { signal: controller.signal });

      if (mountedRef.current && !controller.signal.aborted) {
        setMatrixData(result);
        setLoading(false);
      }
    } catch (err) {
      if (mountedRef.current && err.name !== 'AbortError' && err.name !== 'CanceledError') {
        const errMsg = err.message || 'Matrix endpoint failed';

        if (FALLBACK_ENABLED) {
          logFallback(errMsg);
          if (shellData) {
            setMatrixData(shellToMatrixResponse(shellData, 'orders'));
            setUsingFallback(true);
            setLoading(false);
            return;
          }
        }

        setError(errMsg);
        setLoading(false);
      }
    }
  }, [sourceSystem, grain, metricId, dateFrom, dateTo, shellData]);

  useEffect(() => {
    mountedRef.current = true;
    fetchMatrix();
    return () => {
      mountedRef.current = false;
    };
  }, [fetchMatrix]);

  const refetch = useCallback(() => {
    fetchMatrix();
  }, [fetchMatrix]);

  return { matrixData, loading, error, usingFallback, refetch };
}

export default useOmniviewV2Matrix;
