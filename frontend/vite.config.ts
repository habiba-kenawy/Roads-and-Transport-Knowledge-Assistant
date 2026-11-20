import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  // tailwindcss(): turns the utility classes we write into CSS (Tailwind 4 needs no config file)
  plugins: [react(), tailwindcss()],
  // "@/x" means "src/x", so imports do not climb with ../../..
  resolve: { alias: { '@': path.resolve(import.meta.dirname, './src') } },
  // 5180, not Vite's default 5173 (other projects use that one). strictPort: if it is busy, stop with an error instead of
  // silently moving to a port the backend CORS list does not allow
  server: { port: 5180, strictPort: true },
})
