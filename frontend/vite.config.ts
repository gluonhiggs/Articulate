import fs from 'fs'
import path from 'path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const certPath = path.resolve(__dirname, '../certs/cert.pem')
const keyPath = path.resolve(__dirname, '../certs/key.pem')
const useHttps = fs.existsSync(certPath)

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    https: useHttps ? { cert: certPath, key: keyPath } : undefined,
    proxy: {
      '/api': {
        target: `http${useHttps ? 's' : ''}://127.0.0.1:8000`,
        secure: false, // accept self-signed certs in dev proxy
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
