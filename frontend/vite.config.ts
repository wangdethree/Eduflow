import { fileURLToPath, URL } from 'node:url'
import vue from '@vitejs/plugin-vue'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [vue()],
    resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
    server: {
      port: 5173,
      proxy: {
        // 本地端口冲突时可通过环境变量切换后端地址。
        '/api': env.EDUFLOW_API_PROXY_TARGET || 'http://localhost:8000',
      },
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks: {
            vue: ['vue', 'vue-router', 'pinia', 'axios'],
            element: ['element-plus', '@element-plus/icons-vue'],
            charts: ['echarts'],
          },
        },
      },
    },
  }
})
