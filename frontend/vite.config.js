import { defineConfig } from 'vite'

export default defineConfig({
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'https://your-backend-url.vercel.app',
        changeOrigin: true,
        secure: false
      }
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets'
  }
})