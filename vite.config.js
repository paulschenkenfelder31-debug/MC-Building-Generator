import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    host: '0.0.0.0',
    port: Number(process.env.PORT || 3000),
    strictPort: true,
    proxy: { '/api': `http://127.0.0.1:${process.env.BLOCKWRIGHT_API_PORT || 8000}` },
  },
  build: { rollupOptions: { output: { manualChunks: { 'three-core': ['three'] } } } },
});
