import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // ECharts + import desde echarts-for-react/esm/core: fuerza pre-bundle estable (evita 504 Outdated Optimize Dep).
  optimizeDeps: {
    include: ['echarts', 'echarts-for-react', 'echarts-for-react/esm/core', 'tslib'],
  },
  // Producción: build para raíz del dominio (ej. http://162.55.214.109/)
  base: '/',
  server: {
    port: 5173,
    // Necesario para React Router en dev: redirige cualquier ruta a index.html
    historyApiFallback: true,
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





