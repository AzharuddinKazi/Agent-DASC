import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5174,
    strictPort: true,
  },
  build: {
    rollupOptions: {
      // Two separate bundles from two separate HTML entries — the admin panel
      // (admin.html -> src/admin/) is a standalone app, not a view inside App.jsx's
      // SPA. Same repo/build tool, same design system, but its own login and its own
      // output chunk; it doesn't ship inside the main app's JS at all.
      input: {
        main: path.resolve(__dirname, "index.html"),
        admin: path.resolve(__dirname, "admin.html"),
      },
    },
  },
})