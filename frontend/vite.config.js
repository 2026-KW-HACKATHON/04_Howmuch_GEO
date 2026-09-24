import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
    plugins: [
        react(),
        tailwindcss(),
    ],
    server: {
        proxy: {
            '/vworld-api': {
                target: 'https://api.vworld.kr',
                changeOrigin: true,
                secure: false,
                rewrite: (path) => path.replace(/^\/vworld-api/, ''),
                configure: (proxy, options) => {
                    proxy.on('proxyReq', (proxyReq, req, res) => {
                        proxyReq.setHeader('Host', 'api.vworld.kr');
                    });
                },
            },
        },
    },
})
