<script setup lang="ts">
import axios from 'axios'
import type { ApexOptions } from 'apexcharts'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { predictOptimalWakeup } from '../api/alarm'
import { getMonthlyAnomaly, getWeeklyInsights } from '../api/insights'
import { useAuth } from '../composables/useAuth'

type AggregateStats = {
  hrv_avg: number | null
  deep_minutes_avg: number | null
  efficiency_avg: number | null
}

type WeeklyInsightsResponse = {
  patient_id: string
  previous_week: AggregateStats
  current_week: AggregateStats
  hrv_trend_percent: number | null
  deep_trend_percent: number | null
  efficiency_trend_percent: number | null
  daily: Array<{
    date: string
    hrv: number | null
    deep_minutes: number | null
    efficiency: number | null
  }>
  weekly_recap: string
  ai_insight?: string
}

type MonthlyInsightsOk = {
  status: 'ok'
  alert: string | null
}

const router = useRouter()
const { currentPatientId, currentPatientName, logout } = useAuth()

const patientLabel = computed(() => currentPatientName.value ?? 'Paciente')

const isLoading = ref(true)
const weeklyData = ref<WeeklyInsightsResponse | null>(null)
const monthlyAlert = ref<MonthlyInsightsOk | null>(null)
const errorMessage = ref<string | null>(null)
const emptyStateMessage = ref<string | null>(null)

const targetTime = ref('07:30')
const predictedTime = ref<string | null>(null)
const alarmReason = ref<string | null>(null)
const isPredicting = ref(false)

const weeklyRecap = computed(() => {
  const w = weeklyData.value
  if (!w) return null
  return (w.ai_insight ?? w.weekly_recap ?? '').trim() || null
})

const weeklyRecapSections = computed(() => {
  const text = weeklyRecap.value
  if (!text) return null
  const defs = [
    { key: 'Resumen', icon: 'mdi-chart-line-variant', color: '#38bdf8' },
    { key: 'Lectura', icon: 'mdi-eye-outline', color: '#a78bfa' },
    { key: 'Acción', icon: 'mdi-lightning-bolt-outline', color: '#00e5a0' },
  ]
  const result: { key: string; icon: string; color: string; text: string }[] = []
  for (let i = 0; i < defs.length; i++) {
    const { key, icon, color } = defs[i]
    const startRe = new RegExp(`${key}:[ \t]*`, 'i')
    const startMatch = text.match(startRe)
    if (!startMatch || startMatch.index === undefined) continue
    const contentStart = startMatch.index + startMatch[0].length
    let contentEnd = text.length
    for (let j = i + 1; j < defs.length; j++) {
      const nextRe = new RegExp(`${defs[j].key}:[ \t]*`, 'i')
      const nextMatch = text.match(nextRe)
      if (nextMatch && nextMatch.index !== undefined && nextMatch.index < contentEnd) {
        contentEnd = nextMatch.index
      }
    }
    result.push({ key, icon, color, text: text.slice(contentStart, contentEnd).trim() })
  }
  return result.length > 0 ? result : null
})

const hasWeeklyCharts = computed(() => {
  const w = weeklyData.value
  if (!w) return false
  return (
    w.previous_week.hrv_avg != null &&
    w.current_week.hrv_avg != null &&
    w.previous_week.deep_minutes_avg != null &&
    w.current_week.deep_minutes_avg != null
  )
})

const hrvSeries = computed(() => {
  const w = weeklyData.value
  if (!w) return []
  return [
    { name: 'Semana pasada', data: [w.previous_week.hrv_avg ?? 0] },
    { name: 'Semana actual', data: [w.current_week.hrv_avg ?? 0] },
  ]
})

const deepSeries = computed(() => {
  const w = weeklyData.value
  if (!w) return []
  return [
    { name: 'Semana pasada', data: [w.previous_week.deep_minutes_avg ?? 0] },
    { name: 'Semana actual', data: [w.current_week.deep_minutes_avg ?? 0] },
  ]
})

