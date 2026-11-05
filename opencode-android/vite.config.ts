import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  base: './',
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    allowedHosts: true,
  },
  build: {
    outDir: path.resolve(__dirname, 'android/app/src/main/assets/www'),
    emptyOutDir: true,
    target: 'es2020',
    sourcemap: false,
  },
});
