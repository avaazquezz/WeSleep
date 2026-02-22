<script setup lang="ts">
import axios from 'axios'
import type { ApexOptions } from 'apexcharts'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
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

const weeklyRecap = computed(() => {
  const w = weeklyData.value
  if (!w) return null
  return (w.ai_insight ?? w.weekly_recap ?? '').trim() || null
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
    foreColor: '#0f172a',
  },
  colors: ['#94a3b8', '#0ea5e9'], // slate-400, sky-500
  plotOptions: {
    bar: {
      horizontal: false,
      columnWidth: '45%',
      borderRadius: 8,
    },
  },
  dataLabels: { enabled: false },
  grid: { borderColor: '#e2e8f0' },
  legend: { position: 'top', horizontalAlign: 'left' },
  xaxis: {
    categories: ['Comparativa'],
    labels: { style: { colors: ['#334155'] } },
  },
  yaxis: {
    labels: {
      style: { colors: ['#334155'] },
      formatter: (val) => (Number.isFinite(val) ? Math.round(val).toString() : ''),
    },
  },
  tooltip: { theme: 'light' },
}

const hrvOptions = computed<ApexOptions>(() => ({
  ...baseChartOptions,
  title: {
    text: 'HRV (VFC) promedio',
    style: { fontSize: '14px', fontWeight: '600', color: '#0f172a' },
  },
}))

const deepOptions = computed<ApexOptions>(() => ({
  ...baseChartOptions,
  title: {
    text: 'Sueño profundo promedio (min)',
    style: { fontSize: '14px', fontWeight: '600', color: '#0f172a' },
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
  <v-app-bar color="white" elevation="1">
    <v-toolbar-title class="text-slate-900">
      {{ patientLabel }}
    </v-toolbar-title>
    <v-spacer />
    <v-btn variant="tonal" color="primary" @click="onLogout">
      Cerrar sesión
    </v-btn>
  </v-app-bar>

  <v-main class="bg-slate-50 min-h-screen">
    <v-container fluid class="py-8">
      <div class="mx-auto max-w-6xl px-2 sm:px-6">
        <div class="flex items-start justify-between gap-4">
          <div>
            <h1 class="text-2xl font-semibold tracking-tight text-slate-900">
              Panel Médico Preventivo
            </h1>
            <p class="mt-1 text-sm text-slate-600">
              Resumen semanal y alertas de tendencia para seguimiento clínico.
            </p>
          </div>
        </div>

        <div class="mt-6">
          <v-progress-linear
            v-if="isLoading"
            indeterminate
            color="primary"
            rounded
          />

          <v-alert
            v-else-if="errorMessage"
            type="error"
            variant="tonal"
            border="start"
            class="rounded-lg"
          >
            {{ errorMessage }}
          </v-alert>

          <v-alert
            v-else-if="emptyStateMessage"
            type="info"
            variant="tonal"
            border="start"
            class="rounded-lg"
          >
            {{ emptyStateMessage }}
          </v-alert>
        </div>

        <v-alert
          v-if="!isLoading && !errorMessage && monthlyAlertText"
          type="warning"
          variant="tonal"
          border="start"
          prominent
          class="mt-6 rounded-xl"
        >
          <div class="text-base font-semibold text-slate-900">
            Alerta mensual (IA)
          </div>
          <div class="mt-2 whitespace-pre-line text-slate-800">
            {{ monthlyAlertText }}
          </div>
        </v-alert>

        <v-card
          v-if="!isLoading && !errorMessage"
          class="mt-6 rounded-xl"
          elevation="2"
        >
          <v-card-title class="flex items-center gap-3">
            <v-icon icon="mdi-robot-outline" color="primary" />
            <span class="text-slate-900">Weekly Recap (IA)</span>
          </v-card-title>
          <v-card-text>
            <div v-if="weeklyRecap" class="whitespace-pre-line text-slate-700">
              {{ weeklyRecap }}
            </div>
            <v-alert
              v-else
              type="info"
              variant="tonal"
              border="start"
              class="rounded-lg"
            >
              Aún no hay suficiente información para generar un recap semanal.
              Necesitamos más registros de sueño (mínimo 14 días).
            </v-alert>
          </v-card-text>
        </v-card>

        <v-row v-if="!isLoading && !errorMessage" class="mt-2" dense>
          <v-col cols="12" md="6">
            <v-card class="rounded-xl" elevation="2">
              <v-card-title class="text-slate-900">
                HRV semanal
              </v-card-title>
              <v-card-subtitle class="text-slate-600">
                Semana pasada: {{ formatMaybeNumber(weeklyData?.previous_week.hrv_avg) }} ·
                Actual: {{ formatMaybeNumber(weeklyData?.current_week.hrv_avg) }}
              </v-card-subtitle>
              <v-card-text>
                <div v-if="hasWeeklyCharts">
                  <apexchart
                    type="bar"
                    height="260"
                    :options="hrvOptions"
                    :series="hrvSeries"
                  />
                </div>
                <v-alert
                  v-else
                  type="info"
                  variant="tonal"
                  border="start"
                  class="rounded-lg"
                >
                  Sin datos suficientes para mostrar la comparativa de HRV (VFC).
                </v-alert>
              </v-card-text>
            </v-card>
          </v-col>

          <v-col cols="12" md="6">
            <v-card class="rounded-xl" elevation="2">
              <v-card-title class="text-slate-900">
                Sueño profundo semanal
              </v-card-title>
              <v-card-subtitle class="text-slate-600">
                Semana pasada: {{ formatMaybeNumber(weeklyData?.previous_week.deep_minutes_avg, ' min') }} ·
                Actual: {{ formatMaybeNumber(weeklyData?.current_week.deep_minutes_avg, ' min') }}
              </v-card-subtitle>
              <v-card-text>
                <div v-if="hasWeeklyCharts">
                  <apexchart
                    type="bar"
                    height="260"
                    :options="deepOptions"
                    :series="deepSeries"
                  />
                </div>
                <v-alert
                  v-else
                  type="info"
                  variant="tonal"
                  border="start"
                  class="rounded-lg"
                >
                  Sin datos suficientes para mostrar la comparativa de sueño profundo.
                </v-alert>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
      </div>
    </v-container>
  </v-main>
</template>

