//frontend/vite.config.js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: true, // Allow external connections
  },
  preview: {
    port: process.env.PORT || 3000, // Use PORT env variable for Render
    host: '0.0.0.0', // Must be '0.0.0.0' for Render
    allowedHosts: [
      'hospital-equipment-frontend.onrender.com',
      '.onrender.com' // Allow any subdomain of onrender.com
    ]
  },
  build: {
    outDir: 'dist',
    sourcemap: false, // Disable sourcemaps for production
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          utils: ['axios']
        }
      }
    }
  },
  define: {
    // Ensure environment variables are available
    'process.env': {}
  }
})