import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// ── Vite Config ──────────────────────────────────────────────────────────────
// KEY: The `proxy` block solves the Day 8 CORS problem entirely.
// All requests to /api/* in React dev mode are forwarded to the Quart backend
// at localhost:5000. No CORS headers needed in the browser — the proxy handles it.
// ─────────────────────────────────────────────────────────────────────────────
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
    },
  },
});