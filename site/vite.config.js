import { createReadStream, existsSync, statSync } from 'node:fs';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';

const here = fileURLToPath(new URL('.', import.meta.url));
const repoAssets = join(here, '..', 'docs', 'assets');
const TYPES = { '.svg': 'image/svg+xml', '.png': 'image/png', '.webp': 'image/webp' };

// GitHub Pages serves the whole repository, so the built pages sit beside docs/ and
// reference the figures with plain relative URLs. Only the dev server needs the map.
const devDocsAssets = {
  name: 'dev-docs-assets',
  apply: 'serve',
  configureServer(server) {
    server.middlewares.use('/docs/assets', (req, res, next) => {
      const file = join(repoAssets, normalize(decodeURIComponent(req.url.split('?')[0])));
      if (!file.startsWith(repoAssets) || !existsSync(file) || !statSync(file).isFile()) return next();
      res.setHeader('Content-Type', TYPES[extname(file)] ?? 'application/octet-stream');
      createReadStream(file).pipe(res);
    });
  },
};

export default defineConfig({
  base: './',
  appType: 'mpa',
  plugins: [devDocsAssets],
  build: {
    rollupOptions: {
      input: {
        en: 'index.html',
        ja: 'index.ja.html',
      },
    },
  },
});
