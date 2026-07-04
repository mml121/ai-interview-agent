import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const devPort = Number(env.VITE_DEV_PORT || 5173)

  return {
    plugins: [react()],
    server: {
      host: '127.0.0.1',
      port: devPort,
      strictPort: true,
    },
  }
})
