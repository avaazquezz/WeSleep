import { api } from './axios'

type PredictOptimalWakeupResponse = {
  optimal_wakeup_time: string
  reason: string
}

export async function predictOptimalWakeup(patientId: string, targetTime: string) {
  const { data } = await api.get<PredictOptimalWakeupResponse>(`/alarm/predict/${patientId}`, {
    params: { target_time: targetTime },
  })
  return data
}

