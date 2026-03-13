/**
 * Mapeo canonical_key (API) → etiqueta de visualización en UI.
 * Alineado con backend/app/contracts/data_contract.py REAL_SERVICE_TYPE_DISPLAY.
 * NO normalizar aquí: solo mostrar el valor canónico con etiqueta unificada (CONFORT_PLUS, TUK_TUK, DELIVERY).
 */
export const REAL_SERVICE_TYPE_DISPLAY = {
  comfort_plus: 'CONFORT_PLUS',
  tuk_tuk: 'TUK_TUK',
  delivery: 'DELIVERY',
  economico: 'ECONOMY',
  comfort: 'COMFORT',
  minivan: 'MINIVAN',
  premier: 'PREMIER',
  standard: 'STANDARD',
  start: 'START',
  xl: 'XL',
  economy: 'ECONOMY',
  cargo: 'CARGO',
  moto: 'MOTO',
  taxi_moto: 'MOTO',
  UNCLASSIFIED: 'UNCLASSIFIED',
}

/**
 * Devuelve la etiqueta de visualización para un tipo de servicio REAL canónico.
 * Si no está en el mapa, devuelve el valor en mayúsculas o el original.
 */
export function formatRealServiceTypeDisplay(canonicalKey) {
  if (canonicalKey == null || canonicalKey === '') return '—'
  const k = String(canonicalKey).trim().toLowerCase()
  return REAL_SERVICE_TYPE_DISPLAY[k] ?? canonicalKey
}
