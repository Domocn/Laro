import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// Every REACT_APP_* key the app reads at build time. CRA inlined these
// automatically; Vite needs them declared explicitly so the existing
// `process.env.REACT_APP_X` call sites keep working unchanged.
const REACT_APP_KEYS = [
  'REACT_APP_BACKEND_URL',
  'REACT_APP_CAST_APP_ID',
  'REACT_APP_REVENUECAT_WEB_API_KEY',
] as const;

// Build-time values are only defaults. Production injects the real values at
// container start by rewriting the `%REACT_APP_*%` placeholders that survive
// into the bundle (see docker-entrypoint.sh), so those must NOT be stripped.
function reactAppDefines(mode: string, env: Record<string, string>) {
  const defines: Record<string, string> = { 'process.env.NODE_ENV': JSON.stringify(mode) };
  for (const key of REACT_APP_KEYS) {
    defines[`process.env.${key}`] = JSON.stringify(env[key] ?? '');
  }
  return defines;
}

export default defineConfig(({ mode }) => {
  // loadEnv with '' so REACT_APP_* are read from .env files too (CRA behaviour).
  const env = loadEnv(mode, process.cwd(), 'REACT_APP_');

  return {
    plugins: [react()],
    resolve: {
      alias: { '@': path.resolve(__dirname, './src') },
    },
    define: reactAppDefines(mode, env),
    server: {
      host: '0.0.0.0',
      port: Number(process.env.PORT) || 3000,
      strictPort: false,
      allowedHosts: true,
      // Freebuff owns the dev server; HMR must stay off.
      hmr: false,
    },
    preview: {
      host: '0.0.0.0',
      port: Number(process.env.PORT) || 3000,
    },
    build: {
      outDir: 'dist',
      // Never ship source maps publicly — they expand attack surface.
      sourcemap: false,
      chunkSizeWarningLimit: 700,
      rollupOptions: {
        output: {
          // Only pull out what is genuinely on the critical path in EVERY
          // route. Do NOT add a catch-all here: assigning a module to a manual
          // chunk makes it a static dependency of the entry, so a blanket
          // 'vendor' bucket would drag route-only libraries (date-fns, embla,
          // cmdk, react-day-picker, the RevenueCat SDK) into the first load
          // and undo the per-route lazy() splitting in App.jsx.
          manualChunks(id) {
            if (!id.includes('node_modules')) return undefined;
            if (id.includes('/react-dom/') || id.includes('/react/') || id.includes('react-router')) {
              return 'react';
            }
            return undefined;
          },
        },
      },
    },
    test: {
      globals: true,
      // CRA's Jest defaulted to jsdom, and several suites touch
      // window/localStorage without opting in. Keep that default.
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.js'],
      include: ['src/**/*.test.{js,jsx}'],
    },
  };
});
