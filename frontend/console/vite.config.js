import {defineConfig} from 'vite';

export default defineConfig({
  base: '/console/',
  server: {host: '127.0.0.1', port: 5173, strictPort: false},
  build: {outDir: 'dist', emptyOutDir: true, sourcemap: false},
});
