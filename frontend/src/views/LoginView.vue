<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'

type PatientOption = { title: string; value: string }

const router = useRouter()
const { login } = useAuth()

const patients: PatientOption[] = [
  {
    title: 'Paciente Sano (Control)',
    value: 'e9f7e4d0-2e3e-4ebf-b77a-18011e5897fa',
  },
  {
    title: 'Paciente Fatigado (Alerta IA)',
    value: 'f05277dc-ecee-4ea2-9c4c-3de9b54008f1',
  },
  {
    title: 'Paciente Fragmentado (Alerta IA)',
    value: '2013db39-79dd-45ec-b9ae-9eeaa7b1b6ad',
  },
]

const selectedPatientId = ref<string | null>(null)
const selectedPatientName = computed(() => {
  const found = patients.find((p) => p.value === selectedPatientId.value)
  return found?.title ?? null
})

const isValid = computed(() => !!selectedPatientId.value && !!selectedPatientName.value)

function onSubmit() {
  if (!selectedPatientId.value || !selectedPatientName.value) return
  login(selectedPatientId.value, selectedPatientName.value)
  router.push('/')
}
</script>

<template>
  <div class="h-screen flex items-center justify-center bg-slate-50 px-6">
    <v-card class="w-full max-w-lg" elevation="6">
      <v-card-title class="text-slate-900">
        Acceso B2B · WeSleep
      </v-card-title>
      <v-card-subtitle class="text-slate-600">
        Selecciona un paciente para entrar al panel (mock auth).
      </v-card-subtitle>

      <v-card-text class="pt-6">
        <v-select
          v-model="selectedPatientId"
          :items="patients"
          item-title="title"
          item-value="value"
          label="Paciente"
          variant="outlined"
          color="primary"
          density="comfortable"
          hide-details
        />
      </v-card-text>

      <v-card-actions class="px-4 pb-4">
        <v-spacer />
        <v-btn
          color="primary"
          variant="flat"
          :disabled="!isValid"
          @click="onSubmit"
        >
          Entrar
        </v-btn>
      </v-card-actions>
    </v-card>
  </div>
</template>

