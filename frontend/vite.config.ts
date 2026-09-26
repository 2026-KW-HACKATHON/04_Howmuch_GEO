import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
    plugins: [
        react(),
        tailwindcss(),
    ],
    server: {
    host: true, // 0.0.0.0 허용
    port: 5173,
    strictPort: true,
    allowedHosts: true, // 모든 외부 호스트(Codespaces 주소 포함) 허용
  },
})