import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Dev proxy target — override with VITE_API_PORT when the API runs on a
// side port (e.g. `VITE_API_PORT=8181 npm run dev` while production owns 8080).
const apiPort = process.env.VITE_API_PORT ?? '8080'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': `http://127.0.0.1:${apiPort}`,
    },
  },
})
