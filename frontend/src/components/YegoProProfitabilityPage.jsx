import { useState, useEffect, useCallback, useRef } from 'react'
import {
  getYegoProProfitabilityOverview,
  getYegoProProfitabilityWeekly,
  getYegoProProfitabilityDaily,
  getYegoProProfitabilityDrivers,
  getYegoProProfitabilityVehicles,
  getYegoProProfitabilityShifts,
  getYegoProProfitabilityInputMapping,
  getYegoProProfitabilityQuality,
  getYegoProProfitabilityRootCause,
} from '../services/api'

const TABS = [
  { id: 'overview', label: 'Overview', fetcher: getYegoProProfitabilityOverview },
  { id: 'weekly', label: 'Weekly Closed', fetcher: getYegoProProfitabilityWeekly },
  { id: 'daily', label: 'Last Closed Day', fetcher: getYegoProProfitabilityDaily },
  { id: 'drivers', label: 'Drivers', fetcher: getYegoProProfitabilityDrivers },
  { id: 'vehicles', label: 'Vehicles', fetcher: getYegoProProfitabilityVehicles },
  { id: 'shifts', label: 'Shifts', fetcher: getYegoProProfitabilityShifts },
  { id: 'waterfall', label: 'Waterfall', fetcher: getYegoProProfitabilityInputMapping },
  { id: 'quality', label: 'Data Quality', fetcher: getYegoProProfitabilityQuality },
  { id: 'coverage', label: 'Coverage Audit', fetcher: null },
]

const EMPTY_STATES = {
  overview: 'No hay datos de resumen disponibles para este periodo. Fuente financiera pendiente.',
  weekly: 'No hay semanas cerradas disponibles. Data operativa disponible, data financiera parcial.',
  daily: 'No hay datos del ultimo dia cerrado. Fuente financiera pendiente.',
  drivers: 'No hay datos de conductores disponibles. Data operativa disponible, data financiera parcial.',
  vehicles: 'No hay datos de vehiculos disponibles. Fuente financiera pendiente.',
  shifts: 'No hay datos de turnos disponibles. Data operativa disponible, data financiera parcial.',
  waterfall: 'No hay datos de waterfall disponibles. Fuente financiera pendiente.',
  coverage: 'No hay datos de coverage disponibles. Verifica que el endpoint overview este respondiendo.',
}

const HUMAN_GUIDES = {
  overview: {
    title: 'Rentabilidad general de Yego Pro',
    what: 'Aqui ves si Yego Pro gana o pierde dinero. Los KPIs comparan la semana cerrada contra la ultima facturacion disponible.',
    how: 'Mira la utilidad neta semanal primero. Si es roja, revisa la seccion "Donde se va el dinero?" y "Hallazgos observados". Los conductores/vehiculos en perdida senalan donde actuar.',
    decision: 'Te permite decidir si la operacion es sostenible y si necesitas ajustar esquemas de pago, vehiculos operativos o niveles de servicio.',
    next: 'Si hay perdidas, ve a las tabs Drivers o Vehicles para identificar quien destruye margen.',
    warning: 'Solo 1 semana de billing disponible. No tomes decisiones fuertes de sustentabilidad sin mas semanas cerradas.',
  },
  weekly: {
    title: 'Historico semanal cerrado',
    what: 'Cada fila representa una semana cerrada de facturacion. Muestra ingresos, costos, utilidad y margen semana a semana.',
    how: 'Compara la utilidad entre semanas. Si esta bajando, revisa si esta subiendo algun costo (combustible, mantenimiento) o si bajo el revenue. La tendencia importa mas que una semana.',
    decision: 'Te muestra si la operacion esta mejorando o empeorando semana a semana.',
    next: 'Si ves una semana atipica, ve a Drivers para revisar que conductores causaron la desviacion.',
    warning: 'Billing actualmente tiene solo 1 semana. Cuando haya 4+, podras ver tendencias.',
  },
  daily: {
    title: 'Produccion operativa diaria',
    what: 'Cada fila es un dia de operacion con viajes completados, cancelados, revenue y turnos dia/noche. Sin data financiera de costos.',
    how: 'Revisa dias con baja produccion o alta cancelacion. Identifica patrones (ej. domingos bajos, sabados altos). Compara revenue dia vs noche.',
    decision: 'Te ayuda a entender dias de alta y baja demanda para ajustar turnos o disponibilidad.',
    next: 'Si ves baja produccion en ciertos dias, ajusta la asignacion de conductores.',
    warning: 'Data operativa solo. No incluye costos. Para rentabilidad, usa Weekly Closed.',
  },
  drivers: {
    title: 'Rentabilidad por conductor',
    what: 'Cada fila es un conductor con su produccion, revenue, payout y utilidad en la semana cerrada. Ordenado por mayor perdida primero.',
    how: 'Aqui detectas conductores que destruyen margen. Mira la columna "Utilidad / Perdida". Los que estan en rojo no cubren sus costos.',
    decision: 'Te permite identificar que conductores necesitan mas volumen de viajes o un ajuste de payout.',
    next: 'Si un conductor pierde dinero, revisa sus viajes, horas trabajadas y payout % para entender por que.',
    warning: 'El payout del conductor se toma del billing semanal. Si el conductor no tiene billing, no aparecera aqui.',
  },
  vehicles: {
    title: 'Estructura de flota y cuotas',
    what: 'Muestra la configuracion de vehiculos activos con sus cuotas semanales y esquemas de bono.',
    how: 'Revisa la estructura de cuotas contra la produccion esperada de cada vehiculo. Si la cuota excede lo que el vehiculo produce, esta en riesgo de perdida.',
    decision: 'Te permite evaluar si la configuracion de la flota (cuotas, bonos, viajes minimos) es adecuada.',
    next: 'Compara las cuotas semanales contra el revenue por vehiculo en Utilizacion.',
    warning: 'No hay asignacion vehiculo-conductor. La rentabilidad por vehiculo es estimada.',
  },
  shifts: {
    title: 'Produccion por turno (dia/noche)',
    what: 'Muestra la diferencia de produccion entre turnos diurnos y nocturnos. Revenue, viajes, km por turno.',
    how: 'Si la noche produce igual o mas que el dia, la flota tiene potencial subutilizado. Si la noche produce muy poco, concentra la operacion en el dia.',
    decision: 'Te permite decidir si vale la pena operar turnos nocturnos o concentrarse en horario diurno.',
    next: 'Si la brecha es significativa (>20%), ajusta la asignacion de turnos.',
    warning: 'Turnos usando fuente nativa module_calculated_shifts. La cobertura de placa puede variar.',
  },
  waterfall: {
    title: 'Estructura de costos e ingresos',
    what: 'Muestra el desglose completo de ingresos y costos: ticket promedio, comision plataforma, combustible, mantenimiento, payout conductor, cuota vehiculo, bonos. Cada fila tiene fuente y confianza.',
    how: 'Revisa cuales costos dominan. Si el payout es alto (>40% del revenue), considera ajustar el % de pago. Si los costos fijos dominan, revisa la configuracion de flota.',
    decision: 'Te permite ver la estructura completa del P&L y donde estan las fugas de dinero.',
    next: 'Si detectas un costo desproporcionado, revisa la fuente y confianza de ese dato en Data Quality.',
    warning: 'El waterfall es una vista consolidada. Algunos inputs son SUPUESTOS (no mediciones reales).',
  },
  quality: {
    title: 'Calidad y cobertura de datos',
    what: 'Verifica que todas las fuentes de datos esten disponibles, actualizadas y con cobertura suficiente. Muestra MV status, freshness y warnings de cobertura.',
    how: 'Revisa los warnings primero. Si hay fuentes MISSING o EMPTY, la rentabilidad calculada esta incompleta. El estado general te dice si los datos son confiables.',
    decision: 'Si faltan fuentes, no tomes decisiones fuertes. Los datos parciales pueden enganar.',
    next: 'Si hay fuentes pendientes, espera mas semanas de billing o coordina para que se registren los cierres pendientes.',
    warning: 'Si la cobertura de cierres o billing es baja, cualquier analisis financiero es parcial. No simules escenarios con datos incompletos.',
  },
  coverage: {
    title: 'Auditoria de registro operativo',
    what: 'Aqui verificas si el equipo esta registrando correctamente produccion, cierres y billing. Cada barra muestra el % de cobertura actual.',
    how: 'Mira los semaforos: verde (>90%) = confiable, amarillo (70-89%) = incompleto, rojo (<70%) = insuficiente. Si hay rojos, la data no es suficiente para tomar decisiones.',
    decision: 'Te indica si la data operativa es suficientemente completa para auditar la operacion con confianza.',
    next: 'Si hay gaps, coordina con el equipo de operacion para mejorar el registro de cierres, asignar placas a turnos o esperar mas semanas de billing.',
    warning: 'Sin cobertura suficiente, las metricas de rentabilidad son parciales. No simules escenarios hasta tener cobertura completa.',
  },
}

