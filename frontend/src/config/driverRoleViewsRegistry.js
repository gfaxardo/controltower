/**
 * driverRoleViewsRegistry.js — FASE H3.5
 * Role-Based Operating Views
 *
 * Define qué ve cada rol en Drivers. Controla layout, NO permisos.
 * Role view controls layout, not permissions. NO es RBAC.
 *
 * Principios:
 *  - Misma data, diferentes lentes
 *  - Un solo sistema, múltiples formas de operar
 *  - Preservar Full Capability Map accesible
 */

export const ROLES = {
  OPERATOR: 'operator',
  SUPERVISOR: 'supervisor',
  STRATEGY: 'strategy',
  ADMIN: 'admin',
}

export const ROLE_VIEWS_REGISTRY = {
  operator: {
    role: ROLES.OPERATOR,
    label: 'Operator',
    description: 'Vista enfocada para operadores de campo. ¿Qué debo hacer hoy?',
    primary_question: '¿Qué debo hacer hoy?',
    default_route: '/drivers/operator',
    sections: [
      { key: 'my_work', label: 'My Work Today', component: 'MyWorkToday' },
      { key: 'action_queues', label: 'Action Queues', component: 'DriverActionableLists' },
      { key: 'pilot', label: 'Operational Pilot', component: 'PilotWorkboard' },
    ],
    hidden_from_default: [
      'drivers_supply', 'drivers_lifecycle', 'drivers_diagnostic',
      'drivers_behavior_benchmarking', 'drivers_behavioral_alerts',
      'drivers_fleet_leakage', 'drivers_behavioral_patterns',
      'drivers_recoverability', 'drivers_operational_intelligence',
      'drivers_campaign_intelligence', 'drivers_crm_bridge',
      'drivers_campaign_effectiveness', 'drivers_operational_workflows',
      'drivers_data_foundation', 'drivers_operational_health', 'drivers_capability_governance',
    ],
    guidance: 'Revisa tus casos asignados y contacta drivers en orden de prioridad. Registra cada contacto y resultado.',
  },
  supervisor: {
    role: ROLES.SUPERVISOR,
    label: 'Supervisor',
    description: 'Vista de supervisión de equipo y campañas. ¿Cómo va mi equipo?',
    primary_question: '¿Cómo va mi equipo y qué está trabado?',
    default_route: '/drivers/supervisor',
    sections: [
      { key: 'execution_overview', label: 'Execution Overview', component: 'ExecutionOverview' },
      { key: 'action_queues', label: 'Action Queues', component: 'DriverActionableLists' },
      { key: 'campaign_intel', label: 'Campaign Progress', component: 'CampaignProgress' },
      { key: 'crm_bridge', label: 'CRM Sync', component: 'CrmBridge' },
      { key: 'pilot', label: 'Operational Pilot', component: 'PilotWorkboard' },
    ],
    hidden_from_default: [
      'drivers_supply', 'drivers_lifecycle', 'drivers_diagnostic',
      'drivers_behavior_benchmarking', 'drivers_behavioral_alerts',
      'drivers_fleet_leakage', 'drivers_behavioral_patterns',
      'drivers_recoverability', 'drivers_operational_intelligence',
      'drivers_campaign_effectiveness', 'drivers_operational_workflows',
      'drivers_data_foundation', 'drivers_operational_health', 'drivers_capability_governance',
    ],
    guidance: 'Monitorea el avance de cada operador. Identifica casos bloqueados y campañas sin sync. Toma decisiones de redistribución.',
  },
  strategy: {
    role: ROLES.STRATEGY,
    label: 'Strategy',
    description: 'Vista analítica para decisiones de crecimiento. ¿Qué segmentos funcionan?',
    primary_question: '¿Qué segmentos, campañas y cohorts funcionan?',
    default_route: '/drivers/strategy',
    sections: [
      { key: 'supply', label: 'Supply Overview', component: 'SupplyView' },
      { key: 'effectiveness', label: 'Campaign Effectiveness', component: 'CampaignEffectiveness' },
      { key: 'lifecycle', label: 'Lifecycle Intelligence', component: 'StrategyLifecycle' },
      { key: 'campaign_intel', label: 'Campaign Intelligence', component: 'CampaignIntelligence' },
      { key: 'behavioral', label: 'Behavioral Intelligence', component: 'StrategyBehavioral' },
    ],
    hidden_from_default: [
      'drivers_action_queues', 'drivers_pilot',
      'drivers_operational_workflows', 'drivers_crm_bridge',
      'drivers_data_foundation', 'drivers_operational_health', 'drivers_capability_governance',
    ],
    guidance: 'Analiza efectividad de campañas, tendencias de lifecycle y patrones de comportamiento. "Observed lift", no causalidad.',
  },
  admin: {
    role: ROLES.ADMIN,
    label: 'Admin / Data',
    description: 'Vista de gobernanza y salud del sistema. ¿Puedo confiar en el sistema?',
    primary_question: '¿La data está confiable y el sistema está sano?',
    default_route: '/drivers/admin',
    sections: [
      { key: 'data_foundation', label: 'Data Foundation', component: 'DataFoundation' },
      { key: 'health', label: 'System Health', component: 'SystemHealth' },
      { key: 'governance', label: 'Capability Governance', component: 'CapabilityGovernance' },
      { key: 'supply', label: 'Supply Overview', component: 'SupplyView' },
    ],
    hidden_from_default: [
      'drivers_action_queues', 'drivers_pilot',
      'drivers_lifecycle', 'drivers_diagnostic',
      'drivers_behavior_benchmarking', 'drivers_behavioral_alerts',
      'drivers_fleet_leakage', 'drivers_behavioral_patterns',
      'drivers_recoverability', 'drivers_operational_intelligence',
      'drivers_campaign_intelligence', 'drivers_crm_bridge',
      'drivers_campaign_effectiveness', 'drivers_operational_workflows',
    ],
    guidance: 'Verifica que los datos estén frescos, las fuentes operativas y el sistema sin bloqueos. Monitorea sync health.',
  },
}

/**
 * Get role view config. Returns admin as fallback if role not found.
 */
export function getRoleView (role) {
  return ROLE_VIEWS_REGISTRY[role] || ROLE_VIEWS_REGISTRY.admin
}

/**
 * Get persisted role from localStorage. Default: supervisor.
 */
export function getPersistedRole () {
  try {
    const stored = localStorage.getItem('drivers_role_view')
    if (stored && ROLE_VIEWS_REGISTRY[stored]) return stored
  } catch { /* ignore */ }
  return ROLES.SUPERVISOR
}

/**
 * Persist role selection.
 */
export function setPersistedRole (role) {
  try {
    localStorage.setItem('drivers_role_view', role)
  } catch { /* ignore */ }
}

export default ROLE_VIEWS_REGISTRY
