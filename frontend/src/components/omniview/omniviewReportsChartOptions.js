/**
 * Opciones ECharts para BusinessSliceOmniviewReports (datos alineados a la matriz).
 */
import { ECHARTS_AXIS, ECHARTS_COLORS, ECHARTS_TEXT } from './echartsTheme.js'
import { fmtValue, periodLabelShort } from './omniviewMatrixUtils.js'

function axisValueFormatter (kpiKey) {
  return (v) => {
    if (v == null || Number.isNaN(Number(v))) return ''
    return fmtValue(Number(v), kpiKey)
  }
}

/**
 * Gráfico principal: varias líneas por período (mismo KPI).
 * @param {string} [titleText] — título (p. ej. nombre del KPI)
 * @param {string} [subtext] — ventana temporal y grano
 */
export function buildMainLineOption ({
  chartData,
  seriesList,
  kpiKey,
  titleText,
  subtext,
}) {
  const categories = chartData.map((d) => d.xlabel)
  const hasTitle = Boolean(titleText || subtext)

  const series = seriesList.map((s, idx) => {
    return {
      name: s.label,
      type: 'line',
      smooth: 0.35,
      symbol: 'circle',
      symbolSize: 5,
      showSymbol: false,
      lineStyle: { width: 2.5, color: s.color },
      itemStyle: { color: s.color },
      emphasis: { focus: 'series' },
      areaStyle: {
        opacity: 0.14,
        color: s.color,
      },
      data: chartData.map((row) => {
        const val = row[`v${idx}`]
        return val != null && !Number.isNaN(val) ? val : null
      }),
    }
  })

  return {
    color: ECHARTS_COLORS,
    textStyle: ECHARTS_TEXT,
    animationDuration: 500,
    title: hasTitle
      ? {
          text: titleText || '',
          subtext: subtext || '',
          left: 12,
          top: 6,
          textStyle: { color: '#0f172a', fontSize: 14, fontWeight: 600 },
          subtextStyle: { color: '#64748b', fontSize: 11, fontWeight: 400 },
        }
      : undefined,
    grid: {
      left: 56,
      right: 24,
      top: hasTitle ? 78 : 48,
      bottom: 100,
      containLabel: false,
    },
    toolbox: {
      right: 12,
      top: 8,
      feature: {
        dataZoom: { yAxisIndex: false, title: { zoom: 'Zoom', back: 'Restaurar zoom' } },
        restore: { title: 'Restaurar' },
        saveAsImage: { title: 'Descargar PNG', name: 'omniview-reportes', pixelRatio: 2 },
      },
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', crossStyle: { color: '#94a3b8' } },
      backgroundColor: 'rgba(15, 23, 42, 0.94)',
      borderColor: '#334155',
      textStyle: { color: '#f8fafc', fontSize: 12 },
      formatter (params) {
        if (!params?.length) return ''
        const head = params[0].axisValueLabel || params[0].name
        let html = `<div style="font-weight:600;margin-bottom:6px;border-bottom:1px solid #334155;padding-bottom:4px">${head}</div>`
        for (const p of params) {
          const v = fmtValue(p.value, kpiKey)
          html += `<div style="margin-top:4px"><span style="display:inline-block;margin-right:6px;border-radius:50%;width:8px;height:8px;background:${p.color}"></span>${p.seriesName}: <b>${v}</b></div>`
        }
        return html
      },
    },
    legend: {
      type: 'scroll',
      bottom: 8,
      left: 'center',
      textStyle: { color: '#475569', fontSize: 11 },
      itemGap: 12,
      tooltip: { show: true },
    },
    dataZoom: [
      { type: 'inside', xAxisIndex: 0, filterMode: 'none' },
      {
        type: 'slider',
        xAxisIndex: 0,
        height: 22,
        bottom: 36,
        borderColor: '#e2e8f0',
        fillerColor: 'rgba(79, 70, 229, 0.12)',
        handleStyle: { color: '#4f46e5' },
      },
    ],
    xAxis: {
      type: 'category',
      data: categories,
      boundaryGap: false,
      axisLine: ECHARTS_AXIS.axisLine,
      axisTick: ECHARTS_AXIS.axisTick,
      axisLabel: { ...ECHARTS_AXIS.axisLabel, rotate: categories.length > 14 ? 35 : 0 },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        ...ECHARTS_AXIS.axisLabel,
        formatter: axisValueFormatter(kpiKey),
      },
      splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } },
    },
    series,
  }
}

/** Sparkline / mini área por KPI (totales matriz). */
export function buildSparklineOption ({ periods, values, kpi, color, grain }) {
  const cat = periods.map((pk) => periodLabelShort(pk, grain))
  return {
    textStyle: ECHARTS_TEXT,
    grid: { left: 4, right: 4, top: 4, bottom: 4 },
    xAxis: {
      type: 'category',
      data: cat,
      show: false,
      boundaryGap: false,
    },
    yAxis: { type: 'value', show: false, splitLine: { show: false } },
    tooltip: {
      trigger: 'axis',
      formatter (params) {
        const p = params[0]
        if (!p) return ''
        return `<b>${p.axisValue}</b><br/>${kpi.label}: ${fmtValue(p.value, kpi.key)}`
      },
    },
    series: [
      {
        type: 'line',
        smooth: 0.3,
        symbol: 'none',
        lineStyle: { width: 2, color },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: `${color}55` },
              { offset: 1, color: `${color}05` },
            ],
          },
        },
        data: values,
      },
    ],
  }
}

