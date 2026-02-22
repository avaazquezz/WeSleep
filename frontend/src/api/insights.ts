import { api } from './axios'

export async function getWeeklyInsights(patientId: string) {
  const { data } = await api.get(`/insights/weekly/${patientId}`)
  return data
}

export async function getMonthlyAnomaly(patientId: string) {
  const { data } = await api.get(`/insights/monthly/${patientId}`)
  return data
}

