import { useState, useEffect, useCallback } from 'react'
import {
  getLimaGrowthTodayActionPlan,
  getLimaGrowthAllocationTrace,
  getLimaGrowthProgramCapacityPolicy,
  getLimaGrowthOperationalSummary,
  getLimaGrowthDriverStateSummary,
  getLimaGrowthProgramsSummary,
  getLimaGrowthOpportunityWorklist,
  getLimaGrowthAssignmentQueue,
  buildLimaGrowthAssignmentQueue,
  getLimaGrowthQueueSummary,
  getLoopControlConfig,
  getLoopControlExports,
  getLimaGrowthCapacitySummary,
  updateLimaGrowthCapacityConfig,
  getLimaGrowthPriorityAllocation,
  getLimaGrowthChannelAllocation,
  getLimaGrowthIntradaySignalsSummary,
  getLimaGrowthIntradaySignalsByCampaign,
  getLimaGrowthIntradaySignalsByProgram,
  buildLimaGrowthIntradaySignals,
  getLimaGrowthOperationalTruth,
  getLimaGrowthProgramStatus,
} from '../../../services/api.js'
import api from '../../../services/api.js'

export default function useLimaGrowthData(date) {
  const [data, setData] = useState({})
  const [loading, setLoading] = useState({})
  const [errors, setErrors] = useState({})
  const [effectiveDate, setEffectiveDate] = useState(date)

  const fetchSection = useCallback(async (key, fn) => {
    setLoading((p) => ({ ...p, [key]: true }))
    setErrors((p) => ({ ...p, [key]: null }))
    try {
      const result = await fn()
      if (result?.status === 'MISSING_SERVING_FACT') {
        setErrors((p) => ({ ...p, [key]: result.remediation || 'Serving fact no disponible' }))
        setData((p) => ({ ...p, [key]: null, [`${key}_missing`]: result }))
        return null
      }
      setData((p) => ({ ...p, [key]: result }))
      return result
    } catch (e) {
      setErrors((p) => ({ ...p, [key]: e.message || 'Error' }))
      return null
    } finally {
      setLoading((p) => ({ ...p, [key]: false }))
    }
  }, [])

  useEffect(() => {
    if (!date) return
    fetchSection('todayActionPlan', () => getLimaGrowthTodayActionPlan(date))
    fetchSection('allocationTrace', () => getLimaGrowthAllocationTrace(date))
    fetchSection('programPolicy', () => getLimaGrowthProgramCapacityPolicy(date))
    fetchSection('summary', () => getLimaGrowthOperationalSummary(date))
    fetchSection('driverState', () => getLimaGrowthDriverStateSummary(date))
    fetchSection('programs', () => getLimaGrowthProgramsSummary(date))
    fetchSection('config', getLoopControlConfig)
    fetchSection('exports', () => getLoopControlExports({ limit: 10 }))
    fetchSection('capacity', () => getLimaGrowthCapacitySummary(date))
    fetchSection('priorityAlloc', () => getLimaGrowthPriorityAllocation(date))
    fetchSection('channelAlloc', () => getLimaGrowthChannelAllocation(date))
    fetchSection('queueSummary', () => getLimaGrowthQueueSummary(date))
    fetchSection('intradaySignals', () => getLimaGrowthIntradaySignalsSummary(date))
    fetchSection('intradaySignalsByCampaign', () => getLimaGrowthIntradaySignalsByCampaign(date))
    fetchSection('intradaySignalsByProgram', () => getLimaGrowthIntradaySignalsByProgram(date))
    fetchSection('operationalTruth', () => getLimaGrowthOperationalTruth(date))
    fetchSection('programStatus', () => getLimaGrowthProgramStatus(date))
  }, [date, fetchSection])

  const refreshQueue = useCallback((filters = {}) => {
    return fetchSection('queue', () => getLimaGrowthAssignmentQueue({ date, ...filters }))
  }, [date, fetchSection])

  const buildQueue = useCallback(async () => {
    if (!date) throw new Error('No operational date available. Wait for data to load.')
    const result = await buildLimaGrowthAssignmentQueue(date)
    await refreshQueue()
    return result
  }, [date, refreshQueue])

  const refreshWorklist = useCallback((filters = {}) => {
    return fetchSection('worklist', () => getLimaGrowthOpportunityWorklist({ date, limit: 1000, ...filters }))
  }, [date, fetchSection])

  const exportQueue = useCallback(async (limit = 5) => {
    if (!date) throw new Error('No operational date available. Wait for data to load.')
    try {
      const response = await api.post('/yego-lima-growth/assignment-queue/export', {
        date,
        program_code: 'PROGRAM_CHURN_PREVENTION',
        campaign_name: `QUEUE_EXPORT_${date}`,
        limit,
      })
      setData((p) => ({ ...p, lastExport: response.data }))
      await refreshQueue()
      await fetchSection('summary', () => getLimaGrowthOperationalSummary(date))
      return response.data
    } catch (e) {
      setErrors((p) => ({ ...p, export: e.message || 'Export error' }))
      return null
    }
  }, [date, refreshQueue, fetchSection])

  const saveCapacity = useCallback(async (channels) => {
    const payload = {
      config_date: date,
      channels: channels.map((ch) => ({
        channel: ch.channel,
        agents: ch.agents,
        capacity_per_agent: ch.capacity_per_agent,
      })),
    }
    const result = await updateLimaGrowthCapacityConfig(payload)
    await fetchSection('capacity', () => getLimaGrowthCapacitySummary(date))
    return result
  }, [date, fetchSection])

  const buildIntradaySignals = useCallback(async () => {
    if (!date) throw new Error('No operational date available. Wait for data to load.')
    const result = await buildLimaGrowthIntradaySignals(date)
    await fetchSection('intradaySignals', () => getLimaGrowthIntradaySignalsSummary(date))
    await fetchSection('intradaySignalsByCampaign', () => getLimaGrowthIntradaySignalsByCampaign(date))
    await fetchSection('intradaySignalsByProgram', () => getLimaGrowthIntradaySignalsByProgram(date))
    return result
  }, [date, fetchSection])

  return {
    data, loading, errors,
    refreshQueue, buildQueue, refreshWorklist, exportQueue, saveCapacity,
    buildIntradaySignals,
    fetchSection,
  }
}
