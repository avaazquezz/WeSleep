<script setup lang="ts">
import { ref } from 'vue'

const count = ref(0)
</script>

<template>
  <div class="mx-auto max-w-5xl px-6 py-10">
    <div class="flex items-center justify-between gap-4">
      <div>
        <h1 class="text-2xl font-semibold tracking-tight text-slate-900">
          WeSleep B2B
        </h1>
        <p class="mt-1 text-sm text-slate-600">
          Vue 3 + Vite + TypeScript + Tailwind + Vuetify 3
        </p>
      </div>

      <div class="flex items-center gap-3">
        <v-btn color="primary" variant="flat" @click="count++">
          Count: {{ count }}
        </v-btn>
        <v-btn variant="tonal" @click="count = 0">Reset</v-btn>
      </div>
    </div>

    <v-card class="mt-8" variant="elevated">
      <v-card-title class="text-base">Next steps</v-card-title>
      <v-card-text>
        <ul class="list-disc pl-5 text-sm text-slate-700 space-y-1">
          <li>Crea tus rutas en <code class="font-mono">src/router</code>.</li>
          <li>
            Usa tu cliente HTTP en <code class="font-mono">src/api/axios.ts</code>.
          </li>
          <li>Levanta todo con <code class="font-mono">docker compose up</code>.</li>
        </ul>
      </v-card-text>
    </v-card>
  </div>
</template>

