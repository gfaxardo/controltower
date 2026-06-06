import { useState, useEffect, useCallback } from 'react'
import {
  getLimaGrowthOperationalSummary,
  getLimaGrowthDriverStateSummary,
  getLimaGrowthProgramsSummary,
  getLimaGrowthOpportunityWorklist,
  getLimaGrowthAssignmentQueue,
  buildLimaGrowthAssignmentQueue,
  getLoopControlConfig,
  getLoopControlExports,
  getLimaGrowthCapacitySummary,
  updateLimaGrowthCapacityConfig,
  getLimaGrowthPriorityAllocation,
  getLimaGrowthChannelAllocation,
} from '../../../services/api.js'
import api from '../../../services/api.js'

export default function useLimaGrowthData(date) {
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
      setErrors((p) => ({ ...p, [key]: e.message || 'Error' }))
      return null
    } finally {
      setLoading((p) => ({ ...p, [key]: false }))
    }
  }, [])

  useEffect(() => {
    fetchSection('summary', () => getLimaGrowthOperationalSummary(date))
    fetchSection('driverState', () => getLimaGrowthDriverStateSummary(date))
    fetchSection('programs', () => getLimaGrowthProgramsSummary(date))
    fetchSection('config', getLoopControlConfig)
    fetchSection('exports', () => getLoopControlExports({ limit: 10 }))
    fetchSection('capacity', () => getLimaGrowthCapacitySummary(date))
    fetchSection('priorityAlloc', () => getLimaGrowthPriorityAllocation(date))
    fetchSection('channelAlloc', () => getLimaGrowthChannelAllocation(date))
  }, [date, fetchSection])

  const refreshQueue = useCallback((filters = {}) => {
    return fetchSection('queue', () => getLimaGrowthAssignmentQueue({ date, ...filters }))
  }, [date, fetchSection])

  const buildQueue = useCallback(async () => {
    const result = await buildLimaGrowthAssignmentQueue(date)
    await refreshQueue()
    return result
  }, [date, refreshQueue])

  const refreshWorklist = useCallback((filters = {}) => {
    return fetchSection('worklist', () => getLimaGrowthOpportunityWorklist({ date, limit: 1000, ...filters }))
  }, [date, fetchSection])

  const exportQueue = useCallback(async (limit = 5) => {
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

  return {
    data, loading, errors,
    refreshQueue, buildQueue, refreshWorklist, exportQueue, saveCapacity,
    fetchSection,
  }
}
