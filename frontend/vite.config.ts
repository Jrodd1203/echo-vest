import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/stream': 'http://localhost:8081',
      '/raw':    'http://localhost:8081',
      '/depth':  'http://localhost:8081',
      '/ws': { target: 'ws://localhost:8081', ws: true },
    },
  },
})
