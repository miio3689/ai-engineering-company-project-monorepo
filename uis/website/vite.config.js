import { defineConfig } from 'vite';

const configuredHosts = process.env.VITE_ALLOWED_HOSTS?.trim();
const allowedHosts = configuredHosts
  ? configuredHosts === '*'
    ? true
    : configuredHosts.split(',').map((host) => host.trim()).filter(Boolean)
  : undefined;

export default defineConfig({
  server: allowedHosts ? { allowedHosts } : {},
  preview: { allowedHosts },
  build: {
    rollupOptions: {
      input: ['index.html', 'application.html'],
    },
  },
});