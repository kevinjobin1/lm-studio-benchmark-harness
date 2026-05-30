import { defineConfig } from 'astro/config';
import react from '@astrojs/react';

export default defineConfig({
  integrations: [react()],
  output: 'static',
  site: 'https://kevinjobin1.github.io/lm-studio-benchmark-harness',
  base: '/lm-studio-benchmark-harness',
  build: {
    assets: 'assets',
  },
});
