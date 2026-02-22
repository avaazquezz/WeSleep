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
  <div
    class="relative min-h-screen overflow-hidden flex items-center justify-center px-6"
    style="background: #091524;"
  >
    <!-- Ambient glow -->
    <div
      class="pointer-events-none absolute inset-0"
      style="background: radial-gradient(ellipse 70% 50% at 50% 25%, rgba(0,229,160,0.055) 0%, transparent 100%);"
    />

    <div class="relative z-10 w-full max-w-sm">
      <!-- Logo mark -->
      <div class="mb-10 flex flex-col items-center gap-4">
        <div
          class="flex h-16 w-16 items-center justify-center rounded-full"
          style="background: rgba(255,255,255,0.05); border: 1.5px solid rgba(255,255,255,0.1);"
        >
          <span class="text-xl font-bold tracking-tight text-white">W</span>
        </div>
        <div class="text-center">
          <h1 class="text-3xl font-bold tracking-tight text-white">WeSleep</h1>
          <p class="mt-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-white/30">
            Clinical Intelligence
          </p>
        </div>
      </div>

      <!-- Login card -->
      <div
        class="overflow-hidden rounded-2xl px-6 py-7"
        style="background: #112240; border: 1px solid rgba(255,255,255,0.07);"
      >
        <h2 class="text-[15px] font-semibold text-white">Acceso B2B</h2>
        <p class="mt-0.5 text-xs text-white/40">
          Selecciona un perfil de paciente para continuar.
        </p>

        <div class="mt-6">
          <v-select
            v-model="selectedPatientId"
            :items="patients"
            item-title="title"
            item-value="value"
            label="Paciente"
            variant="outlined"
            density="comfortable"
            hide-details
            color="#00e5a0"
            base-color="rgba(255,255,255,0.3)"
          />
        </div>

        <button
          class="mt-5 w-full rounded-xl py-3.5 text-sm font-bold transition-all active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40"
          style="background: #00e5a0; color: #091524;"
          :disabled="!isValid"
          @click="onSubmit"
        >
          Entrar al Panel
        </button>
      </div>

      <p class="mt-8 text-center text-[10px] tracking-wide text-white/15">
        WeSleep Technologies · Barcelona
      </p>
    </div>
  </div>
</template>

