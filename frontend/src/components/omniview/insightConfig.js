/**
 * insightConfig.js — INSIGHT_CONFIG único: thresholds, pesos, reglas, copy de transparencia.
 * El motor solo consume `INSIGHT_CONFIG` (o un merge runtime); no duplicar números fuera de aquí.
 */

// ═══════════════════════════════════════════════════════════════════════════════
// Objeto principal exportado
// ═══════════════════════════════════════════════════════════════════════════════

export const INSIGHT_CONFIG = {
  metrics: {
    revenue_yego_net: {
      direction: 'down_is_bad',
      warningPct: -0.05,
      criticalPct: -0.10,
      label: 'Revenue',
    },
    trips_completed: {
      direction: 'down_is_bad',
      warningPct: -0.10,
      criticalPct: -0.20,
      label: 'Viajes',
    },
    active_drivers: {
      direction: 'down_is_bad',
      warningPct: -0.10,
      criticalPct: -0.20,
      label: 'Conductores',
    },
    avg_ticket: {
      direction: 'down_is_bad',
      warningPct: -0.05,
      criticalPct: -0.10,
      label: 'Ticket',
    },
    cancel_rate_pct: {
      direction: 'up_is_bad',
      warningPp: 3,
      criticalPp: 5,
      label: 'Cancel rate',
    },
  },

  /** Multiplicador aplicado a umbrales según grano (mayor = más exigente, menos alertas en daily ruidoso). */
  grainThresholdMultipliers: {
    monthly: 1.0,
    weekly: 1.3,
    daily: 1.8,
  },

  /** Multiplicador adicional para periodos parciales (PARTIAL/CURRENT_DAY). Se aplica sobre grainMult. */
  partialPeriodThresholdMultiplier: 1.5,

  impactWeights: {
    revenue_yego_net: 0.6,
    trips_completed: 0.3,
    active_drivers: 0.1,
  },

  rootCauseThresholds: {
    drivers_drop_pct: -0.05,
    ticket_drop_pct: -0.03,
    trips_drop_pct: -0.05,
    cancel_up_pp: 200,
  },

  causes: {
    supply_drop: {
      label: 'Caída de supply (conductores)',
      action: 'Reactivar conductores inactivos en la zona',
      priority: 'high',
    },
    ticket_drop: {
      label: 'Caída de ticket medio',
      action: 'Revisar pricing y promociones activas',
      priority: 'high',
    },
    demand_drop: {
      label: 'Caída de demanda (viajes)',
      action: 'Revisar canales de demanda y campañas de marketing',
      priority: 'medium',
    },
    ops_issues: {
      label: 'Problemas operativos / matching',
      action: 'Auditar matching, tiempos de espera y zonas calientes',
      priority: 'high',
    },
    combined: {
      label: 'Múltiples factores',
      action: 'Análisis profundo requerido: múltiples factores afectados',
      priority: 'medium',
    },
  },

  defaultAction: {
    action: 'Revisar detalles en inspector',
    priority: 'low',
  },

  rootCauseRules: [
    { id: 'ops_issues', match: (flags, trigger) => trigger === 'cancel_rate_pct' || flags.cancelUp },
    { id: 'supply_drop', match: (flags) => flags.driversDrop && !flags.ticketDrop && !flags.tripsDrop },
    { id: 'ticket_drop', match: (flags) => flags.ticketDrop && !flags.driversDrop },
    { id: 'demand_drop', match: (flags) => flags.tripsDrop && !flags.driversDrop && !flags.ticketDrop },
    { id: 'supply_drop', match: (flags) => flags.driversDrop },
    { id: 'demand_drop', match: (flags) => flags.tripsDrop },
  ],

  severityRank: { critical: 2, warning: 1, info: 0 },
  severityLabels: { critical: 'Critical', warning: 'Warning' },

  /**
   * Overrides opcionales por grano: solo campos de métrica que cambian (se fusionan sobre metrics base).
   * Ej.: daily más ruidoso → cancel más holgado; weekly cancel más sensible.
   */
  grainOverrides: {
    weekly: {
      metrics: {
        cancel_rate_pct: { warningPp: 2.5, criticalPp: 4 },
      },
    },
    daily: {
      metrics: {
        cancel_rate_pct: { warningPp: 4, criticalPp: 7 },
        revenue_yego_net: { warningPct: -0.06, criticalPct: -0.12 },
      },
    },
  },

  /** Textos de leyenda / transparencia (UI). */
  transparency: {
    critical:
      'Critical: desviación fuerte vs. el periodo anterior según umbrales definidos en configuración.',
    warning:
      'Warning: desviación moderada; conviene revisar antes de asumir causa raíz.',
    impactSummary:
      'Impacto: combinación ponderada (configurable) del valor absoluto actual y la magnitud del cambio % en revenue, viajes y conductores; sirve para ordenar prioridades, no como métrica financiera.',
    disclaimer:
      'Las causas y acciones son sugerencias por reglas heurísticas sobre deltas ya calculados; no sustituyen análisis operativo ni conclusiones definitivas.',
  },

  /** Defaults de panel (pueden sobreescribirse por localStorage en calibración ligera). */
  panelDefaults: {
    topN: 10,
  },
}