/**
 * Heatmap: índices período x línea (top N), valor = KPI.
 */
export function buildHeatmapOption ({
  periods,
  lineKeys,
  matrix,
  lineLabels,
  kpiKey,
  grain,
}) {
  const data = []
  let min = Infinity
  let max = -Infinity
  for (let j = 0; j < lineKeys.length; j++) {
    for (let i = 0; i < periods.length; i++) {
      const v = matrix[j][i]
      if (v != null && !Number.isNaN(v)) {
        data.push([i, j, v])
        min = Math.min(min, v)
        max = Math.max(max, v)
      }
    }
  }
  if (!data.length) {
    return {
      title: {
        text: 'Sin datos para heatmap',
        left: 'center',
        top: 'middle',
        textStyle: { color: '#94a3b8', fontSize: 13 },
      },
    }
  }
  if (min === max) {
    max = min + 1e-9
  }

  return {
    textStyle: ECHARTS_TEXT,
    tooltip: {
      position: 'top',
      formatter (p) {
        const [xi, yi, val] = p.data
        const period = periods[xi]
        const line = lineLabels[yi]
        return `${periodLabelShort(period, grain)}<br/>${line}<br/><b>${fmtValue(val, kpiKey)}</b>`
      },
    },
    grid: { left: '26%', right: 52, top: 28, bottom: 56, containLabel: true },
    xAxis: {
      type: 'category',
      data: periods.map((pk) => periodLabelShort(pk, grain)),
      splitArea: { show: true },
      axisLabel: { rotate: periods.length > 12 ? 40 : 0, fontSize: 10, color: '#64748b' },
    },
    yAxis: {
      type: 'category',
      data: lineLabels,
      splitArea: { show: true },
      axisLabel: {
        fontSize: 10,
        color: '#334155',
        lineHeight: 14,
        formatter (value) {
          if (typeof value !== 'string') return value
          return value.includes(' · ') ? value.split(' · ').join('\n') : value
        },
      },
    },
    visualMap: {
      min,
      max,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 4,
      inRange: {
        color: ['#f8fafc', '#a5b4fc', '#312e81'],
      },
      textStyle: { color: '#64748b', fontSize: 11 },
    },
    series: [
      {
        name: kpiKey,
        type: 'heatmap',
        data,
        label: { show: false },
        emphasis: {
          itemStyle: { shadowBlur: 6, shadowColor: 'rgba(79,70,229,0.35)' },
        },
      },
    ],
  }
}

/** Barras horizontales: composición por tajada en el último período con datos. */
export function buildCompositionBarOption ({ labels, values }) {
  return {
    textStyle: ECHARTS_TEXT,
    grid: { left: 8, right: 24, top: 16, bottom: 8, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter (params) {
        const p = params[0]
        return `${p.name}<br/>Viajes: <b>${Number(p.value).toLocaleString()}</b>`
      },
    },
    xAxis: {
      type: 'value',
      axisLabel: { formatter: (v) => Number(v).toLocaleString() },
      splitLine: ECHARTS_AXIS.splitLine,
    },
    yAxis: {
      type: 'category',
      data: labels,
      axisLabel: {
        fontSize: 10,
        color: '#334155',
        formatter (value) {
          if (typeof value !== 'string') return value
          return value.length > 48 ? `${value.slice(0, 46)}…` : value
        },
      },
      inverse: true,
    },
    series: [
      {
        type: 'bar',
        data: values,
        barMaxWidth: 28,
        barCategoryGap: '28%',
        label: {
          show: true,
          position: 'right',
          distance: 6,
          fontSize: 10,
          color: '#475569',
          formatter: (p) => (p.value != null ? Number(p.value).toLocaleString() : ''),
        },
        itemStyle: {
          borderRadius: [0, 4, 4, 0],
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 1,
            y2: 0,
            colorStops: [
              { offset: 0, color: '#6366f1' },
              { offset: 1, color: '#4f46e5' },
            ],
          },
        },
      },
    ],
  }
}

/**
 * Total actual vs totales de período de comparación (meta backend), mismo KPI.
 */
