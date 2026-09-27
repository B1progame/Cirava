import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';
import { readFileSync } from 'node:fs';
import { loadEnv } from 'vite';

const packageVersion = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8')).version as string;

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  const configuredChannel = process.env.VITE_CIRAVA_APP_CHANNEL || env.VITE_CIRAVA_APP_CHANNEL;
  const configuredVersion = process.env.VITE_CIRAVA_APP_VERSION || env.VITE_CIRAVA_APP_VERSION || packageVersion;
  const repository = process.env.VITE_CIRAVA_GITHUB_REPOSITORY || env.VITE_CIRAVA_GITHUB_REPOSITORY || 'B1progame/Cirava';
  const channel = configuredChannel === 'beta'
    ? 'beta'
    : configuredChannel === 'release'
      ? 'release'
      : /-(?:[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)/.test(packageVersion)
        ? 'beta'
        : 'release';

  return {
  // The desktop shell opens dist/index.html via file://; relative assets keep
  // both the Vite server and the packaged PyInstaller bundle working.
  base: './',
  plugins: [react()],
  define: {
    'import.meta.env.VITE_CIRAVA_VERSION': JSON.stringify(packageVersion),
    'import.meta.env.VITE_CIRAVA_APP_VERSION': JSON.stringify(configuredVersion),
    'import.meta.env.VITE_CIRAVA_APP_CHANNEL': JSON.stringify(channel),
    'import.meta.env.VITE_CIRAVA_STABLE_MANIFEST_URL': JSON.stringify(process.env.VITE_CIRAVA_STABLE_MANIFEST_URL || env.VITE_CIRAVA_STABLE_MANIFEST_URL || `https://github.com/${repository}/releases/latest/download/update-manifest.json`),
    'import.meta.env.VITE_CIRAVA_BETA_RELEASES_API_URL': JSON.stringify(process.env.VITE_CIRAVA_BETA_RELEASES_API_URL || env.VITE_CIRAVA_BETA_RELEASES_API_URL || `https://api.github.com/repos/${repository}/releases?per_page=100`),
  },
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  };
});
