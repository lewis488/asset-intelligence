import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/auth': 'http://localhost:8001',
      '/assets': 'http://localhost:8001',
      '/analysis': 'http://localhost:8001',
      '/vaisala': 'http://localhost:8001',
      '/health': 'http://localhost:8001',
      '^/admin/(authorities|users|data-overview)(/|$)': 'http://localhost:8001',
    },
  },
})
