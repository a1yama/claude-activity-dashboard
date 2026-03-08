/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const apiPort = process.env.DATASETTE_PORT || '8765';
const serverPort = Number(process.env.VITE_PORT || '5173');

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: serverPort,
    proxy: {
      '/api': {
        target: `http://localhost:${apiPort}`,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  build: {
    outDir: '../static',
    emptyOutDir: true,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    css: false,
  },
})
