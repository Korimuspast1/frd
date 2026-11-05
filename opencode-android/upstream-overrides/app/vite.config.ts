import { defineConfig } from "vite"
import desktopPlugin, { channel } from "./vite.js"
import { icons } from "./vite.icons"

export default defineConfig({
  plugins: [desktopPlugin, icons(channel)] as any,
  server: {
    host: "0.0.0.0",
    allowedHosts: true,
    port: 3000,
  },
  build: {
    assetsDir: "_assets",
    target: "esnext",
    sourcemap: false,
  },
})