export function buildActualVsComparisonLineOption ({
  periods,
  actualValues,
  comparisonValues,
  kpiKey,
  kpiLabel,
  subtext,
  grain,
}) {
  const hasActual = actualValues.some((v) => v != null && !Number.isNaN(v))
  const hasCmp = comparisonValues.some((v) => v != null && !Number.isNaN(v))
  if (!hasActual && !hasCmp) return null

  const categories = periods.map((pk) => periodLabelShort(pk, grain))
  return {
    color: [ECHARTS_COLORS[0], '#94a3b8'],
    textStyle: ECHARTS_TEXT,
    title: {
      text: kpiLabel || 'Actual vs comparación',
      subtext: subtext || '',
      left: 12,
      top: 6,
      textStyle: { color: '#0f172a', fontSize: 14, fontWeight: 600 },
      subtextStyle: { color: '#64748b', fontSize: 11 },
    },
    grid: { left: 56, right: 24, top: 72, bottom: 72, containLabel: false },
    tooltip: {
      trigger: 'axis',
      formatter (params) {
        if (!params?.length) return ''
        const head = params[0].axisValueLabel || params[0].name
        let html = `<div style="font-weight:600;margin-bottom:6px">${head}</div>`
        for (const p of params) {
          const v = fmtValue(p.value, kpiKey)
          html += `<div style="margin-top:4px"><span style="display:inline-block;margin-right:6px;border-radius:50%;width:8px;height:8px;background:${p.color}"></span>${p.seriesName}: <b>${v}</b></div>`
        }
        return html
      },
    },
    legend: { bottom: 8, left: 'center', textStyle: { fontSize: 11 }, tooltip: { show: true } },
    xAxis: {
      type: 'category',
      data: categories,
      boundaryGap: false,
      axisLine: ECHARTS_AXIS.axisLine,
      axisLabel: { ...ECHARTS_AXIS.axisLabel, rotate: categories.length > 14 ? 35 : 0 },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { ...ECHARTS_AXIS.axisLabel, formatter: axisValueFormatter(kpiKey) },
      splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } },
    },
    series: [
      {
        name: 'Actual (total)',
        type: 'line',
        smooth: 0.35,
        showSymbol: true,
        symbolSize: 5,
        lineStyle: { width: 2.5 },
        data: actualValues,
      },
      {
        name: 'Comparación (baseline)',
        type: 'line',
        smooth: 0.35,
        showSymbol: true,
        symbolSize: 4,
        lineStyle: { width: 2, type: 'dashed' },
        data: comparisonValues,
      },
    ],
  }
}

/** Viajes unmapped por período (meta), si existe. */
export function buildUnmappedTripsLineOption ({ periods, values, grain, subtext }) {
  const has = values.some((v) => v != null && v > 0)
  if (!has) return null
  const categories = periods.map((pk) => periodLabelShort(pk, grain))
  return {
    color: ['#f59e0b'],
    textStyle: ECHARTS_TEXT,
    title: {
      text: 'Viajes no mapeados (unmapped)',
      subtext: subtext || '',
      left: 12,
      top: 6,
      textStyle: { color: '#0f172a', fontSize: 13, fontWeight: 600 },
      subtextStyle: { color: '#64748b', fontSize: 11 },
    },
    grid: { left: 48, right: 20, top: 64, bottom: 48 },
    tooltip: {
      trigger: 'axis',
      formatter (params) {
        const p = params[0]
        if (!p) return ''
        return `${p.axisValue}<br/>Unmapped: <b>${Number(p.value).toLocaleString()}</b> viajes`
      },
    },
    xAxis: {
      type: 'category',
      data: categories,
      boundaryGap: false,
      axisLabel: { fontSize: 10, color: '#64748b' },
    },
    yAxis: {
      type: 'value',
      axisLabel: { fontSize: 10, formatter: (v) => Number(v).toLocaleString() },
      splitLine: ECHARTS_AXIS.splitLine,
    },
    series: [
      {
        name: 'Unmapped',
        type: 'line',
        smooth: 0.3,
        areaStyle: { opacity: 0.12, color: '#f59e0b' },
        data: values,
      },
    ],
  }
}

/** Barras: viajes por ciudad (último período). */
export function buildCityTripsBarOption ({ labels, values, subtext }) {
  if (!labels.length) return null
  return {
    textStyle: ECHARTS_TEXT,
    title: {
      text: 'Viajes por ciudad — último período',
      subtext: subtext || '',
      left: 12,
      top: 6,
      textStyle: { color: '#0f172a', fontSize: 13, fontWeight: 600 },
      subtextStyle: { color: '#64748b', fontSize: 11 },
    },
    grid: { left: 8, right: 88, top: 56, bottom: 8, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter (params) {
        const p = params[0]
        return `${p.name}<br/>Viajes: <b>${Number(p.value).toLocaleString()}</b>`
      },
    },
    xAxis: {
      type: 'value',
      axisLabel: { formatter: (v) => Number(v).toLocaleString() },
      splitLine: ECHARTS_AXIS.splitLine,
    },
    yAxis: {
      type: 'category',
      data: labels,
      inverse: true,
      axisLabel: { fontSize: 10, color: '#334155' },
    },
    series: [
      {
        type: 'bar',
        data: values,
        barMaxWidth: 26,
        label: {
          show: true,
          position: 'right',
          fontSize: 10,
          formatter: (p) => (p.value != null ? Number(p.value).toLocaleString() : ''),
        },
        itemStyle: {
          borderRadius: [0, 4, 4, 0],
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 1, y2: 0,
            colorStops: [
              { offset: 0, color: '#0d9488' },
              { offset: 1, color: '#059669' },
            ],
          },
        },
      },
    ],
  }
}
