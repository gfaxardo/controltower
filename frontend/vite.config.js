import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // Producción: build para raíz del dominio (ej. http://162.55.214.109/)
  base: '/',
  server: {
    port: 5173,
    proxy: {
      '/api': {
        // Dev: backend local (uvicorn). Producción/otro: definir VITE_API_URL (ej. http://162.55.214.109:8000)
        target: process.env.VITE_API_URL || 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
        // Drill puede tardar hasta 5 min (statement_timeout 300s); proxy debe esperar 6 min
        timeout: 360000
      }
    }
  }
})





