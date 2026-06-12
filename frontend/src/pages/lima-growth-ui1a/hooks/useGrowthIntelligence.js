import { useState, useEffect, useCallback } from 'react'
import {
  getGrowthHealth,
  getGrowthFreshness,
  getGrowthOperability,
  getLimaGrowthOperationalSummary,
  getLimaGrowthDriverStateSummary,
  getLimaGrowthOperationalTruth,
  getLimaGrowthProgramsSummary,
  getLimaGrowthProgramStatus,
  getLimaGrowthTaxonomySummary,
  getLimaGrowthMovementSummary,
  getLimaGrowthMovementRecords,
  getYangoLoyaltySummary,
  getYangoLoyaltyKpis,
  getYangoLoyaltyCityComparison,
} from '../../../services/api.js'

export default function useGrowthIntelligence(date) {
  const [data, setData] = useState({})
  const [loading, setLoading] = useState({})
  const [errors, setErrors] = useState({})

  const fetchSection = useCallback(async (key, fn) => {
    setLoading((p) => ({ ...p, [key]: true }))
    setErrors((p) => ({ ...p, [key]: null }))
    try {
      const result = await fn()
      setData((p) => ({ ...p, [key]: result }))
      return result
    } catch (e) {
      const msg = e?.response?.data?.detail || e.message || 'Error fetching data'
      setErrors((p) => ({ ...p, [key]: msg }))
      return null
    } finally {
      setLoading((p) => ({ ...p, [key]: false }))
    }
  }, [])

  useEffect(() => {
    fetchSection('health', getGrowthHealth)
    fetchSection('freshness', getGrowthFreshness)
    fetchSection('operability', getGrowthOperability)
  }, [fetchSection])

  useEffect(() => {
    if (!date) return
    fetchSection('overview', () => getLimaGrowthOperationalSummary(date))
    fetchSection('driverState', () => getLimaGrowthDriverStateSummary(date))
    fetchSection('operationalTruth', () => getLimaGrowthOperationalTruth(date))
    fetchSection('programs', () => getLimaGrowthProgramsSummary(date))
    fetchSection('programStatus', () => getLimaGrowthProgramStatus(date))
    fetchSection('taxonomy', () => getLimaGrowthTaxonomySummary(date))
    fetchSection('movementSummary', () => getLimaGrowthMovementSummary({ date }))
    fetchSection('movementRecords', () => getLimaGrowthMovementRecords({ date, limit: 100 }))
    fetchSection('loyaltySummary', () => getYangoLoyaltySummary({}))
    fetchSection('loyaltyKPIs', () => getYangoLoyaltyKpis({}))
    fetchSection('loyaltyCityComp', () => getYangoLoyaltyCityComparison({}))
  }, [date, fetchSection])

  const retrySection = useCallback((key, fn) => {
    return fetchSection(key, fn)
  }, [fetchSection])

  const retryAll = useCallback(() => {
    fetchSection('health', getGrowthHealth)
    fetchSection('freshness', getGrowthFreshness)
    fetchSection('operability', getGrowthOperability)
    if (!date) return
    fetchSection('overview', () => getLimaGrowthOperationalSummary(date))
    fetchSection('driverState', () => getLimaGrowthDriverStateSummary(date))
    fetchSection('operationalTruth', () => getLimaGrowthOperationalTruth(date))
    fetchSection('programs', () => getLimaGrowthProgramsSummary(date))
    fetchSection('programStatus', () => getLimaGrowthProgramStatus(date))
    fetchSection('taxonomy', () => getLimaGrowthTaxonomySummary(date))
    fetchSection('movementSummary', () => getLimaGrowthMovementSummary({ date }))
    fetchSection('movementRecords', () => getLimaGrowthMovementRecords({ date, limit: 100 }))
    fetchSection('loyaltySummary', () => getYangoLoyaltySummary({}))
    fetchSection('loyaltyKPIs', () => getYangoLoyaltyKpis({}))
    fetchSection('loyaltyCityComp', () => getYangoLoyaltyCityComparison({}))
  }, [date, fetchSection])

  return { data, loading, errors, fetchSection, retrySection, retryAll }
}
