<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth'

const router = useRouter()
const { currentPatientName, logout } = useAuth()

const patientLabel = computed(() => currentPatientName.value ?? 'Paciente')

function onLogout() {
  logout()
  router.push('/login')
}
</script>

<template>
  <div class="min-h-screen bg-slate-50">
    <v-app-bar color="white" elevation="1">
      <v-toolbar-title class="text-slate-900">
        {{ patientLabel }}
      </v-toolbar-title>
      <v-spacer />
      <v-btn variant="tonal" color="primary" @click="onLogout">
        Cerrar sesión
      </v-btn>
    </v-app-bar>

    <v-main>
      <div class="mx-auto max-w-6xl px-6 py-10">
        <h1 class="text-2xl font-semibold tracking-tight text-slate-900">
          Panel Médico Preventivo
        </h1>
        <p class="mt-2 text-sm text-slate-600">
          Dashboard B2B (skeleton) para el MVP.
        </p>
      </div>
    </v-main>
  </div>
</template>

