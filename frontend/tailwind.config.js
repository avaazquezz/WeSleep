/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        ws: {
          bg: '#091524',
          surface: '#112240',
          'surface-alt': '#0f1e38',
          green: '#00e5a0',
          sky: '#38bdf8',
          amber: '#f59e0b',
          red: '#ef4444',
        },
      },
      fontFamily: {
        mono: ['"SF Mono"', 'ui-monospace', '"Fira Code"', 'monospace'],
      },
    },
  },
  plugins: [],
}
