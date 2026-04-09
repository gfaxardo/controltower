import { cellMatchesTrustSegment } from './omniviewMatrixUtils.js'

function sqlText (v) {
  return `'${String(v ?? '').replace(/'/g, "''")}'`
}

function sqlDate (v) {
  return `${sqlText(String(v ?? '').slice(0, 10))}::date`
}

function buildFilters ({ city, lob }) {
  return [
    city ? `AND city = ${sqlText(city)}` : '',
    lob ? `AND business_slice_name = ${sqlText(lob)}` : '',
  ].filter(Boolean).join('\n')
}

function buildResolvedFilters ({ city, lob }) {
  return [
    city ? `AND city = ${sqlText(city)}` : '',
    lob ? `AND business_slice_name = ${sqlText(lob)}` : '',
  ].filter(Boolean).join('\n')
}

function buildPeriodRange ({ periodKey, grain }) {
  const d = String(periodKey || '').slice(0, 10)
  if (!d) return null
  if (grain === 'monthly') {
    return {
      start: `${sqlDate(d.replace(/-\d{2}$/, '-01').slice(0, 10))}`,
    }
  }
  return {
    start: sqlDate(d),
  }
}

function compactNum (v) {
  if (v == null || v === '') return null
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  if (Math.abs(n) >= 1000) return n.toLocaleString()
  if (Math.abs(n) >= 1) return n.toFixed(2).replace(/\.00$/, '')
  return n.toFixed(4).replace(/0+$/, '').replace(/\.$/, '')
}

function severityRank (status) {
  if (status === 'blocked') return 2
  if (status === 'warning') return 1
  return 0
}

function buildEvidenceList (ctx) {
  const evidence = ctx.segment?.evidence && typeof ctx.segment.evidence === 'object'
    ? ctx.segment.evidence
    : {}
  const metricDelta = ctx.selection?.periodDeltas?.[ctx.kpiKey] || null
  const out = []

  if (metricDelta?.value != null) out.push({ label: 'Current', value: compactNum(metricDelta.value) })
  if (metricDelta?.previous != null) out.push({ label: 'Base', value: compactNum(metricDelta.previous) })
  if (metricDelta?.delta_pct != null) out.push({ label: 'Delta %', value: `${(metricDelta.delta_pct * 100).toFixed(1)}%` })
  if (metricDelta?.delta_abs_pp != null) out.push({ label: 'Delta pp', value: compactNum(metricDelta.delta_abs_pp) })
  if (ctx.raw && ctx.kpiKey && ctx.raw[ctx.kpiKey] != null) out.push({ label: 'Raw', value: compactNum(ctx.raw[ctx.kpiKey]) })

  const extraKeys = [
    ['gap_count', 'Gap days'],
    ['lag_days', 'Lag days'],
    ['day_fact_max', 'day_fact_max'],
    ['source_max', 'source_max'],
    ['period', 'Periodo'],
    ['rows_trips', 'Rows trips'],
    ['total_trips', 'Total trips'],
    ['trips_diff', 'Trips diff'],
    ['rows_revenue', 'Rows revenue'],
    ['total_revenue', 'Total revenue'],
    ['rev_diff', 'Revenue diff'],
  ]
  for (const [key, label] of extraKeys) {
    if (evidence[key] != null) out.push({ label, value: compactNum(evidence[key]) })
  }

  return out.slice(0, 10)
}

function defaultQueries (ctx) {
  const periodExpr = buildPeriodRange(ctx)
  const filters = buildFilters(ctx)
  return [
    {
      label: 'Fact slice',
      sql: `SELECT trip_date, city, business_slice_name, trips_completed, revenue_yego_net
FROM ops.real_business_slice_day_fact
WHERE 1=1
${periodExpr ? `  AND trip_date >= ${periodExpr.start}` : ''}
${filters ? `  ${filters}` : ''}
ORDER BY trip_date DESC
LIMIT 50;`,
    },
  ]
}

