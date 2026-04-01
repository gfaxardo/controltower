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
        // Weekly/margin-quality pueden superar 6 min (evidencia ~361s); proxy alineado con LONG_HTTP_TIMEOUT_MS en api.js
        timeout: 900000
      }
    }
  }
})





