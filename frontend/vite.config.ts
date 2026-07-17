import vue from "@vitejs/plugin-vue"
import { loadEnv } from "vite"
import { defineConfig } from "vitest/config"

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "")

  return {
    plugins: [vue()],
    server: {
      proxy: {
        "/api": {
          target: env.CIVICPULSE_API_PROXY_TARGET ?? "http://127.0.0.1:8000",
        },
      },
    },
    test: {
      environment: "jsdom",
    },
  }
})
