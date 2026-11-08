import { defineConfig } from 'astro/config';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  site: 'https://phys-math.dev',
  output: 'static',
  trailingSlash: 'always',
  image: {
    remotePatterns: [{ protocol: 'https', hostname: 'pub-df8eda899f364205ba20a32dc3740d46.r2.dev' }]
  },
  vite: {
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      }
    }
  }
});
