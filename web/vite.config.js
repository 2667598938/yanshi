import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// https://vite.dev/config/
const proxy = {
  // 所有后端接口代理到本地 FastAPI（生产由 Nginx 同源托管，无需跨域）
  '/api': {
    target: 'http://127.0.0.1:8000',
    changeOrigin: true,
  },
  '/health': {
    target: 'http://127.0.0.1:8000',
    changeOrigin: true,
  },
}

// 本地内测时通过 Cloudflare Tunnel / ngrok 暴露，需要放行对应的隧道域名
const tunnelHosts = ['.trycloudflare.com', '.ngrok-free.app', '.lhr.life', '.localhost.run']

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 27341,
    strictPort: true,
    allowedHosts: tunnelHosts,
    proxy,
  },
  preview: {
    port: 4173,
    strictPort: true,
    allowedHosts: tunnelHosts,
    proxy,
  },
})
