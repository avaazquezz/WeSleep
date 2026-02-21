import { ref } from 'vue'

const LS_PATIENT_ID_KEY = 'patientId'
const LS_PATIENT_NAME_KEY = 'patientName'

export const currentPatientId = ref<string | null>(
  localStorage.getItem(LS_PATIENT_ID_KEY),
)
export const currentPatientName = ref<string | null>(
  localStorage.getItem(LS_PATIENT_NAME_KEY),
)

function login(id: string, name: string) {
  localStorage.setItem(LS_PATIENT_ID_KEY, id)
  localStorage.setItem(LS_PATIENT_NAME_KEY, name)
  currentPatientId.value = id
  currentPatientName.value = name
}

function logout() {
  localStorage.removeItem(LS_PATIENT_ID_KEY)
  localStorage.removeItem(LS_PATIENT_NAME_KEY)
  currentPatientId.value = null
  currentPatientName.value = null
}

export function useAuth() {
  return {
    currentPatientId,
    currentPatientName,
    login,
    logout,
  }
}

