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
    class="relative min-h-screen overflow-hidden flex items-stretch"
    style="background: #091524;"
  >
    <!-- Ambient glow -->
    <div
      class="pointer-events-none absolute inset-0"
      style="background: radial-gradient(ellipse 80% 60% at 50% 20%, rgba(0,229,160,0.055) 0%, transparent 100%);"
    />

    <!-- Mobile: full screen centered | Desktop: split layout -->
    <div class="relative z-10 flex w-full flex-col lg:flex-row">

      <!-- ─── LEFT PANEL (desktop only) ─── -->
      <div
        class="hidden lg:flex lg:flex-col lg:justify-between lg:w-[44%] xl:w-[40%] px-12 xl:px-16 py-12"
        style="border-right: 1px solid rgba(255,255,255,0.05);"
      >
        <!-- Top: Logo + Brand -->
        <div>
          <div class="flex items-center gap-4 mb-16">
            <div
              class="flex h-12 w-12 items-center justify-center rounded-full"
              style="background: rgba(255,255,255,0.05); border: 1.5px solid rgba(255,255,255,0.1);"
            >
              <span class="text-lg font-bold tracking-tight text-white">W</span>
            </div>
            <div>
              <h1 class="text-xl font-bold tracking-tight text-white">WeSleep</h1>
              <p class="text-[10px] font-semibold uppercase tracking-[0.2em] text-white/30">
                Clinical Intelligence
              </p>
            </div>
          </div>

          <!-- Feature highlights -->
          <div class="space-y-6">
            <div class="flex items-start gap-4">
              <div
                class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl"
                style="background: rgba(0,229,160,0.1); border: 1px solid rgba(0,229,160,0.15);"
              >
                <v-icon size="15" color="#00e5a0">mdi-alarm</v-icon>
              </div>
              <div>
                <p class="text-sm font-semibold text-white/80">Smart Alarm</p>
                <p class="mt-0.5 text-xs text-white/35 leading-relaxed">
                  Despertador personalizado basado en tus fases de sueño.
                </p>
              </div>
            </div>

            <div class="flex items-start gap-4">
              <div
                class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl"
                style="background: rgba(56,189,248,0.1); border: 1px solid rgba(56,189,248,0.15);"
              >
                <v-icon size="15" color="#38bdf8">mdi-robot-outline</v-icon>
              </div>
              <div>
                <p class="text-sm font-semibold text-white/80">Weekly Recap IA</p>
                <p class="mt-0.5 text-xs text-white/35 leading-relaxed">
                  Análisis semanal generado por inteligencia artificial.
                </p>
              </div>
            </div>

            <div class="flex items-start gap-4">
              <div
                class="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl"
                style="background: rgba(245,158,11,0.1); border: 1px solid rgba(245,158,11,0.15);"
              >
                <v-icon size="15" color="#f59e0b">mdi-brain</v-icon>
              </div>
              <div>
                <p class="text-sm font-semibold text-white/80">Detección de Anomalías</p>
                <p class="mt-0.5 text-xs text-white/35 leading-relaxed">
                  Alertas mensuales de tendencias clínicas relevantes.
                </p>
              </div>
            </div>
          </div>
        </div>

        <!-- Bottom: footer info -->
        <p class="text-[10px] tracking-wide text-white/15">
          WeSleep Technologies · Barcelona
        </p>
      </div>

      <!-- ─── RIGHT PANEL / MOBILE FULL ─── -->
      <div class="flex flex-1 items-center justify-center px-5 sm:px-8 py-12 lg:py-0">
        <div class="w-full max-w-sm">

          <!-- Mobile only: Logo mark -->
          <div class="mb-10 flex flex-col items-center gap-4 lg:hidden">
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

          <!-- Desktop: section label -->
          <div class="hidden lg:block mb-8">
            <h2 class="text-2xl font-bold tracking-tight text-white">Acceso al Panel</h2>
            <p class="mt-1.5 text-sm text-white/35">
              Selecciona un perfil de paciente para continuar.
            </p>
          </div>

          <!-- Login card (always styled, works on both mobile and desktop) -->
          <div
            class="overflow-hidden rounded-2xl px-6 py-7"
            style="background: #112240; border: 1px solid rgba(255,255,255,0.07);"
          >
            <!-- Card header (hidden on desktop since the section label above handles it) -->
            <div class="lg:hidden">
              <h2 class="text-[15px] font-semibold text-white">Acceso B2B</h2>
              <p class="mt-0.5 text-xs text-white/40">
                Selecciona un perfil de paciente para continuar.
              </p>
            </div>

            <div class="mt-6 lg:mt-0">
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
              class="mt-5 w-full rounded-xl py-4 text-sm font-bold transition-all active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40"
              style="background: #00e5a0; color: #091524;"
              :disabled="!isValid"
              @click="onSubmit"
            >
              Entrar al Panel
            </button>
          </div>

          <p class="mt-8 text-center text-[10px] tracking-wide text-white/15 lg:hidden">
            WeSleep Technologies · Barcelona
          </p>
        </div>
      </div>
    </div>
  </div>
</template>
