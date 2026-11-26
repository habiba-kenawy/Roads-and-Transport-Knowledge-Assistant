import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(import.meta.dirname, './src') } },
  // Port 5180 is in the backend's CORS list (5173 is used by other projects here). strictPort: fail instead of moving to a port CORS refuses.
  server: { port: 5180, strictPort: true },
  test: { include: ['src/**/*.test.ts'] },
  build: {
    rolldownOptions: {
      output: {
        // Keep the libraries in their own files: each stays under the size warning, and a change to our code does not reload them.
        codeSplitting: {
          groups: [
            { name: 'react', test: /node_modules\/(react|react-dom|scheduler)\// },
            { name: 'radix', test: /node_modules\/(radix-ui|@radix-ui)\// },
          ],
        },
      },
    },
  },
})