const baseChartOptions: ApexOptions = {
  chart: {
    type: 'bar',
    toolbar: { show: false },
    foreColor: '#64748b',
    background: 'transparent',
  },
  colors: ['#1e3a5f', '#00e5a0'],
  plotOptions: {
    bar: {
      horizontal: false,
      columnWidth: '45%',
      borderRadius: 8,
    },
  },
  dataLabels: { enabled: false },
  grid: { borderColor: 'rgba(255,255,255,0.05)' },
  legend: { position: 'top', horizontalAlign: 'left' },
  xaxis: {
    categories: ['Comparativa'],
    labels: { style: { colors: ['#64748b'] } },
  },
  yaxis: {
    labels: {
      style: { colors: ['#64748b'] },
      formatter: (val) => (Number.isFinite(val) ? Math.round(val).toString() : ''),
    },
  },
  tooltip: { theme: 'dark' },
}

const hrvOptions = computed<ApexOptions>(() => ({
  ...baseChartOptions,
  title: {
    text: 'HRV (VFC) promedio',
    style: { fontSize: '13px', fontWeight: '600', color: '#94a3b8' },
  },
}))

const deepOptions = computed<ApexOptions>(() => ({
  ...baseChartOptions,
  title: {
    text: 'Sueño profundo promedio (min)',
    style: { fontSize: '13px', fontWeight: '600', color: '#94a3b8' },
  },
}))

const monthlyAlertText = computed(() => {
  const raw = monthlyAlert.value?.alert ?? null
  return raw?.trim() || null
})

function formatMaybeNumber(v: number | null | undefined, suffix = '') {
  if (v == null || !Number.isFinite(v)) return '—'
  return `${v.toFixed(1)}${suffix}`
}

function resolveErrorMessage(err: unknown) {
  if (axios.isAxiosError(err)) {
    const detail = (err.response?.data as any)?.detail
    if (typeof detail === 'string' && detail.trim()) return detail.trim()
    if (typeof err.message === 'string' && err.message.trim()) return err.message.trim()
  }
  return 'No se pudieron cargar los insights. Intenta de nuevo en unos segundos.'
}

function resolveAlarmErrorMessage(err: unknown) {
  if (axios.isAxiosError(err)) {
    const detail = (err.response?.data as any)?.detail
    if (typeof detail === 'string' && detail.trim()) return detail.trim()
    if (typeof err.message === 'string' && err.message.trim()) return err.message.trim()
  }
  return 'No pudimos calcular la ventana óptima. Intenta nuevamente en unos segundos.'
}

async function handlePredictAlarm() {
  const patientId = currentPatientId.value
  if (!patientId) {
    predictedTime.value = null
    alarmReason.value = 'Necesitamos un paciente activo para calcular el despertador.'
    router.push('/login')
    return
  }

  isPredicting.value = true
  predictedTime.value = null
  alarmReason.value = null

  try {
    const res = await predictOptimalWakeup(patientId, targetTime.value)
    predictedTime.value = res.optimal_wakeup_time
    alarmReason.value = res.reason
  } catch (err) {
    predictedTime.value = null
    alarmReason.value = resolveAlarmErrorMessage(err)
  } finally {
    isPredicting.value = false
  }
}

function onLogout() {
  logout()
  router.push('/login')
}