const COLUMN_LABELS = {
  driver_id: 'ID Conductor', driver_name: 'Conductor', vehicle_id: 'ID Vehiculo',
  vehicle_plate: 'Placa', vehicle_name: 'Vehiculo', profit: 'Utilidad / Perdida',
  loss: 'Perdida', revenue: 'Ingreso', cost: 'Costo', margin: 'Margen',
  margin_pct: 'Margen %', trips: 'Viajes', hours: 'Horas', week: 'Semana',
  date: 'Fecha', day: 'Dia', shift: 'Turno', shift_type: 'Tipo Turno',
  period: 'Periodo', country: 'Pais', city: 'Ciudad', status: 'Estado',
  source: 'Fuente', confidence: 'Confianza', observation: 'Observacion',
  input: 'Input', category: 'Categoria', value: 'Valor', type: 'Tipo',
  name: 'Nombre', label: 'Etiqueta', amount: 'Monto', total: 'Total',
  net: 'Neto', gross: 'Bruto', billing: 'Facturacion', fuel: 'Combustible',
  maintenance: 'Mantenimiento', insurance: 'Seguro', depreciation: 'Depreciacion',
  total_cost: 'Costo Total', total_revenue: 'Ingreso Total', net_profit: 'Utilidad Neta',
  result: 'Resultado', missing_source: 'Fuente pendiente', payout: 'Payout Conductor',
  contribution: 'Contribucion', net_effect: 'Efecto Neto', km: 'Km',
  km_empty: 'Km Vacio', revenue_per_hour: 'Ingreso/Hora', trips_per_driver: 'Viajes/Conductor',
  revenue_per_driver: 'Ingreso/Conductor', revenue_per_vehicle: 'Ingreso/Vehiculo',
  trips_per_vehicle: 'Viajes/Vehiculo', km_per_trip: 'Km/Viaje',
  fixed_costs: 'Costos Fijos', other: 'Otros',
}

const SOURCE_TYPE_LABELS = {
  REAL: 'Real', DERIVED: 'Derivado', ASSUMPTION: 'Supuesto', NOT_AVAILABLE: 'No disponible',
  real: 'Real', derived: 'Derivado', assumption: 'Supuesto', not_available: 'No disponible',
}

const SOURCE_TYPE_COLORS = {
  REAL: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  DERIVED: 'bg-blue-50 text-blue-700 border-blue-200',
  ASSUMPTION: 'bg-amber-50 text-amber-700 border-amber-200',
  NOT_AVAILABLE: 'bg-gray-100 text-gray-500 border-gray-200',
  real: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  derived: 'bg-blue-50 text-blue-700 border-blue-200',
  assumption: 'bg-amber-50 text-amber-700 border-amber-200',
  not_available: 'bg-gray-100 text-gray-500 border-gray-200',
}

const SHIFT_LABELS = {
  day: 'Dia', night: 'Noche', morning: 'Manana', afternoon: 'Tarde',
  evening: 'Noche', dia: 'Dia', noche: 'Noche', manana: 'Manana', tarde: 'Tarde',
}

function safeVal (v) {
  if (v === null || v === undefined || v === '') return null
  if (typeof v === 'number' && isNaN(v)) return null
  if (typeof v === 'string' && (v === 'null' || v === 'undefined' || v === 'NaN' || v === 'None')) return null
  return v
}

function num (v) { const s = safeVal(v); return typeof s === 'number' ? s : null }

