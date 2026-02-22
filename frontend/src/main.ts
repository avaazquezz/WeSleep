import { createApp } from 'vue'
import App from './App.vue'
import './style.css'

import VueApexCharts from 'vue3-apexcharts'

import 'vuetify/styles'
import '@mdi/font/css/materialdesignicons.css'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import { aliases, mdi } from 'vuetify/iconsets/mdi'

import router from './router'

const vuetify = createVuetify({
  components,
  directives,
  icons: {
    defaultSet: 'mdi',
    aliases,
    sets: { mdi },
  },
})

const app = createApp(App)
app.use(router)
app.use(vuetify)
app.use(VueApexCharts)
app.mount('#app')
