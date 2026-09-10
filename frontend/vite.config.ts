import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'


export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5179,
    host: '127.0.0.1',
    proxy: {
      '/v1': { target: 'http://127.0.0.1:8009', changeOrigin: true },
      '/health': { target: 'http://127.0.0.1:8009', changeOrigin: true },
      '/fm': {
        target: 'http://127.0.0.1:8062',
        changeOrigin: true,
        rewrite: p => p.replace(/^\/fm/, ''),
      },
    },
  },
})