const DIAGNOSTIC_MAP = {
  ROLLUP_MISMATCH: {
    title: 'Descuadre entre rollup Matrix y universo resolved',
    summary: (ctx) => `La suma de líneas de Matrix no está reconciliando con el universo canon para ${ctx.periodKey}. Eso suele indicar duplicación, pérdida de mapping o una carga mensual inconsistente en el rollup.`,
    causes: [
      'Duplicados o faltantes en mapping de business slice.',
      'Carga mensual incremental incompleta o corrida sobre un subconjunto.',
      'Diferencia entre agregación de facts y universo resolved.',
    ],
    queries: (ctx) => {
      const filters = buildFilters(ctx)
      const resolvedFilters = buildResolvedFilters(ctx)
      return [
        {
          label: 'Month fact rollup',
          sql: `SELECT month, city, business_slice_name, SUM(trips_completed) AS trips_completed, SUM(revenue_yego_net) AS revenue_yego_net
FROM ops.real_business_slice_month_fact
WHERE month = ${sqlDate(ctx.periodKey)}
${filters ? `  ${filters}` : ''}
GROUP BY 1, 2, 3
ORDER BY city, business_slice_name;`,
        },
        {
          label: 'Resolved canon check',
          sql: `SELECT trip_month, city, business_slice_name,
       COUNT(*) FILTER (WHERE completed_flag) AS trips_completed,
       SUM(revenue_yego_net) FILTER (WHERE completed_flag) AS revenue_yego_net
FROM ops.v_real_trips_business_slice_resolved
WHERE resolution_status = 'resolved'
  AND trip_month = ${sqlDate(ctx.periodKey)}
${resolvedFilters ? `  ${resolvedFilters}` : ''}
GROUP BY 1, 2, 3
ORDER BY city, business_slice_name;`,
        },
      ]
    },
  },
  MONTH_REVENUE_MISMATCH: {
    title: 'Revenue mensual no reconciliado',
    summary: (ctx) => `El revenue mensual consolidado para ${ctx.periodKey} no cuadra con la fuente canon. Ejecutivamente esto vuelve poco confiable cualquier lectura de revenue o margen sobre esta tajada.`,
    causes: [
      'Cálculo de revenue distinto entre facts y viajes resueltos.',
      'Backfill parcial del mes o corte mensual incompleto.',
      'Aplicación inconsistente de comisiones o signado de revenue.',
    ],
    queries: (ctx) => {
      const filters = buildFilters(ctx)
      const resolvedFilters = buildResolvedFilters(ctx)
      return [
        {
          label: 'Month fact revenue',
          sql: `SELECT month, city, business_slice_name, SUM(revenue_yego_net) AS revenue_yego_net
FROM ops.real_business_slice_month_fact
WHERE month = ${sqlDate(ctx.periodKey)}
${filters ? `  ${filters}` : ''}
GROUP BY 1, 2, 3
ORDER BY revenue_yego_net DESC;`,
        },
        {
          label: 'Resolved revenue',
          sql: `SELECT trip_month, city, business_slice_name,
       SUM(revenue_yego_net) FILTER (WHERE completed_flag) AS revenue_yego_net
FROM ops.v_real_trips_business_slice_resolved
WHERE resolution_status = 'resolved'
  AND trip_month = ${sqlDate(ctx.periodKey)}
${resolvedFilters ? `  ${resolvedFilters}` : ''}
GROUP BY 1, 2, 3
ORDER BY revenue_yego_net DESC;`,
        },
      ]
    },
  },
  REVENUE_WITHOUT_COMPLETED: {
    title: 'Revenue sin viajes completados',
    summary: () => 'Hay filas donde aparece revenue neto sin viajes completados. Operativamente esto rompe la semántica de la Matrix y puede distorsionar tanto el revenue como métricas derivadas por conductor o ticket.',
    causes: [
      'Agregación day_fact sin respetar completed_flag.',
      'Revenue heredado de viajes no cerrados o anulados.',
      'Reglas de negocio no alineadas entre ETL y consumo ejecutivo.',
    ],
    queries: (ctx) => {
      const periodExpr = buildPeriodRange(ctx)
      const filters = buildFilters(ctx)
      return [
        {
          label: 'Rows with revenue but no completed trips',
          sql: `SELECT trip_date, city, business_slice_name, trips_completed, revenue_yego_net
FROM ops.real_business_slice_day_fact
WHERE COALESCE(trips_completed, 0) = 0
  AND COALESCE(revenue_yego_net, 0) <> 0
${periodExpr ? `  AND trip_date >= ${periodExpr.start}` : ''}
${filters ? `  ${filters}` : ''}
ORDER BY trip_date DESC
LIMIT 50;`,
        },
        {
          label: 'Daily revenue footprint',
          sql: `SELECT trip_date, city, business_slice_name,
       SUM(trips_completed) AS trips_completed,
       SUM(revenue_yego_net) AS revenue_yego_net
FROM ops.real_business_slice_day_fact
WHERE 1=1
${periodExpr ? `  AND trip_date >= ${periodExpr.start}` : ''}
${filters ? `  ${filters}` : ''}
GROUP BY 1, 2, 3
ORDER BY trip_date DESC
LIMIT 90;`,
        },
      ]
    },
  },
  DAY_FACT_DATE_GAPS: {
    title: 'Huecos en day_fact',
    summary: () => 'Faltan días completos en `day_fact`. Eso sesga comparativos diarios y semanales, y puede dar una falsa impresión de caída o mejora por ausencia de datos en vez de cambio real del negocio.',
    causes: [
      'Job incremental diario no ejecutado o fallado parcialmente.',
      'Backfill incompleto en uno o varios meses.',
      'Corte temporal o ventana de carga inconsistente.',
    ],
    queries: (ctx) => {
      const filters = buildFilters(ctx)
      return [
        {
          label: 'Missing dates in day_fact',
          sql: `WITH series AS (
  SELECT generate_series(${sqlDate(ctx.periodKey)} - INTERVAL '21 day', ${sqlDate(ctx.periodKey)}, '1 day')::date AS d
),
present AS (
  SELECT DISTINCT trip_date AS d
  FROM ops.real_business_slice_day_fact
  WHERE trip_date >= ${sqlDate(ctx.periodKey)} - INTERVAL '21 day'
${filters ? `    ${filters}` : ''}
)
SELECT s.d AS missing_date
FROM series s
LEFT JOIN present p USING (d)
WHERE p.d IS NULL
ORDER BY 1;`,
        },
        {
          label: 'Daily footprint around gap window',
          sql: `SELECT trip_date, city, business_slice_name, COUNT(*) AS rows_count,
       SUM(trips_completed) AS trips_completed,
       SUM(revenue_yego_net) AS revenue_yego_net
FROM ops.real_business_slice_day_fact
WHERE trip_date >= ${sqlDate(ctx.periodKey)} - INTERVAL '21 day'
${filters ? `  ${filters}` : ''}
GROUP BY 1, 2, 3
ORDER BY trip_date DESC;`,
        },
      ]
    },
  },
  FACTS_UNREADABLE: {
    title: 'Facts no legibles para auditoría',
    summary: () => 'La capa base de facts no pudo leerse correctamente. En este estado la Matrix puede seguir renderizando parcialmente, pero la confianza operativa debe considerarse bloqueada hasta confirmar que las tablas/vistas existen y responden.',
    causes: [
      'Migraciones pendientes o revertidas.',
      'Permisos insuficientes sobre objetos `ops.real_business_slice_*_fact`.',
      'Vista o tabla inválida tras despliegue.',
    ],
    queries: () => ([
      {
        label: 'Presence check',
        sql: `SELECT
  to_regclass('ops.real_business_slice_day_fact') AS day_fact,
  to_regclass('ops.real_business_slice_week_fact') AS week_fact,
  to_regclass('ops.real_business_slice_month_fact') AS month_fact;`,
      },
      {
        label: 'Basic max checks',
        sql: `SELECT
  (SELECT MAX(trip_date)::date FROM ops.real_business_slice_day_fact) AS day_fact_max,
  (SELECT MAX(week_start)::date FROM ops.real_business_slice_week_fact) AS week_fact_max,
  (SELECT MAX(month)::date FROM ops.real_business_slice_month_fact) AS month_fact_max;`,
      },
    ]),
  },
  __default: {
    title: 'Incidencia de confianza operativa',
    summary: (ctx) => `Se detectó una incidencia de trust sobre la selección actual${ctx.segment?.code ? ` (${ctx.segment.code})` : ''}. La señal requiere revisión antes de usar esta celda como base de decisión ejecutiva.`,
    causes: [
      'Desalineación entre facts, fuente canon o ventana temporal.',
      'Carga incremental incompleta.',
      'Validación de consistencia no superada.',
    ],
    queries: defaultQueries,
  },
}