onMounted(async () => {
  isLoading.value = true
  errorMessage.value = null
  emptyStateMessage.value = null

  const patientId = currentPatientId.value
  if (!patientId) {
    isLoading.value = false
    router.push('/login')
    return
  }

  try {
    const [weekly, monthly] = await Promise.all([
      getWeeklyInsights(patientId),
      getMonthlyAnomaly(patientId),
    ])
    weeklyData.value = weekly as WeeklyInsightsResponse
    monthlyAlert.value = monthly as MonthlyInsightsOk
  } catch (err) {
    if (axios.isAxiosError(err) && err.response?.status === 400) {
      const detail = (err.response?.data as any)?.detail
      if (typeof detail === 'string' && detail.includes('Datos insuficientes')) {
        weeklyData.value = null
        monthlyAlert.value = null
        emptyStateMessage.value = detail.trim()
      } else {
        errorMessage.value = resolveErrorMessage(err)
      }
    } else {
      errorMessage.value = resolveErrorMessage(err)
    }
  } finally {
    isLoading.value = false
  }
})
</script>

<template>
  <!-- ─── APP BAR ─── -->
  <v-app-bar
    elevation="0"
    class="!px-0"
    style="background: #091524; border-bottom: 1px solid rgba(255,255,255,0.05);"
  >
    <div class="flex w-full items-center px-4 sm:px-6 lg:px-8">
      <!-- Logo -->
      <div class="flex items-center gap-3 shrink-0">
        <div
          class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white"
          style="background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.1);"
        >
          W
        </div>
        <span class="hidden sm:block text-xs font-bold tracking-[0.15em] uppercase text-white/30">
          WeSleep
        </span>
      </div>

      <!-- Separator on desktop -->
      <div
        class="hidden lg:block mx-4 h-4 w-px"
        style="background: rgba(255,255,255,0.08);"
      />

      <!-- Patient label -->
      <div class="flex items-center gap-2 ml-3 sm:ml-0">
        <div
          class="hidden lg:flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[9px] font-bold text-white/60"
          style="background: rgba(0,229,160,0.12); border: 1px solid rgba(0,229,160,0.2);"
        >
          P
        </div>
        <span class="text-xs font-medium text-white/60 max-w-[160px] sm:max-w-none truncate">
          {{ patientLabel }}
        </span>
      </div>

      <div class="flex-1" />

      <!-- Desktop nav hint -->
      <div class="hidden lg:flex items-center gap-2 mr-3">
        <span class="text-[10px] text-white/20 font-medium tracking-wide uppercase">Panel Clínico</span>
      </div>

      <!-- Logout -->
      <button
        class="flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-medium text-white/35 transition hover:text-white/65 hover:bg-white/5 active:scale-95"
        @click="onLogout"
      >
        <v-icon size="14">mdi-logout</v-icon>
        <span class="hidden sm:inline">Salir</span>
      </button>
    </div>
  </v-app-bar>

  <!-- ─── MAIN ─── -->
  <v-main style="background: #091524; min-height: 100vh;">
    <div class="px-4 sm:px-6 lg:px-8 py-6 lg:py-8 mx-auto w-full max-w-screen-xl">

      <!-- Page header -->
      <div class="mb-6 lg:mb-8">
        <p class="text-[10px] font-bold uppercase tracking-[0.2em] text-white/25">
          Panel Clínico
        </p>
        <h1 class="mt-1 text-xl lg:text-2xl font-bold tracking-tight text-white">
          Seguimiento Preventivo
        </h1>
      </div>

      <!-- Loading bar (full width) -->
      <div class="mb-4">
        <v-progress-linear
          v-if="isLoading"
          indeterminate
          color="#00e5a0"
          rounded
          height="2"
        />
      </div>

      <!-- ─── ERROR / EMPTY STATE ─── -->
      <div
        v-if="!isLoading && errorMessage"
        class="mb-6 rounded-2xl p-4"
        style="background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.15);"
      >
        <div class="flex items-start gap-3">
          <v-icon size="17" class="mt-px shrink-0" color="#ef4444">mdi-alert-circle-outline</v-icon>
          <p class="text-sm text-red-400 leading-relaxed">{{ errorMessage }}</p>
        </div>
      </div>

      <div
        v-else-if="!isLoading && emptyStateMessage"
        class="mb-6 rounded-2xl p-4"
        style="background: rgba(56,189,248,0.07); border: 1px solid rgba(56,189,248,0.13);"
      >
        <div class="flex items-start gap-3">
          <v-icon size="17" class="mt-px shrink-0" color="#38bdf8">mdi-information-outline</v-icon>
          <p class="text-sm text-sky-300/75 leading-relaxed">{{ emptyStateMessage }}</p>
        </div>
      </div>

      <!-- ─── MAIN GRID ─── -->
      <!-- Mobile: single column stack | Desktop: 2-column asymmetric grid -->
      <div class="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px] xl:grid-cols-[minmax(0,1fr)_400px] gap-5 lg:gap-6 lg:items-start">

        <!-- ══════════ LEFT COLUMN ══════════ -->
        <div class="flex flex-col gap-5">

          <!-- ─── SMART ALARM WIDGET ─── -->
          <div
            class="overflow-hidden rounded-2xl"
            style="background: linear-gradient(145deg, #112240 0%, #0f1e38 100%); border: 1px solid rgba(255,255,255,0.08);"
          >
            <!-- Header -->
            <div class="flex items-center justify-between px-5 pt-5">
              <p class="text-[10px] font-bold uppercase tracking-[0.22em] text-white/35">
                WeSleep Smart Alarm
              </p>
              <v-icon size="14" style="color: rgba(0,229,160,0.5);">mdi-alarm</v-icon>
            </div>

            <!-- Time display -->
            <div class="px-5 pb-1 pt-3">
              <div v-if="predictedTime" class="flex items-baseline gap-3">
                <span class="font-mono text-5xl lg:text-6xl font-extrabold tracking-tight text-white">
                  {{ predictedTime }}
                </span>
                <span class="font-mono text-sm text-white/25">/ {{ targetTime }}</span>
              </div>
              <div v-else class="flex items-baseline gap-2">
                <span class="font-mono text-5xl lg:text-6xl font-extrabold tracking-tight text-white/15">
                  -- : --
                </span>
              </div>
              <p
                v-if="predictedTime && alarmReason"
                class="mt-2 text-xs leading-relaxed text-white/50"
              >
                {{ alarmReason }}
              </p>
              <p v-else-if="!predictedTime && !alarmReason" class="mt-2 text-xs text-white/30">
                Indica tu hora objetivo y calcula la ventana óptima de despertar.
              </p>
            </div>

            <!-- Alarm error inline -->
            <div
              v-if="!predictedTime && alarmReason"
              class="mx-5 mt-2 rounded-xl p-3"
              style="background: rgba(239,68,68,0.09); border: 1px solid rgba(239,68,68,0.18);"
            >
              <p class="text-xs text-red-400">{{ alarmReason }}</p>
            </div>

            <div class="mx-5 mt-4" style="border-top: 1px solid rgba(255,255,255,0.05);" />

            <!-- Input row -->
            <div class="flex items-center gap-3 px-5 py-4">
              <div class="flex-1">
                <label class="mb-1 block text-[10px] font-semibold uppercase tracking-widest text-white/30">
                  Hora objetivo
                </label>
                <input
                  v-model="targetTime"
                  type="time"
                  class="h-11 w-full rounded-xl px-3.5 font-mono text-base font-semibold text-white transition focus:outline-none focus:ring-1 focus:ring-ws-green/40"
                  style="background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.09); color-scheme: dark;"
                />
              </div>
              <div class="shrink-0 pt-5">
                <button
                  class="flex h-11 items-center gap-2 rounded-xl px-5 text-sm font-bold transition-all active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
                  style="background: #00e5a0; color: #091524;"
                  :disabled="isPredicting"
                  @click="handlePredictAlarm"
                >
                  <svg v-if="isPredicting" class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  <v-icon v-else size="15">mdi-calculator-variant-outline</v-icon>
                  {{ isPredicting ? 'Calculando…' : 'Calcular' }}
                </button>
              </div>
            </div>
          </div>

          <!-- ─── WEEKLY RECAP (AI) ─── -->
          <div
            v-if="!isLoading && !errorMessage"
            class="overflow-hidden rounded-2xl"
            style="background: #112240; border: 1px solid rgba(255,255,255,0.07);"
          >
            <div class="p-5 lg:p-6">
              <div class="mb-4 flex items-center gap-2.5">
                <div
                  class="flex h-8 w-8 items-center justify-center rounded-xl"
                  style="background: rgba(56,189,248,0.1);"
                >
                  <v-icon size="15" color="#38bdf8">mdi-robot-outline</v-icon>
                </div>
                <p class="text-[10px] font-bold uppercase tracking-[0.2em] text-white/40">
                  Weekly Recap · IA
                </p>
              </div>

              <!-- Structured sections: Resumen / Lectura / Acción -->
              <template v-if="weeklyRecapSections">
                <!-- On desktop: 3 sections in a grid for wider layout -->
                <div class="lg:grid lg:grid-cols-3 lg:gap-5 flex flex-col gap-0">
                  <div
                    v-for="(section, idx) in weeklyRecapSections"
                    :key="section.key"
                    class="lg:border-l lg:pl-4 first:lg:border-l-0 first:lg:pl-0"
                    :style="idx > 0 ? 'border-color: rgba(255,255,255,0.06);' : ''"
                  >
                    <!-- Mobile divider between sections -->
                    <div
                      v-if="idx > 0"
                      class="my-4 lg:hidden"
                      style="border-top: 1px solid rgba(255,255,255,0.05);"
                    />
                    <div class="mb-2 flex items-center gap-2">
                      <v-icon size="13" :color="section.color">{{ section.icon }}</v-icon>
                      <span
                        class="text-[10px] font-bold uppercase tracking-[0.18em]"
                        :style="{ color: section.color, opacity: '0.8' }"
                      >{{ section.key }}</span>
                    </div>
                    <p class="text-sm leading-[1.7] text-white/65">{{ section.text }}</p>
                  </div>
                </div>
              </template>

              <p v-else-if="weeklyRecap" class="text-sm leading-relaxed text-white/65 whitespace-pre-line">
                {{ weeklyRecap }}
              </p>
              <p v-else class="text-xs italic text-white/25">
                Sin datos suficientes aún. Necesitamos un mínimo de 14 días de registros.
              </p>
            </div>
          </div>

          <!-- ─── CHARTS (side-by-side on all sizes) ─── -->
          <div
            v-if="!isLoading && !errorMessage"
            class="grid grid-cols-1 sm:grid-cols-2 gap-4 lg:gap-5"
          >
            <!-- HRV Chart -->
            <div
              class="overflow-hidden rounded-2xl"
              style="background: #112240; border: 1px solid rgba(255,255,255,0.07);"
            >
              <div class="px-5 pt-4 pb-0">
                <p class="text-[10px] font-bold uppercase tracking-[0.2em] text-white/40">
                  HRV Semanal
                </p>
                <p class="mt-0.5 text-[11px] text-white/25">
                  Pasada: {{ formatMaybeNumber(weeklyData?.previous_week.hrv_avg) }} ·
                  Actual: {{ formatMaybeNumber(weeklyData?.current_week.hrv_avg) }}
                </p>
              </div>
              <div v-if="hasWeeklyCharts" class="px-1 pb-2">
                <apexchart type="bar" height="220" :options="hrvOptions" :series="hrvSeries" />
              </div>
              <div v-else class="px-5 pb-5 pt-3">
                <p class="text-xs italic text-white/20">Sin datos suficientes.</p>
              </div>
            </div>

            <!-- Deep Sleep Chart -->
            <div
              class="overflow-hidden rounded-2xl"
              style="background: #112240; border: 1px solid rgba(255,255,255,0.07);"
            >
              <div class="px-5 pt-4 pb-0">
                <p class="text-[10px] font-bold uppercase tracking-[0.2em] text-white/40">
                  Sueño Profundo Semanal
                </p>
                <p class="mt-0.5 text-[11px] text-white/25">
                  Pasada: {{ formatMaybeNumber(weeklyData?.previous_week.deep_minutes_avg, ' min') }} ·
                  Actual: {{ formatMaybeNumber(weeklyData?.current_week.deep_minutes_avg, ' min') }}
                </p>
              </div>
              <div v-if="hasWeeklyCharts" class="px-1 pb-2">
                <apexchart type="bar" height="220" :options="deepOptions" :series="deepSeries" />
              </div>
              <div v-else class="px-5 pb-5 pt-3">
                <p class="text-xs italic text-white/20">Sin datos suficientes.</p>
              </div>
            </div>
          </div>

        </div>
        <!-- ══════════ END LEFT COLUMN ══════════ -->

        <!-- ══════════ RIGHT COLUMN (sidebar) ══════════ -->
        <div class="flex flex-col gap-5">

          <!-- ─── MONTHLY AI ALERT ─── -->
          <div
            v-if="!isLoading && !errorMessage && monthlyAlertText"
            class="overflow-hidden rounded-2xl"
            style="background: rgba(245,158,11,0.07); border: 1px solid rgba(245,158,11,0.18);"
          >
            <div class="flex items-start gap-4 p-5">
              <div
                class="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
                style="background: rgba(245,158,11,0.12);"
              >
                <v-icon size="17" color="#f59e0b">mdi-brain</v-icon>
              </div>
              <div class="min-w-0 flex-1">
                <p class="text-[10px] font-bold uppercase tracking-[0.18em] text-amber-400/65">
                  Análisis IA · Mensual
                </p>
                <p class="mt-1 text-sm font-semibold leading-snug text-amber-100/90">
                  Tendencia detectada en tu sueño
                </p>
                <p class="mt-1.5 whitespace-pre-line text-xs leading-relaxed text-white/50">
                  {{ monthlyAlertText }}
                </p>
              </div>
            </div>
          </div>

          <!-- ─── STATS CARDS ─── -->
          <div
            v-if="!isLoading && !errorMessage && weeklyData"
            class="overflow-hidden rounded-2xl"
            style="background: #112240; border: 1px solid rgba(255,255,255,0.07);"
          >
            <div class="px-5 pt-4 pb-1">
              <p class="text-[10px] font-bold uppercase tracking-[0.2em] text-white/40 mb-3">
                Métricas Semanales
              </p>
              <div class="grid grid-cols-3 lg:grid-cols-1 gap-3 pb-4">
                <!-- HRV stat -->
                <div
                  class="rounded-xl p-3 lg:p-4 flex lg:flex-row flex-col lg:items-center lg:justify-between items-start gap-1 lg:gap-0"
                  style="background: rgba(56,189,248,0.06); border: 1px solid rgba(56,189,248,0.1);"
                >
                  <div>
                    <p class="text-[9px] lg:text-[10px] font-bold uppercase tracking-widest text-sky-400/60">HRV</p>
                    <p class="font-mono text-lg lg:text-xl font-bold text-white/90 leading-tight">
                      {{ formatMaybeNumber(weeklyData.current_week.hrv_avg) }}
                      <span class="text-xs text-white/30">ms</span>
                    </p>
                  </div>
                  <div
                    v-if="weeklyData.hrv_trend_percent != null"
                    class="text-[11px] font-semibold"
                    :style="{ color: (weeklyData.hrv_trend_percent ?? 0) >= 0 ? '#00e5a0' : '#ef4444' }"
                  >
                    {{ (weeklyData.hrv_trend_percent ?? 0) >= 0 ? '+' : '' }}{{ weeklyData.hrv_trend_percent?.toFixed(1) }}%
                  </div>
                </div>

                <!-- Deep Sleep stat -->
                <div
                  class="rounded-xl p-3 lg:p-4 flex lg:flex-row flex-col lg:items-center lg:justify-between items-start gap-1 lg:gap-0"
                  style="background: rgba(0,229,160,0.05); border: 1px solid rgba(0,229,160,0.1);"
                >
                  <div>
                    <p class="text-[9px] lg:text-[10px] font-bold uppercase tracking-widest text-ws-green/60">Profundo</p>
                    <p class="font-mono text-lg lg:text-xl font-bold text-white/90 leading-tight">
                      {{ formatMaybeNumber(weeklyData.current_week.deep_minutes_avg) }}
                      <span class="text-xs text-white/30">min</span>
                    </p>
                  </div>
                  <div
                    v-if="weeklyData.deep_trend_percent != null"
                    class="text-[11px] font-semibold"
                    :style="{ color: (weeklyData.deep_trend_percent ?? 0) >= 0 ? '#00e5a0' : '#ef4444' }"
                  >
                    {{ (weeklyData.deep_trend_percent ?? 0) >= 0 ? '+' : '' }}{{ weeklyData.deep_trend_percent?.toFixed(1) }}%
                  </div>
                </div>

                <!-- Efficiency stat -->
                <div
                  class="rounded-xl p-3 lg:p-4 flex lg:flex-row flex-col lg:items-center lg:justify-between items-start gap-1 lg:gap-0"
                  style="background: rgba(167,139,250,0.05); border: 1px solid rgba(167,139,250,0.1);"
                >
                  <div>
                    <p class="text-[9px] lg:text-[10px] font-bold uppercase tracking-widest" style="color: rgba(167,139,250,0.6);">Eficiencia</p>
                    <p class="font-mono text-lg lg:text-xl font-bold text-white/90 leading-tight">
                      {{ formatMaybeNumber(weeklyData.current_week.efficiency_avg) }}
                      <span class="text-xs text-white/30">%</span>
                    </p>
                  </div>
                  <div
                    v-if="weeklyData.efficiency_trend_percent != null"
                    class="text-[11px] font-semibold"
                    :style="{ color: (weeklyData.efficiency_trend_percent ?? 0) >= 0 ? '#00e5a0' : '#ef4444' }"
                  >
                    {{ (weeklyData.efficiency_trend_percent ?? 0) >= 0 ? '+' : '' }}{{ weeklyData.efficiency_trend_percent?.toFixed(1) }}%
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- ─── EMPTY sidebar placeholder when no data ─── -->
          <div
            v-if="!isLoading && !errorMessage && !weeklyData && !monthlyAlertText"
            class="rounded-2xl p-6 flex flex-col items-center justify-center text-center"
            style="background: #112240; border: 1px solid rgba(255,255,255,0.06); min-height: 140px;"
          >
            <v-icon size="28" style="color: rgba(255,255,255,0.08);" class="mb-3">mdi-moon-waning-crescent</v-icon>
            <p class="text-xs text-white/20">Sin datos de métricas disponibles</p>
          </div>

          <!-- ─── QUICK INFO CARD ─── -->
          <div
            class="overflow-hidden rounded-2xl px-5 py-4"
            style="background: rgba(0,229,160,0.04); border: 1px solid rgba(0,229,160,0.08);"
          >
            <p class="text-[10px] font-bold uppercase tracking-[0.2em] text-ws-green/40 mb-2">
              Basado en
            </p>
            <p class="text-xs text-white/45 leading-relaxed">
              7 noches históricas (últimos 7 días) y puntuación por fases minuto a minuto.
            </p>
          </div>

        </div>
        <!-- ══════════ END RIGHT COLUMN ══════════ -->

      </div>

      <!-- Bottom spacer -->
      <div class="h-8 lg:h-12" />
    </div>
  </v-main>
</template>
