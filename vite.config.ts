import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';
import { readFileSync } from 'node:fs';

const packageVersion = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8')).version as string;

export default defineConfig({
  // The desktop shell opens dist/index.html via file://; relative assets keep
  // both the Vite server and the packaged PyInstaller bundle working.
  base: './',
  plugins: [react()],
  define: { 'import.meta.env.VITE_CIRAVA_VERSION': JSON.stringify(packageVersion) },
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
});