export function resolveTrustIssueForSelection (matrixTrust, selection, grain) {
  if (!matrixTrust || !selection) return null
  const cityName = selection?.raw?.city || null
  const lineName = selection?.lineData?.business_slice_name || null
  const matches = (matrixTrust.affected_segments || []).filter((segment) =>
    cellMatchesTrustSegment(segment, {
      grain,
      cityName,
      lineName,
      periodKey: selection.period,
      kpiKey: selection.kpiKey,
    })
  )

  const segment = [...matches].sort((a, b) =>
    severityRank(b?.trust_status) - severityRank(a?.trust_status) ||
    Number(b?.severity_weight || 0) - Number(a?.severity_weight || 0)
  )[0]

  if (!segment) return null

  const ctx = {
    matrixTrust,
    selection,
    grain,
    segment,
    city: cityName,
    lob: lineName,
    periodKey: selection.period,
    kpiKey: selection.kpiKey,
    raw: selection.raw || {},
  }

  const def = DIAGNOSTIC_MAP[segment.code] || DIAGNOSTIC_MAP.__default
  const hardCap = matrixTrust?.operational_decision?.confidence?.hard_cap || null
  const issueHistory = matrixTrust?.issue_history?.[segment.issue_key] || null
  const issueCluster = (matrixTrust?.issue_clusters || []).find((c) => c.cluster_key === segment.cluster_key) || null
  const earlyWarnings = (matrixTrust?.early_warnings || []).filter((w) =>
    segment.code === 'DAY_FACT_DATE_GAPS'
      ? w.type === 'gaps_increase'
      : segment.code === 'DERIVED_BEHIND_SOURCE' || segment.code === 'SOURCE_MAX_UNAVAILABLE'
        ? w.type === 'freshness_deterioration'
        : w.type === 'coverage_drop'
  )
  const actionHistory = (matrixTrust?.issue_actions_recent || []).filter((row) => row.issue_key === segment.issue_key)
  return {
    code: segment.code,
    issueKey: segment.issue_key,
    title: def.title,
    summary: def.summary(ctx),
    causes: def.causes,
    severity: segment.trust_status,
    priority: segment.trust_status === 'blocked' ? 'Alta' : 'Media',
    decisionMode: matrixTrust?.operational_decision?.decision_mode || null,
    confidence: matrixTrust?.operational_decision?.confidence || null,
    evidence: buildEvidenceList(ctx),
    action: {
      primary: segment?.action_engine?.action || 'Revisar pipeline y reconciliar con la fuente canon.',
      process: segment?.action_engine?.process || 'Validar carga, revisar logs y repetir reconciliación del periodo afectado.',
    },
    queries: (def.queries(ctx) || defaultQueries(ctx)).slice(0, 2),
    hardCapReason: hardCap?.code === segment.code ? hardCap.reason : null,
    issueHistory,
    issueCluster,
    earlyWarnings,
    actionHistory,
    actionPayload: {
      issue_key: segment.issue_key,
      code: segment.code,
      city: segment.city || cityName,
      lob: segment.lob || lineName,
      period_key: segment.period_key || selection.period,
      metric: selection.kpiKey,
      action_label: segment?.action_engine?.action || def.title,
    },
    nav: segment.nav || {},
  }
}