function fmt (v, type = 'number') {
  const safe = safeVal(v)
  if (safe === null) return 'No disponible'
  if (type === 'currency') return typeof safe === 'number' ? `S/ ${safe.toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : String(safe)
  if (type === 'pct') return typeof safe === 'number' ? `${(safe * 100).toFixed(1)}%` : String(safe)
  if (type === 'number') return typeof safe === 'number' ? safe.toLocaleString('es-PE') : String(safe)
  if (type === 'date') return fmtDate(safe)
  return String(safe)
}

function fmtDate (v) {
  if (!v) return 'No disponible'
  try { const d = new Date(v); if (isNaN(d.getTime())) return String(v); return d.toLocaleDateString('es-PE', { year: 'numeric', month: 'short', day: 'numeric' }) } catch { return String(v) }
}

function fmtCellValue (value, colKey) {
  const safe = safeVal(value)
  if (safe === null) return 'No disponible'
  if (typeof safe === 'number') {
    const moneyKeys = ['profit', 'loss', 'revenue', 'cost', 'margin', 'amount', 'total', 'net', 'gross', 'billing', 'fuel', 'maintenance', 'insurance', 'depreciation', 'total_cost', 'total_revenue', 'net_profit', 'value', 'payout', 'contribution', 'net_effect', 'fixed_costs']
    const pctKeys = ['margin_pct', 'pct', 'rate', 'share']
    if (moneyKeys.some((k) => colKey.includes(k))) return fmt(safe, 'currency')
    if (pctKeys.some((k) => colKey.includes(k))) return fmt(safe, 'pct')
    return fmt(safe, 'number')
  }
  if (['date', 'day', 'week', 'period', 'fecha'].some((k) => colKey.includes(k)) && typeof safe === 'string' && /^\d{4}-\d{2}/.test(safe)) return fmtDate(safe)
  if (colKey === 'shift' || colKey === 'shift_type') return SHIFT_LABELS[String(safe).toLowerCase()] || String(safe)
  return String(safe)
}

function colLabel (key) { return COLUMN_LABELS[key] || key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) }

function extractRows (data) { return data?.rows || data?.data || (Array.isArray(data) ? data : []) }

function extractNum (obj, ...keys) { for (const k of keys) { const v = num(obj?.[k]); if (v !== null) return v } return null }

function sortRows (rows, tabId) {
  if (!rows || rows.length === 0) return rows
  const sorted = [...rows]
  const profitKey = (row) => { for (const k of ['profit', 'net_profit', 'margin', 'result']) { if (typeof row[k] === 'number') return row[k] } return 0 }
  const dateKey = (row) => { for (const k of ['week', 'date', 'day', 'period', 'fecha']) { if (row[k]) return String(row[k]) } return '' }
  switch (tabId) {
    case 'drivers': case 'vehicles': return sorted.sort((a, b) => profitKey(a) - profitKey(b))
    case 'weekly': case 'daily': return sorted.sort((a, b) => dateKey(b).localeCompare(dateKey(a)))
    default: return sorted
  }
}

function signalColor (v) {
  if (v === null || v === undefined) return 'text-ct-text3'
  if (typeof v !== 'number') return 'text-ct-text'
  if (v < 0) return 'text-red-600'
  if (v === 0) return 'text-amber-600'
  return 'text-emerald-600'
}

function signalBg (v) {
  if (v === null || v === undefined) return 'border-ct-border'
  if (typeof v !== 'number') return 'border-ct-border'
  if (v < 0) return 'border-red-200 bg-red-50/30'
  if (v === 0) return 'border-amber-200 bg-amber-50/30'
  return 'border-emerald-200 bg-emerald-50/30'
}

function SourceBadge ({ source, confidence }) {
  if (!source && !confidence) return null
  return (
    <span className="inline-flex items-center gap-1 text-[10px] text-gray-400 ml-1">
      {source && <span className="bg-gray-100 px-1 rounded">{SOURCE_TYPE_LABELS[source] || source}</span>}
      {confidence && <span className="bg-blue-50 text-blue-500 px-1 rounded">{confidence}</span>}
    </span>
  )
}

function MissingSourceNotice ({ field }) {
  return <span className="text-[10px] text-amber-500 bg-amber-50 px-1.5 py-0.5 rounded">{field ? `${colLabel(field)}: fuente financiera pendiente` : 'Fuente financiera pendiente'}</span>
}

function EmptyState ({ tabId }) {
  return (
    <div className="bg-ct-card rounded-lg border border-ct-border p-6 text-center">
      <div className="text-sm text-ct-text3 mb-1">{EMPTY_STATES[tabId] || 'No hay datos disponibles para este periodo.'}</div>
      <div className="text-[10px] text-ct-text3 mt-2">Si esperas datos aqui, verifica el estado de las fuentes en la tab Data Quality.</div>
    </div>
  )
}

function ShiftIcon ({ type }) {
  if (!type) return null
  const t = String(type).toLowerCase()
  if (['day', 'dia', 'morning', 'manana', 'afternoon', 'tarde'].includes(t)) return <span className="ml-1 text-amber-400 text-[10px]" title="Turno diurno">&#9728;</span>
  if (['night', 'noche', 'evening'].includes(t)) return <span className="ml-1 text-indigo-400 text-[10px]" title="Turno nocturno">&#9790;</span>
  return null
}

function SectionTitle ({ children }) {
  return <h2 className="text-sm font-semibold text-ct-text mt-1">{children}</h2>
}

function GuideBlock ({ tabId }) {
  const [open, setOpen] = useState(false)
  const guide = HUMAN_GUIDES[tabId]
  if (!guide) return null
  return (
    <div className="bg-blue-50/50 border border-blue-200 rounded-lg overflow-hidden">
      <button type="button" onClick={() => setOpen(!open)}
        className="w-full px-3 py-2 flex items-center justify-between text-xs text-blue-800 hover:bg-blue-50 transition-colors">
        <span className="font-medium">Guia: {guide.title}</span>
        <span className="text-[10px] text-blue-500">{open ? 'Ocultar' : 'Leer guia'}</span>
      </button>
      {open && (
        <div className="px-3 pb-3 space-y-2 text-[11px] text-blue-800">
          <div><span className="font-medium">Que es:</span> {guide.what}</div>
          <div><span className="font-medium">Como usarlo:</span> {guide.how}</div>
          <div><span className="font-medium">Que decision permite tomar:</span> {guide.decision}</div>
          <div><span className="font-medium">Siguiente paso:</span> {guide.next}</div>
          {guide.warning && <div className="text-amber-700 bg-amber-50 px-2 py-1 rounded border border-amber-200"><span className="font-medium">Advertencia:</span> {guide.warning}</div>}
        </div>
      )}
    </div>
  )
}

function CoverageAuditPanel ({ diagData }) {
  const cov = diagData?.overview?.source_coverage || diagData?.quality?.source_coverage || {}
  const qw = diagData?.quality?.warnings || []
  const rc = diagData?.rootCause || {}
  if (!cov.billing_weeks && !cov.shift_days && !rc.plate_coverage) return <EmptyState tabId="coverage" />

  function pctColor (v) {
    if (v == null) return 'bg-gray-100 text-gray-400'
    if (v >= 90) return 'bg-emerald-100 text-emerald-700'
    if (v >= 70) return 'bg-amber-100 text-amber-700'
    return 'bg-red-100 text-red-700'
  }

  function weekColor (w) {
    if (w == null) return 'bg-gray-100 text-gray-400'
    if (w >= 4) return 'bg-emerald-100 text-emerald-700'
    if (w >= 2) return 'bg-amber-100 text-amber-700'
    return 'bg-red-100 text-red-700'
  }

  function semaforo (label, value, suffix = '%', colorFn = pctColor) {
    return (
      <div className="bg-ct-card rounded-lg border border-ct-border p-3">
        <div className="text-[10px] text-ct-text3 mb-1">{label}</div>
        <div className="text-lg font-bold text-ct-text">{value != null ? `${value}${suffix}` : 'N/D'}</div>
        <div className={`inline-block text-[10px] px-1.5 py-0.5 rounded font-medium mt-1 ${colorFn(value)}`}>
          {value == null ? 'Sin datos' :
           suffix === '%' ? (value >= 90 ? 'Suficiente' : value >= 70 ? 'Parcial' : 'Insuficiente') :
           (value >= 4 ? 'Suficiente' : value >= 2 ? 'Parcial' : 'Insuficiente')}
        </div>
      </div>
    )
  }

  const auditMessages = []
  const closeCov = cov.close_driver_coverage_pct
  const plateCov = cov.plate_coverage_pct
  const billWeeks = cov.billing_weeks
  const shiftDays = cov.shift_days

  if (closeCov != null && closeCov < 80) {
    auditMessages.push({ text: 'Cobertura de liquidaciones insuficiente (' + closeCov + '%). Puede indicar cierres no registrados o proceso incompleto.', severity: 'medium' })
  }
  if (plateCov != null && plateCov < 80) {
    auditMessages.push({ text: 'La relacion vehiculo-conductor es parcial (' + plateCov + '%). La rentabilidad por vehiculo puede estar incompleta.', severity: 'medium' })
  }
  if (billWeeks != null && billWeeks < 4) {
    auditMessages.push({ text: 'No hay suficiente historico financiero para simular esquemas de pago con confianza. Solo ' + billWeeks + ' semana(s) disponible(s).', severity: 'high' })
  }
  if (shiftDays != null && shiftDays > 7 && (closeCov == null || closeCov < 80)) {
    auditMessages.push({ text: 'Hay produccion registrada (' + shiftDays + ' dias de shifts), pero no todos los cierres estan siendo capturados.', severity: 'medium' })
  }

  const gaps = []
  if (closeCov != null && closeCov < 100) {
    gaps.push({ label: 'Produccion sin cierre', value: closeCov < 50 ? 'Significativo' : 'Parcial', detail: 'Cobertura de cierres: ' + closeCov + '%' })
  }
  if (billWeeks != null && billWeeks < 4) {
    gaps.push({ label: 'Billing historico insuficiente', value: billWeeks + ' semana(s)', detail: 'Minimo 4 semanas para tendencias' })
  }
  if (plateCov != null && plateCov < 100) {
    gaps.push({ label: 'Placas sin asignar en shifts', value: plateCov < 50 ? 'Significativo' : 'Parcial', detail: 'Cobertura de placa: ' + plateCov + '%' })
  }
  gaps.push({ label: 'Cierres sin produccion', value: 'No disponible', detail: 'Revisar en Data Quality' })
  gaps.push({ label: 'Vehiculos con uso parcial', value: 'No disponible', detail: 'Sin asignacion vehiculo-conductor' })
  gaps.push({ label: 'Cierres manuales incompletos', value: 'No disponible', detail: 'Campo no expuesto en endpoint actual' })

  return (
    <div className="space-y-4">
      <GuideBlock tabId="coverage" />

      <div>
        <SectionTitle>Cobertura de fuentes</SectionTitle>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
          {semaforo('Shift days', cov.shift_days, ' dias', (v) => v != null && v >= 7 ? 'bg-emerald-100 text-emerald-700' : v != null && v >= 3 ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700')}
          {semaforo('Billing weeks', cov.billing_weeks, ' sem', weekColor)}
          {semaforo('Close driver cov.', cov.close_driver_coverage_pct)}
          {semaforo('Plate coverage', cov.plate_coverage_pct)}
          {semaforo('Trip days', cov.trip_days, ' dias', (v) => v != null && v >= 30 ? 'bg-emerald-100 text-emerald-700' : v != null && v >= 7 ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700')}
          <div className="bg-ct-card rounded-lg border border-ct-border p-3">
            <div className="text-[10px] text-ct-text3 mb-1">Registered drivers</div>
            <div className="text-lg font-bold text-ct-text">{cov.registered_drivers || 'N/D'}</div>
          </div>
        </div>
      </div>

      {gaps.length > 0 && (
        <div>
          <SectionTitle>Gaps operativos detectados</SectionTitle>
          <div className="bg-ct-card rounded-lg border border-ct-border divide-y divide-ct-border/50">
            {gaps.map((g, i) => (
              <div key={i} className="px-3 py-2 flex items-start gap-3">
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium flex-shrink-0 ${g.value === 'Significativo' ? 'bg-red-100 text-red-700' : g.value === 'Parcial' ? 'bg-amber-100 text-amber-700' : 'bg-gray-100 text-gray-500'}`}>{g.value}</span>
                <div className="flex-1">
                  <div className="text-xs font-medium text-ct-text">{g.label}</div>
                  <div className="text-[10px] text-ct-text3">{g.detail}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {auditMessages.length > 0 && (
        <div>
          <SectionTitle>Mensajes de auditoria</SectionTitle>
          <div className="space-y-1.5">
            {auditMessages.map((m, i) => {
              const sevColor = { high: 'border-l-red-500 bg-red-50/40', medium: 'border-l-amber-500 bg-amber-50/40', low: 'border-l-blue-400 bg-blue-50/40' }
              return (
                <div key={i} className={`border-l-4 rounded-r px-3 py-2 text-xs text-ct-text ${sevColor[m.severity] || sevColor.low}`}>{m.text}</div>
              )
            })}
          </div>
        </div>
      )}

      {qw.length > 0 && (
        <div>
          <SectionTitle>Warnings del backend</SectionTitle>
          <div className="space-y-1.5">
            {qw.map((w, i) => {
              const sc = { HIGH: 'bg-red-100 text-red-700 border-red-300', MEDIUM: 'bg-amber-100 text-amber-700 border-amber-300', LOW: 'bg-blue-100 text-blue-700 border-blue-300' }
              return (
                <div key={i} className={`rounded border px-3 py-1.5 text-xs flex items-center gap-2 ${sc[w.severity] || 'bg-gray-100 text-gray-600 border-gray-300'}`}>
                  <span className="text-[10px] font-semibold">{w.severity}</span>
                  <span className="flex-1">{w.message}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {rc.root_cause_summary && rc.root_cause_summary.length > 0 && (
        <div>
          <SectionTitle>Root Cause Summary</SectionTitle>
          <div className="space-y-1.5">
            {rc.root_cause_summary.map((s, i) => {
              const sevColor = { HIGH: 'border-l-red-500 bg-red-50/40', MEDIUM: 'border-l-amber-500 bg-amber-50/40', LOW: 'border-l-blue-400 bg-blue-50/40' }
              return (
                <div key={i} className={`border-l-4 rounded-r px-3 py-2 text-xs text-ct-text ${sevColor[s.severity] || sevColor.low}`}>
                  <span className="font-medium">{s.finding}</span>
                  <div className="text-[10px] text-ct-text3 mt-0.5">Impacto: {s.impact}</div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {rc.missing_driver_closes && rc.missing_driver_closes.length > 0 && (
        <div>
          <SectionTitle>Missing Driver Closes ({rc.missing_driver_closes_count || rc.missing_driver_closes.length} records)</SectionTitle>
          <div className="bg-ct-card rounded-lg border border-ct-border overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="border-b border-ct-border bg-red-50/30">
                  <th className="px-2 py-1.5 text-left font-medium text-ct-text2">Conductor</th>
                  <th className="px-2 py-1.5 text-left font-medium text-ct-text2">Fecha</th>
                  <th className="px-2 py-1.5 text-left font-medium text-ct-text2">Turno</th>
                  <th className="px-2 py-1.5 text-right font-medium text-ct-text2">Viajes</th>
                  <th className="px-2 py-1.5 text-right font-medium text-ct-text2">Revenue</th>
                  <th className="px-2 py-1.5 text-left font-medium text-ct-text2">Placa</th>
                </tr>
              </thead>
              <tbody>
                {rc.missing_driver_closes.slice(0, 30).map((r, i) => (
                  <tr key={i} className="border-b border-ct-border/50 hover:bg-ct-surface/50">
                    <td className="px-2 py-1.5 font-mono text-[10px]">{r.driver_id?.slice(0, 12)}...</td>
                    <td className="px-2 py-1.5">{r.fecha}</td>
                    <td className="px-2 py-1.5">{r.tipo_turno}</td>
                    <td className="px-2 py-1.5 text-right">{fmt(r.trips, 'number')}</td>
                    <td className="px-2 py-1.5 text-right">{fmt(r.revenue, 'currency')}</td>
                    <td className="px-2 py-1.5 text-ct-text3 text-[10px]">{r.placa || 'Sin placa'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {rc.missing_driver_closes.length > 30 && <div className="text-[10px] text-ct-text3 mt-1">Mostrando 30 de {rc.missing_driver_closes.length}</div>}
        </div>
      )}

      {rc.missing_plates && rc.missing_plates.length > 0 && (
        <div>
          <SectionTitle>Missing Plate Assignment ({rc.missing_plates_count || rc.missing_plates.length} shifts)</SectionTitle>
          <div className="bg-ct-card rounded-lg border border-ct-border overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="border-b border-ct-border bg-amber-50/50">
                  <th className="px-2 py-1.5 text-left font-medium text-ct-text2">Conductor</th>
                  <th className="px-2 py-1.5 text-left font-medium text-ct-text2">Fecha</th>
                  <th className="px-2 py-1.5 text-left font-medium text-ct-text2">Turno</th>
                  <th className="px-2 py-1.5 text-right font-medium text-ct-text2">Viajes</th>
                  <th className="px-2 py-1.5 text-right font-medium text-ct-text2">Revenue</th>
                </tr>
              </thead>
              <tbody>
                {rc.missing_plates.slice(0, 30).map((r, i) => (
                  <tr key={i} className="border-b border-ct-border/50 hover:bg-ct-surface/50">
                    <td className="px-2 py-1.5 font-mono text-[10px]">{r.driver_id?.slice(0, 12)}...</td>
                    <td className="px-2 py-1.5">{r.fecha}</td>
                    <td className="px-2 py-1.5">{r.tipo_turno}</td>
                    <td className="px-2 py-1.5 text-right">{fmt(r.trips, 'number')}</td>
                    <td className="px-2 py-1.5 text-right">{fmt(r.revenue, 'currency')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {rc.production_without_billing && rc.production_without_billing.length > 0 && (
        <div>
          <SectionTitle>Production Without Billing ({rc.production_without_billing.length} weeks)</SectionTitle>
          <div className="bg-ct-card rounded-lg border border-ct-border overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="border-b border-ct-border bg-red-50/30">
                  <th className="px-2 py-1.5 text-left font-medium text-ct-text2">Semana</th>
                  <th className="px-2 py-1.5 text-right font-medium text-ct-text2">Conductores</th>
                  <th className="px-2 py-1.5 text-right font-medium text-ct-text2">Viajes</th>
                  <th className="px-2 py-1.5 text-right font-medium text-ct-text2">Revenue</th>
                </tr>
              </thead>
              <tbody>
                {rc.production_without_billing.map((r, i) => (
                  <tr key={i} className="border-b border-ct-border/50 hover:bg-ct-surface/50">
                    <td className="px-2 py-1.5">{r.week_start}</td>
                    <td className="px-2 py-1.5 text-right">{fmt(r.drivers, 'number')}</td>
                    <td className="px-2 py-1.5 text-right">{fmt(r.trips, 'number')}</td>
                    <td className="px-2 py-1.5 text-right text-red-600 font-medium">{fmt(r.revenue, 'currency')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {rc.billing_with_support && rc.billing_with_support.length > 0 && (
        <div>
          <SectionTitle>Billing Support ({rc.billing_weeks_count || rc.billing_with_support.length} weeks)</SectionTitle>
          <div className="bg-ct-card rounded-lg border border-ct-border overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="border-b border-ct-border bg-emerald-50/50">
                  <th className="px-2 py-1.5 text-left font-medium text-ct-text2">Semana</th>
                  <th className="px-2 py-1.5 text-right font-medium text-ct-text2">Conductores</th>
                  <th className="px-2 py-1.5 text-right font-medium text-ct-text2">Viajes</th>
                  <th className="px-2 py-1.5 text-right font-medium text-ct-text2">Revenue</th>
                </tr>
              </thead>
              <tbody>
                {rc.billing_with_support.map((r, i) => (
                  <tr key={i} className="border-b border-ct-border/50 hover:bg-ct-surface/50">
                    <td className="px-2 py-1.5">{r.week_start}</td>
                    <td className="px-2 py-1.5 text-right">{fmt(r.drivers, 'number')}</td>
                    <td className="px-2 py-1.5 text-right">{fmt(r.trips, 'number')}</td>
                    <td className="px-2 py-1.5 text-right text-emerald-600 font-medium">{fmt(r.revenue, 'currency')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="bg-ct-card rounded-lg border border-ct-border p-3">
        <div className="text-xs font-medium text-ct-text mb-2">Resumen de fuentes</div>
        <div className="space-y-1 text-[11px] text-ct-text2">
          <div><strong className="text-ct-text">module_calculated_shifts</strong> = produccion diaria / turnos ({cov.shift_days || '?'} dias)</div>
          <div><strong className="text-ct-text">module_driver_closes</strong> = liquidaciones y pagos al conductor ({cov.close_days || '?'} dias)</div>
          <div><strong className="text-ct-text">module_weekly_billing</strong> = cierre financiero semanal ({cov.billing_weeks || '?'} semanas)</div>
          <div><strong className="text-ct-text">trips_2026</strong> = viajes completados ({cov.trip_days || '?'} dias)</div>
        </div>
      </div>
    </div>
  )
}

function SectionError ({ label }) {
  return <div className="text-[11px] text-ct-text3 bg-ct-surface rounded border border-ct-border px-3 py-2">Datos de {label} no disponibles en este momento.</div>
}

function DiagKpi ({ label, value, type = 'currency' }) {
  const v = num(value)
  return (
    <div className={`bg-ct-card rounded-lg border p-2.5 ${signalBg(v)}`}>
      <div className="text-[10px] text-ct-text3 mb-0.5">{label}</div>
      <div className={`text-base font-bold ${signalColor(v)}`}>{fmt(value, type)}</div>
    </div>
  )
}

function DiagCountKpi ({ label, value, total, bad }) {
  const v = num(value)
  const isBad = bad === true
  return (
    <div className={`bg-ct-card rounded-lg border p-2.5 ${isBad ? 'border-red-200 bg-red-50/30' : 'border-emerald-200 bg-emerald-50/30'}`}>
      <div className="text-[10px] text-ct-text3 mb-0.5">{label}</div>
      <div className={`text-base font-bold ${isBad ? 'text-red-600' : 'text-emerald-600'}`}>{fmt(v, 'number')}</div>
      {total != null && <div className="text-[9px] text-ct-text3">de {fmt(total, 'number')} total</div>}
    </div>
  )
}

function DiagnosticHeader ({ overview, drivers, vehicles }) {
  const ov = overview?.summary || overview?.kpis || overview || {}
  const ovFlat = Array.isArray(ov) ? Object.fromEntries(ov.map((k) => [k.key || k.label, k.value])) : ov

  const netWeekly = extractNum(ovFlat, 'net_profit_weekly', 'net_profit', 'profit', 'weekly_profit')
  const netMonthly = extractNum(ovFlat, 'net_profit_monthly', 'monthly_profit', 'estimated_monthly_profit')
  const revWeekly = extractNum(ovFlat, 'revenue_weekly', 'revenue', 'weekly_revenue')
  const revMonthly = extractNum(ovFlat, 'revenue_monthly', 'monthly_revenue', 'estimated_monthly_revenue')
  const marginPct = extractNum(ovFlat, 'margin_pct', 'margin', 'margin_percent')

  const driverRows = extractRows(drivers)
  const vehicleRows = extractRows(vehicles)
  const profitableDrivers = driverRows.filter((r) => num(r.profit ?? r.net_profit ?? r.margin) > 0).length
  const lossDrivers = driverRows.filter((r) => num(r.profit ?? r.net_profit ?? r.margin) < 0).length
  const profitableVehicles = vehicleRows.filter((r) => num(r.profit ?? r.net_profit ?? r.margin) > 0).length
  const lossVehicles = vehicleRows.filter((r) => num(r.profit ?? r.net_profit ?? r.margin) < 0).length

  const hasData = netWeekly !== null || revWeekly !== null || driverRows.length > 0 || vehicleRows.length > 0
  if (!hasData) return null

  return (
    <div className="space-y-2">
      <SectionTitle>Que esta pasando?</SectionTitle>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
        <DiagKpi label="Utilidad neta semanal" value={netWeekly} />
        <DiagKpi label="Utilidad neta mensual est." value={netMonthly} />
        <DiagKpi label="Revenue semanal" value={revWeekly} />
        <DiagKpi label="Revenue mensual est." value={revMonthly} />
        <DiagKpi label="Margen %" value={marginPct} type="pct" />
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <DiagCountKpi label="Conductores rentables" value={profitableDrivers} total={driverRows.length} />
        <DiagCountKpi label="Conductores en perdida" value={lossDrivers} total={driverRows.length} bad />
        <DiagCountKpi label="Vehiculos rentables" value={profitableVehicles} total={vehicleRows.length} />
        <DiagCountKpi label="Vehiculos en perdida" value={lossVehicles} total={vehicleRows.length} bad />
      </div>
    </div>
  )
}

function TopRankedCard ({ title, rows, isLoss }) {
  if (!rows || rows.length === 0) return null
  const profitVal = (r) => num(r.profit ?? r.net_profit ?? r.margin ?? r.result) ?? 0
  const sorted = [...rows].sort((a, b) => isLoss ? profitVal(a) - profitVal(b) : profitVal(b) - profitVal(a))
  const top5 = sorted.slice(0, 5)
  const idKey = (r) => r.vehicle_plate || r.vehicle_name || r.vehicle_id || r.driver_name || r.driver_id || r.name || r.id || '?'
  return (
    <div className="bg-ct-card rounded-lg border border-ct-border">
      <div className={`px-3 py-1.5 border-b text-xs font-semibold ${isLoss ? 'text-red-700 bg-red-50/50 border-red-100' : 'text-emerald-700 bg-emerald-50/50 border-emerald-100'}`}>{title}</div>
      <div className="divide-y divide-ct-border/50">
        {top5.map((r, i) => {
          const pv = profitVal(r)
          return (
            <div key={i} className="px-3 py-1.5 flex items-center gap-2 text-xs">
              <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${isLoss ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700'}`}>{i + 1}</span>
              <span className="flex-1 truncate font-medium text-ct-text">{idKey(r)}</span>
              <span className={`font-semibold ${pv < 0 ? 'text-red-600' : 'text-emerald-600'}`}>{fmt(pv, 'currency')}</span>
              <span className="text-ct-text3 w-16 text-right">{fmt(num(r.revenue), 'currency')}</span>
              <span className="text-ct-text3 w-10 text-right">{fmt(num(r.trips), 'number')}</span>
              <span className="text-ct-text3 w-12 text-right">{fmt(num(r.margin_pct ?? r.margin), 'pct')}</span>
            </div>
          )
        })}
      </div>
      <div className="px-3 py-1 text-[9px] text-ct-text3 flex gap-4 border-t border-ct-border/50">
        <span>Utilidad</span><span>Revenue</span><span>Viajes</span><span>Margen</span>
      </div>
    </div>
  )
}

function DriverLeaderboard ({ drivers }) {
  const rows = extractRows(drivers)
  if (rows.length === 0) return null
  return (
    <div className="space-y-2">
      <SectionTitle>Conductores: contribucion al resultado</SectionTitle>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <TopRankedCard title="TOP CONDUCTORES RENTABLES" rows={rows} isLoss={false} />
        <TopRankedCard title="TOP CONDUCTORES EN PERDIDA" rows={rows} isLoss />
      </div>
    </div>
  )
}

function LossExplanation ({ waterfall }) {
  const items = waterfall?.steps || waterfall?.items || waterfall?.rows || waterfall?.data || (Array.isArray(waterfall) ? waterfall : null)
  if (!items || items.length === 0) return null

  const costItems = items.filter((it) => {
    const v = num(it.value ?? it.amount)
    return v !== null && v !== 0
  })
  const totalAbs = costItems.reduce((s, it) => s + Math.abs(num(it.value ?? it.amount) ?? 0), 0)
  if (totalAbs === 0) return null

  const dist = costItems.map((it) => {
    const raw = num(it.value ?? it.amount) ?? 0
    const label = it.label || it.name || it.step || colLabel(it.input || 'otro')
    const pct = totalAbs > 0 ? (Math.abs(raw) / totalAbs) : 0
    return { label, value: raw, pct }
  }).sort((a, b) => b.pct - a.pct)

  return (
    <div className="space-y-2">
      <SectionTitle>Donde se va el dinero?</SectionTitle>
      <div className="bg-ct-card rounded-lg border border-ct-border p-3 space-y-1.5">
        {dist.map((d, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="text-xs text-ct-text2 w-40 truncate">{d.label}</span>
            <div className="flex-1 h-4 bg-gray-100 rounded overflow-hidden">
              <div className={`h-full rounded ${d.value < 0 ? 'bg-red-400' : 'bg-emerald-400'}`} style={{ width: `${(d.pct * 100).toFixed(0)}%` }} />
            </div>
            <span className="text-xs font-semibold w-12 text-right text-ct-text">{(d.pct * 100).toFixed(0)}%</span>
            <span className={`text-xs w-24 text-right ${d.value < 0 ? 'text-red-600' : 'text-emerald-600'}`}>{fmt(d.value, 'currency')}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function UtilizationDiagnostics ({ overview, drivers, vehicles }) {
  const ov = overview?.summary || overview?.kpis || overview || {}
  const ovFlat = Array.isArray(ov) ? Object.fromEntries(ov.map((k) => [k.key || k.label, k.value])) : ov
  const driverRows = extractRows(drivers)
  const vehicleRows = extractRows(vehicles)

  const totalDrivers = driverRows.length || num(ovFlat.total_drivers) || 0
  const totalVehicles = vehicleRows.length || num(ovFlat.total_vehicles) || 0
  const totalTrips = num(ovFlat.trips ?? ovFlat.total_trips) ?? driverRows.reduce((s, r) => s + (num(r.trips) ?? 0), 0)
  const totalRevenue = num(ovFlat.revenue ?? ovFlat.total_revenue ?? ovFlat.revenue_weekly) ?? driverRows.reduce((s, r) => s + (num(r.revenue) ?? 0), 0)
  const totalHours = num(ovFlat.hours ?? ovFlat.total_hours)
  const totalKm = num(ovFlat.km ?? ovFlat.total_km)
  const kmEmpty = num(ovFlat.km_empty ?? ovFlat.km_vacio)

  const tripsPerDriver = totalDrivers > 0 ? totalTrips / totalDrivers : null
  const revPerDriver = totalDrivers > 0 ? totalRevenue / totalDrivers : null
  const revPerVehicle = totalVehicles > 0 ? totalRevenue / totalVehicles : null
  const tripsPerVehicle = totalVehicles > 0 ? totalTrips / totalVehicles : null
  const kmPerTrip = totalTrips > 0 && totalKm ? totalKm / totalTrips : null
  const revPerHour = totalHours && totalHours > 0 ? totalRevenue / totalHours : null

  const hasData = totalTrips > 0 || totalRevenue > 0
  if (!hasData) return null

  function utilLevel (val, low, high) {
    if (val === null) return null
    if (val < low) return 'bajo'
    if (val > high) return 'alto'
    return 'medio'
  }

  const metrics = [
    { label: 'Viajes/Conductor', value: tripsPerDriver, level: utilLevel(tripsPerDriver, 5, 20), type: 'number' },
    { label: 'Ingreso/Conductor', value: revPerDriver, level: utilLevel(revPerDriver, 200, 800), type: 'currency' },
    { label: 'Ingreso/Vehiculo', value: revPerVehicle, level: utilLevel(revPerVehicle, 300, 1000), type: 'currency' },
    { label: 'Viajes/Vehiculo', value: tripsPerVehicle, level: utilLevel(tripsPerVehicle, 5, 25), type: 'number' },
    { label: 'Km/Viaje', value: kmPerTrip, level: utilLevel(kmPerTrip, 3, 15), type: 'number' },
    { label: 'Km vacio', value: kmEmpty, level: null, type: 'number' },
    { label: 'Ingreso/Hora', value: revPerHour, level: utilLevel(revPerHour, 10, 40), type: 'currency' },
  ].filter((m) => m.value !== null)

  if (metrics.length === 0) return null

  const levelColor = { bajo: 'text-red-600 bg-red-50', medio: 'text-amber-600 bg-amber-50', alto: 'text-emerald-600 bg-emerald-50' }
  const levelLabel = { bajo: 'Bajo', medio: 'Medio', alto: 'Alto' }

  return (
    <div className="space-y-2">
      <SectionTitle>Utilizacion</SectionTitle>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
        {metrics.map((m, i) => (
          <div key={i} className="bg-ct-card rounded-lg border border-ct-border p-2.5">
            <div className="text-[10px] text-ct-text3 mb-0.5">{m.label}</div>
            <div className="text-base font-bold text-ct-text">{fmt(m.value, m.type)}</div>
            {m.level && <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${levelColor[m.level]}`}>{levelLabel[m.level]}</span>}
          </div>
        ))}
      </div>
    </div>
  )
}

function ShiftDiagnostics ({ shifts }) {
  const rows = extractRows(shifts)
  if (rows.length === 0) return null

  const dayShifts = ['day', 'dia', 'morning', 'manana', 'afternoon', 'tarde']
  const nightShifts = ['night', 'noche', 'evening']
  const classifyShift = (r) => {
    const s = String(r.shift || r.shift_type || '').toLowerCase()
    if (dayShifts.includes(s)) return 'day'
    if (nightShifts.includes(s)) return 'night'
    return null
  }

  const dayRows = rows.filter((r) => classifyShift(r) === 'day')
  const nightRows = rows.filter((r) => classifyShift(r) === 'night')

  const avg = (arr, key) => {
    const vals = arr.map((r) => num(r[key])).filter((v) => v !== null)
    return vals.length > 0 ? vals.reduce((a, b) => a + b, 0) / vals.length : null
  }
  const sum = (arr, key) => {
    const vals = arr.map((r) => num(r[key])).filter((v) => v !== null)
    return vals.length > 0 ? vals.reduce((a, b) => a + b, 0) : null
  }

  const dayRev = sum(dayRows, 'revenue') ?? avg(dayRows, 'revenue')
  const nightRev = sum(nightRows, 'revenue') ?? avg(nightRows, 'revenue')
  const dayMargin = avg(dayRows, 'margin_pct') ?? avg(dayRows, 'margin')
  const nightMargin = avg(nightRows, 'margin_pct') ?? avg(nightRows, 'margin')

  const hasComparison = dayRev !== null && nightRev !== null && dayRev > 0
  const revDiffPct = hasComparison ? Math.abs(dayRev - nightRev) / Math.max(dayRev, 1) : null
  const isSignificant = revDiffPct !== null && revDiffPct > 0.20

  return (
    <div className="space-y-2">
      <SectionTitle>Diagnostico dia/noche</SectionTitle>
      <div className="bg-ct-card rounded-lg border border-ct-border p-3">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
          <div>
            <div className="text-[10px] text-ct-text3">Revenue dia <span className="text-amber-400">&#9728;</span></div>
            <div className="text-sm font-bold text-ct-text">{fmt(dayRev, 'currency')}</div>
          </div>
          <div>
            <div className="text-[10px] text-ct-text3">Revenue noche <span className="text-indigo-400">&#9790;</span></div>
            <div className="text-sm font-bold text-ct-text">{fmt(nightRev, 'currency')}</div>
          </div>
          <div>
            <div className="text-[10px] text-ct-text3">Margen dia</div>
            <div className="text-sm font-bold text-ct-text">{fmt(dayMargin, 'pct')}</div>
          </div>
          <div>
            <div className="text-[10px] text-ct-text3">Margen noche</div>
            <div className="text-sm font-bold text-ct-text">{fmt(nightMargin, 'pct')}</div>
          </div>
        </div>
        {revDiffPct !== null && (
          <div className={`text-xs px-3 py-1.5 rounded ${isSignificant ? 'bg-amber-50 text-amber-700 border border-amber-200' : 'bg-gray-50 text-ct-text2 border border-ct-border'}`}>
            Diferencia observada: {(revDiffPct * 100).toFixed(0)}% &mdash; {isSignificant ? 'La diferencia observada es significativa.' : 'La diferencia observada es moderada.'}
          </div>
        )}
      </div>
    </div>
  )
}

function KeyFindings ({ overview, drivers, vehicles, waterfall, shifts, diagData }) {
  const findings = []
  const driverRows = extractRows(drivers)
  const vehicleRows = extractRows(vehicles)

  const profitValD = (r) => num(r.profit ?? r.net_profit ?? r.margin ?? r.result)
  const profitValV = (r) => num(r.profit ?? r.net_profit ?? r.margin ?? r.result)

  if (vehicleRows.length > 0) {
    const lossV = vehicleRows.filter((r) => (profitValV(r) ?? 0) < 0).length
    const pct = lossV / vehicleRows.length
    if (pct > 0.6) findings.push({ text: `${(pct * 100).toFixed(0)}% de los vehiculos estan en perdida.`, severity: 'high' })
    else if (pct > 0.3) findings.push({ text: `${(pct * 100).toFixed(0)}% de los vehiculos estan en perdida.`, severity: 'medium' })
    else if (lossV > 0) findings.push({ text: `${lossV} vehiculo${lossV !== 1 ? 's' : ''} en perdida de ${vehicleRows.length} total.`, severity: 'low' })
  }

  if (driverRows.length > 0) {
    const lossD = driverRows.filter((r) => (profitValD(r) ?? 0) < 0).length
    const pct = lossD / driverRows.length
    if (pct > 0.5) findings.push({ text: `${(pct * 100).toFixed(0)}% de los conductores estan en perdida.`, severity: 'high' })
    else if (lossD > 0) findings.push({ text: `${lossD} conductor${lossD !== 1 ? 'es' : ''} en perdida de ${driverRows.length} total.`, severity: lossD > 3 ? 'medium' : 'low' })
  }

  const items = waterfall?.steps || waterfall?.items || waterfall?.rows || waterfall?.data || (Array.isArray(waterfall) ? waterfall : null)
  if (items && items.length > 0) {
    const totalAbs = items.reduce((s, it) => s + Math.abs(num(it.value ?? it.amount) ?? 0), 0)
    if (totalAbs > 0) {
      const payoutItem = items.find((it) => {
        const l = (it.label || it.name || it.input || '').toLowerCase()
        return l.includes('payout') || l.includes('conductor') || l.includes('driver')
      })
      if (payoutItem) {
        const pPct = Math.abs(num(payoutItem.value ?? payoutItem.amount) ?? 0) / totalAbs
        if (pPct > 0.4) findings.push({ text: `La mayor parte del costo (${(pPct * 100).toFixed(0)}%) proviene del payout a conductores.`, severity: 'medium' })
      }
    }
  }

  const ov = overview?.summary || overview?.kpis || overview || {}
  const ovFlat = Array.isArray(ov) ? Object.fromEntries(ov.map((k) => [k.key || k.label, k.value])) : ov
  const totalTrips = num(ovFlat.trips ?? ovFlat.total_trips)
  const totalD = driverRows.length || num(ovFlat.total_drivers) || 0
  if (totalTrips !== null && totalD > 0 && totalTrips / totalD < 5) {
    findings.push({ text: 'La utilizacion promedio es baja (menos de 5 viajes por conductor).', severity: 'medium' })
  }

  const shiftRows = extractRows(shifts)
  if (shiftRows.length > 0) {
    const dayShifts = ['day', 'dia', 'morning', 'manana', 'afternoon', 'tarde']
    const nightShifts = ['night', 'noche', 'evening']
    const dayR = shiftRows.filter((r) => dayShifts.includes(String(r.shift || r.shift_type || '').toLowerCase()))
    const nightR = shiftRows.filter((r) => nightShifts.includes(String(r.shift || r.shift_type || '').toLowerCase()))
    const sumRev = (arr) => arr.reduce((s, r) => s + (num(r.revenue) ?? 0), 0)
    const dR = sumRev(dayR); const nR = sumRev(nightR)
    if (dR > 0 && nR > 0) {
      const diff = Math.abs(dR - nR) / Math.max(dR, nR)
      if (diff < 0.2) findings.push({ text: 'La brecha dia/noche es limitada (diferencia menor al 20%).', severity: 'low' })
    }
  }

  const cov = diagData?.overview?.source_coverage || diagData?.quality?.source_coverage || {}
  if (cov.close_driver_coverage_pct != null && cov.close_driver_coverage_pct < 80) {
    findings.push({ text: `Cobertura de liquidaciones insuficiente (${cov.close_driver_coverage_pct}%). Cierres no registrados o proceso incompleto.`, severity: 'medium' })
  }
  if (cov.plate_coverage_pct != null && cov.plate_coverage_pct < 80) {
    findings.push({ text: `Relacion vehiculo-conductor parcial (${cov.plate_coverage_pct}%). Rentabilidad por vehiculo incompleta.`, severity: 'medium' })
  }
  if (cov.billing_weeks != null && cov.billing_weeks < 4) {
    findings.push({ text: `Solo ${cov.billing_weeks} semana(s) de billing. Sin suficiente historico para simular esquemas de pago.`, severity: 'high' })
  }
  if (cov.shift_days && cov.shift_days > 7 && (cov.close_driver_coverage_pct == null || cov.close_driver_coverage_pct < 80)) {
    findings.push({ text: 'Hay produccion registrada (' + cov.shift_days + ' dias de shifts) pero no todos los cierres estan siendo capturados.', severity: 'medium' })
  }

  if (findings.length === 0) return null

  const sevColor = { high: 'border-l-red-500 bg-red-50/40', medium: 'border-l-amber-500 bg-amber-50/40', low: 'border-l-blue-400 bg-blue-50/40' }

  return (
    <div className="space-y-2">
      <SectionTitle>Hallazgos observados</SectionTitle>
      <div className="space-y-1.5">
        {findings.map((f, i) => (
          <div key={i} className={`border-l-4 rounded-r px-3 py-2 text-xs text-ct-text ${sevColor[f.severity] || sevColor.low}`}>
            {f.text}
          </div>
        ))}
      </div>
    </div>
  )
}

function DataConfidence ({ quality, billingWeeks }) {
  const confItems = [
    { label: 'Operacion', level: 'HIGH', color: 'bg-emerald-100 text-emerald-800 border-emerald-300' },
    { label: 'Billing', level: 'PARTIAL', color: 'bg-amber-100 text-amber-800 border-amber-300' },
    { label: 'Simulacion', level: 'N/A', color: 'bg-gray-100 text-gray-500 border-gray-300' },
  ]
  return (
    <div className="space-y-2">
      <SectionTitle>Confianza de datos</SectionTitle>
      <div className="bg-ct-card rounded-lg border border-ct-border p-3">
        <div className="flex flex-wrap gap-2 mb-2">
          {confItems.map((c) => (
            <span key={c.label} className={`inline-flex items-center gap-1.5 px-2 py-1 rounded border text-xs font-medium ${c.color}`}>
              {c.label}: <span className="font-bold">{c.level}</span>
            </span>
          ))}
        </div>
        <div className="text-xs text-ct-text2">Historico financiero disponible: <span className="font-semibold">{billingWeeks} semana{billingWeeks !== 1 ? 's' : ''}</span>.</div>
      </div>
    </div>
  )
}

function OverviewDiagnostic ({ diagData, diagLoading, diagErrors, billingWeeks }) {
  const anyLoading = Object.values(diagLoading).some(Boolean)
  const allDone = Object.values(diagLoading).every((v) => !v)
  const hasAnyData = Object.values(diagData).some((v) => v != null)

  if (anyLoading && !hasAnyData) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="w-5 h-5 border-2 border-ct-accent border-t-transparent rounded-full animate-spin" />
        <span className="ml-2 text-xs text-ct-text3">Cargando diagnostico ejecutivo...</span>
      </div>
    )
  }

  if (allDone && !hasAnyData) return <EmptyState tabId="overview" />

  return (
    <div className="space-y-4">
      {diagErrors.overview && <SectionError label="resumen" />}
      <DiagnosticHeader overview={diagData.overview} drivers={diagData.drivers} vehicles={diagData.vehicles} />

      {diagData.vehicles ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <TopRankedCard title="TOP VEHICULOS EN PERDIDA" rows={extractRows(diagData.vehicles)} isLoss />
          <TopRankedCard title="TOP VEHICULOS RENTABLES" rows={extractRows(diagData.vehicles)} isLoss={false} />
        </div>
      ) : diagErrors.vehicles ? <SectionError label="vehiculos" /> : null}

      {diagData.drivers ? (
        <DriverLeaderboard drivers={diagData.drivers} />
      ) : diagErrors.drivers ? <SectionError label="conductores" /> : null}

      {diagData.waterfall ? (
        <LossExplanation waterfall={diagData.waterfall} />
      ) : diagErrors.waterfall ? <SectionError label="waterfall" /> : null}

      {(diagData.overview || diagData.drivers || diagData.vehicles) && (
        <UtilizationDiagnostics overview={diagData.overview} drivers={diagData.drivers} vehicles={diagData.vehicles} />
      )}

      {diagData.shifts ? (
        <ShiftDiagnostics shifts={diagData.shifts} />
      ) : diagErrors.shifts ? <SectionError label="turnos" /> : null}

      <KeyFindings
        overview={diagData.overview}
        drivers={diagData.drivers}
        vehicles={diagData.vehicles}
        waterfall={diagData.waterfall}
        shifts={diagData.shifts}
        diagData={diagData}
      />

      <DataConfidence quality={diagData.quality} billingWeeks={billingWeeks} />

      {anyLoading && (
        <div className="text-[10px] text-ct-text3 flex items-center gap-1">
          <div className="w-3 h-3 border border-ct-accent border-t-transparent rounded-full animate-spin" />
          Cargando secciones adicionales...
        </div>
      )}
    </div>
  )
}

function DataTable ({ rows, columns, tabId }) {
  if (!rows || rows.length === 0) return <EmptyState tabId={tabId} />
  const sorted = sortRows(rows, tabId)
  const cols = columns || (sorted.length > 0 ? Object.keys(sorted[0]).filter((k) => !k.endsWith('_source') && !k.endsWith('_confidence')) : [])
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs border-collapse">
        <thead>
          <tr className="border-b border-ct-border">
            {cols.map((c) => <th key={c} className="px-2 py-1.5 text-left font-medium text-ct-text2 whitespace-nowrap">{colLabel(c)}</th>)}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr key={i} className="border-b border-ct-border/50 hover:bg-ct-surface/50">
              {cols.map((c) => {
                const isProfit = ['profit', 'net_profit', 'margin', 'result'].includes(c)
                return (
                  <td key={c} className="px-2 py-1.5 whitespace-nowrap">
                    <span className={isProfit && typeof safeVal(row[c]) === 'number' && row[c] < 0 ? 'text-red-600 font-medium' : ''}>
                      {fmtCellValue(row[c], c)}
                    </span>
                    {isProfit && num(row[c]) !== null && row[c] < 0 && <span className="text-[10px] bg-red-50 text-red-600 px-1 py-px rounded ml-1">En perdida</span>}
                    {(c === 'shift' || c === 'shift_type') && <ShiftIcon type={row[c]} />}
                    {row[`${c}_source`] && <SourceBadge source={row[`${c}_source`]} confidence={row[`${c}_confidence`]} />}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="text-[10px] text-ct-text3 mt-1 px-1">{sorted.length} registro{sorted.length !== 1 ? 's' : ''}</div>
    </div>
  )
}

function TabularPanel ({ data, tabId }) {
  if (!data) return <EmptyState tabId={tabId} />
  const rows = data.rows || data.data || (Array.isArray(data) ? data : null)
  const columns = data.columns || null
  const meta = data.meta || data.period || null
  if (!rows || rows.length === 0) return <><GuideBlock tabId={tabId} /><EmptyState tabId={tabId} /></>
  return (
    <div className="space-y-3">
      <GuideBlock tabId={tabId} />
      {meta && (
        <div className="flex flex-wrap gap-2 text-[11px] text-ct-text3">
          {typeof meta === 'string' ? <span>{meta}</span> : Object.entries(meta).map(([k, v]) => (
            <span key={k} className="bg-gray-50 px-1.5 py-0.5 rounded">{colLabel(k)}: {fmtCellValue(v, k)}</span>
          ))}
        </div>
      )}
      {data.missing_sources && data.missing_sources.length > 0 && (
        <div className="flex flex-wrap gap-1">{data.missing_sources.map((ms, i) => <MissingSourceNotice key={i} field={ms} />)}</div>
      )}
      <DataTable rows={rows} columns={columns} tabId={tabId} />
    </div>
  )
}

function WaterfallPanel ({ data }) {
  if (!data) return <><GuideBlock tabId="waterfall" /><EmptyState tabId="waterfall" /></>
  const items = data.steps || data.items || data.rows || data.data || (Array.isArray(data) ? data : null)
  const isPartial = data.partial === true || data.is_partial === true
  if (!items || items.length === 0) return <><GuideBlock tabId="waterfall" /><EmptyState tabId="waterfall" /></>
  return (
    <div className="space-y-2">
      <GuideBlock tabId="waterfall" />
      {isPartial && <div className="bg-amber-50 border border-amber-200 rounded px-3 py-1.5 text-[11px] text-amber-700">Waterfall parcial: algunos inputs no tienen fuente financiera completa. Resultado observado con datos disponibles.</div>}
      {data.missing_sources && data.missing_sources.length > 0 && <div className="flex flex-wrap gap-1 mb-1">{data.missing_sources.map((ms, i) => <MissingSourceNotice key={i} field={ms} />)}</div>}
      {items.map((item, i) => {
        const label = item.label || item.name || item.step || colLabel(item.input || `step_${i + 1}`)
        const raw = num(item.value ?? item.amount); const value = raw ?? 0; const isPositive = value >= 0
        const pct = maxAbs > 0 ? (Math.abs(value) / maxAbs) * 100 : 0
        return (
          <div key={i} className="flex items-center gap-2 bg-ct-card rounded border border-ct-border px-3 py-2">
            <span className="text-xs text-ct-text2 w-44 flex-shrink-0 truncate" title={label}>{label}</span>
            <div className="flex-1 h-5 bg-gray-100 rounded overflow-hidden"><div className={`h-full rounded ${isPositive ? 'bg-emerald-400' : 'bg-red-400'}`} style={{ width: `${Math.min(pct, 100)}%` }} /></div>
            <span className={`text-xs font-medium w-24 text-right ${isPositive ? 'text-emerald-600' : 'text-red-600'}`}>{raw !== null ? fmt(value, 'currency') : 'No disponible'}</span>
            {item.missing_source ? <MissingSourceNotice /> : <SourceBadge source={item.source} confidence={item.confidence} />}
          </div>
        )
      })}
      <div className="mt-2 bg-ct-card rounded-lg border border-ct-border overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead><tr className="border-b border-ct-border"><th className="px-2 py-1.5 text-left font-medium text-ct-text2">Input</th><th className="px-2 py-1.5 text-right font-medium text-ct-text2">Valor</th><th className="px-2 py-1.5 text-left font-medium text-ct-text2">Fuente</th><th className="px-2 py-1.5 text-left font-medium text-ct-text2">Confianza</th></tr></thead>
          <tbody>{items.map((item, i) => (
            <tr key={i} className="border-b border-ct-border/50">
              <td className="px-2 py-1.5">{item.label || item.name || item.step || colLabel(item.input || `step_${i + 1}`)}</td>
              <td className="px-2 py-1.5 text-right font-medium">{fmt(num(item.value ?? item.amount), 'currency')}</td>
              <td className="px-2 py-1.5">{SOURCE_TYPE_LABELS[item.source] || item.source || 'No disponible'}</td>
              <td className="px-2 py-1.5">{item.confidence || 'No disponible'}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  )
}

function QualityPanel ({ data }) {
  if (!data) return <><GuideBlock tabId="quality" /><EmptyState tabId="quality" /></>
  const checks = data.checks || data.inputs || data.rows || data.data || (Array.isArray(data) ? data : null)
  if (!checks || checks.length === 0) return <><GuideBlock tabId="quality" /><EmptyState tabId="quality" /></>

  const sourceInfo = [
    { table: 'module_calculated_shifts', label: 'Produccion diaria / turnos', icon: '&#9711;' },
    { table: 'module_driver_closes', label: 'Liquidaciones y pagos al conductor', icon: '&#9632;' },
    { table: 'module_weekly_billing', label: 'Cierre financiero semanal', icon: '&#9650;' },
  ]

  const grouped = {}
  for (const check of checks) { const key = (check.source_type || check.type || check.category || 'unknown').toUpperCase(); if (!grouped[key]) grouped[key] = []; grouped[key].push(check) }
  const groupOrder = ['REAL', 'DERIVED', 'ASSUMPTION', 'NOT_AVAILABLE']
  const sortedKeys = [...new Set([...groupOrder.filter((k) => grouped[k]), ...Object.keys(grouped).filter((k) => !groupOrder.includes(k))])]
  const hasGroups = sortedKeys.length > 1 || (sortedKeys.length === 1 && sortedKeys[0] !== 'UNKNOWN')
  const statusColor = (s) => ({ ok: 'bg-emerald-50 text-emerald-700 border-emerald-200', pass: 'bg-emerald-50 text-emerald-700 border-emerald-200', warning: 'bg-amber-50 text-amber-700 border-amber-200', fail: 'bg-red-50 text-red-700 border-red-200', error: 'bg-red-50 text-red-700 border-red-200' })[String(s).toLowerCase()] || 'bg-gray-50 text-gray-700 border-gray-200'
  return (
    <div className="space-y-4">
      <GuideBlock tabId="quality" />

      <div className="bg-ct-card rounded-lg border border-ct-border p-3">
        <div className="text-xs font-medium text-ct-text mb-2">Fuentes de datos de Profitability</div>
        <div className="space-y-1 text-[11px] text-ct-text2">
          {sourceInfo.map((s) => (
            <div key={s.table} className="flex items-start gap-2">
              <span className="text-ct-text3 mt-0.5">{s.icon}</span>
              <div><strong className="text-ct-text">{s.table}</strong> = {s.label}</div>
            </div>
          ))}
        </div>
      </div>
      {data.summary && <div className="flex flex-wrap gap-3 mb-1">{Object.entries(data.summary).map(([k, v]) => <span key={k} className="text-xs bg-gray-50 px-2 py-1 rounded border border-ct-border"><span className="text-ct-text3">{colLabel(k)}:</span> <span className="font-medium text-ct-text">{fmtCellValue(v, k)}</span></span>)}</div>}
      {hasGroups ? sortedKeys.map((gk) => (
        <div key={gk}>
          <div className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium border mb-2 ${SOURCE_TYPE_COLORS[gk] || 'bg-gray-50 text-gray-600 border-gray-200'}`}>{SOURCE_TYPE_LABELS[gk] || gk}</div>
          <div className="space-y-1.5 ml-1">{grouped[gk].map((c, i) => <QualityRow key={i} check={c} statusColor={statusColor} />)}</div>
        </div>
      )) : <div className="space-y-1.5">{checks.map((c, i) => <QualityRow key={i} check={c} statusColor={statusColor} />)}</div>}
    </div>
  )
}

function QualityRow ({ check, statusColor }) {
  const status = check.status || check.result || 'unknown'
  return (
    <div className={`rounded border px-3 py-2 flex items-start gap-3 ${statusColor(status)}`}>
      <span className="text-[10px] font-semibold w-16 flex-shrink-0 uppercase mt-0.5">{status}</span>
      <div className="flex-1 min-w-0">
        <div className="text-xs font-medium">{check.label || check.name || check.input || check.check || 'Check'}</div>
        {(check.observation || check.detail) && <div className="text-[10px] opacity-80 mt-0.5">{check.observation || check.detail}</div>}
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        {check.source && <span className="text-[10px] bg-white/60 px-1.5 py-0.5 rounded">{SOURCE_TYPE_LABELS[check.source] || check.source}</span>}
        {check.confidence && <span className="text-[10px] bg-white/60 px-1.5 py-0.5 rounded">{check.confidence}</span>}
      </div>
    </div>
  )
}

function renderTabPanel (tabId, data) {
  switch (tabId) {
    case 'waterfall': return <WaterfallPanel data={data} />
    case 'quality': return <QualityPanel data={data} />
    default: return <TabularPanel data={data} tabId={tabId} />
  }
}

function friendlyError (err, tabLabel) {
  const status = err.response?.status
  if (status === 404) return `Datos de ${tabLabel} no disponibles en este momento.`
  if (status === 502 || status === 503) return 'Servicio temporalmente fuera de alcance. Reintenta en unos minutos.'
  if (status === 504) return 'Tiempo de espera agotado al consultar datos. Reintenta en unos minutos.'
  if (status === 401 || status === 403) return 'Sesion expirada o sin permisos. Recarga la pagina.'
  if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) return 'Tiempo de espera agotado. Reintenta en unos minutos.'
  if (err.code === 'ERR_CANCELED') return null
  const detail = err.response?.data?.detail || err.response?.data?.message
  if (detail && typeof detail === 'string' && detail.length < 200) return detail
  return `No se pudieron cargar los datos de ${tabLabel}. Reintenta en unos minutos.`
}

const DIAG_ENDPOINTS = [
  { key: 'overview', fetcher: getYegoProProfitabilityOverview },
  { key: 'weekly', fetcher: getYegoProProfitabilityWeekly },
  { key: 'daily', fetcher: getYegoProProfitabilityDaily },
  { key: 'drivers', fetcher: getYegoProProfitabilityDrivers },
  { key: 'vehicles', fetcher: getYegoProProfitabilityVehicles },
  { key: 'shifts', fetcher: getYegoProProfitabilityShifts },
  { key: 'waterfall', fetcher: getYegoProProfitabilityInputMapping },
  { key: 'quality', fetcher: getYegoProProfitabilityQuality },
  { key: 'rootCause', fetcher: getYegoProProfitabilityRootCause },
]

export default function YegoProProfitabilityPage () {
  const [activeTab, setActiveTab] = useState('overview')
  const [tabData, setTabData] = useState(null)
  const [tabLoading, setTabLoading] = useState(false)
  const [tabError, setTabError] = useState(null)
  const [billingWeeks, setBillingWeeks] = useState(1)

  const [diagData, setDiagData] = useState({})
  const [diagLoading, setDiagLoading] = useState({})
  const [diagErrors, setDiagErrors] = useState({})
  const [diagLoaded, setDiagLoaded] = useState(false)

  const abortRef = useRef(null)
  const diagAbortRef = useRef(null)

  useEffect(() => {
    if (diagLoaded) return
    setDiagLoaded(true)
    if (diagAbortRef.current) diagAbortRef.current.abort()
    const controller = new AbortController()
    diagAbortRef.current = controller

    const initial = {}; const initLoading = {}; const initErrors = {}
    DIAG_ENDPOINTS.forEach((e) => { initial[e.key] = null; initLoading[e.key] = true; initErrors[e.key] = null })
    setDiagData(initial); setDiagLoading(initLoading); setDiagErrors(initErrors)

    DIAG_ENDPOINTS.forEach(({ key, fetcher }) => {
      fetcher().then((result) => {
        if (controller.signal.aborted) return
        setDiagData((prev) => ({ ...prev, [key]: result }))
        if (key === 'quality' && result) {
          const w = result.billing_weeks ?? result.summary?.billing_weeks
          if (typeof w === 'number' && w > 0) setBillingWeeks(w)
        }
        if (key === 'overview' && result) {
          const w = result.billing_weeks ?? result.meta?.billing_weeks
          if (typeof w === 'number' && w > 0) setBillingWeeks(w)
        }
      }).catch((err) => {
        if (controller.signal.aborted) return
        setDiagErrors((prev) => ({ ...prev, [key]: true }))
      }).finally(() => {
        if (!controller.signal.aborted) setDiagLoading((prev) => ({ ...prev, [key]: false }))
      })
    })

    return () => controller.abort()
  }, [diagLoaded])

  const loadTab = useCallback(async (tabId) => {
    if (tabId === 'overview' || tabId === 'coverage') return
    if (abortRef.current) abortRef.current.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const tab = TABS.find((t) => t.id === tabId)
    if (!tab) return
    setTabLoading(true); setTabError(null); setTabData(null)
    try {
      const result = await tab.fetcher()
      if (controller.signal.aborted) return
      setTabData(result)
    } catch (err) {
      if (controller.signal.aborted) return
      const msg = friendlyError(err, tab.label)
      if (msg) setTabError(msg)
    } finally {
      if (!controller.signal.aborted) setTabLoading(false)
    }
  }, [])

  useEffect(() => {
    if (activeTab !== 'overview') loadTab(activeTab)
    return () => { if (abortRef.current) abortRef.current.abort() }
  }, [activeTab, loadTab])

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-base font-semibold text-ct-text">Yego Pro &mdash; Profitability</h1>
          <p className="text-[11px] text-ct-text3">Fleet Project &rsaquo; Yego Pro &rsaquo; Profitability</p>
        </div>
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-xs text-amber-800 flex items-center gap-2">
        <svg className="w-3.5 h-3.5 flex-shrink-0 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
        </svg>
        Historico financiero parcial: billing disponible para {billingWeeks} semana{billingWeeks !== 1 ? 's' : ''}.
      </div>

      <div className="flex gap-0.5 border-b border-ct-border overflow-x-auto">
        {TABS.map(({ id, label }) => (
          <button key={id} type="button" onClick={() => setActiveTab(id)}
            className={`px-3 py-2 text-xs font-medium whitespace-nowrap transition-all border-b-2 ${activeTab === id ? 'border-ct-accent text-ct-accent' : 'border-transparent text-ct-text2 hover:text-ct-text hover:border-ct-border'}`}>
            {label}
          </button>
        ))}
      </div>

      <div className="min-h-[200px]">
        {activeTab === 'overview' && (
          <OverviewDiagnostic diagData={diagData} diagLoading={diagLoading} diagErrors={diagErrors} billingWeeks={billingWeeks} />
        )}

        {activeTab === 'coverage' && (
          <CoverageAuditPanel diagData={diagData} />
        )}

        {activeTab !== 'overview' && activeTab !== 'coverage' && tabLoading && (
          <div className="flex items-center justify-center py-12">
            <div className="w-5 h-5 border-2 border-ct-accent border-t-transparent rounded-full animate-spin" />
            <span className="ml-2 text-xs text-ct-text3">Cargando {TABS.find((t) => t.id === activeTab)?.label}...</span>
          </div>
        )}

        {activeTab !== 'overview' && activeTab !== 'coverage' && tabError && !tabLoading && (
          <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-xs text-red-700 flex items-center gap-2">
            <span>{tabError}</span>
            <button type="button" onClick={() => loadTab(activeTab)} className="ml-auto px-2 py-0.5 rounded bg-red-100 hover:bg-red-200 text-red-700 text-[11px] font-medium transition-colors">Reintentar</button>
          </div>
        )}

        {activeTab !== 'overview' && activeTab !== 'coverage' && !tabLoading && !tabError && tabData && renderTabPanel(activeTab, tabData)}
        {activeTab !== 'overview' && activeTab !== 'coverage' && !tabLoading && !tabError && !tabData && <EmptyState tabId={activeTab} />}
      </div>
    </div>
  )
}
