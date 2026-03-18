#!/usr/bin/env node
/**
 * Convert a .drawio file to PNG using headless Chromium + draw.io viewer.
 *
 * Usage:
 *   node tools/drawio_to_png.mjs <input.drawio> [output.png]
 *
 * Requires: puppeteer-core (npm install --prefix tools puppeteer-core)
 *           chromium-browser on PATH
 */

import puppeteer from 'puppeteer-core';
import http from 'http';
import fs from 'fs';
import path from 'path';

const args = process.argv.slice(2);
if (args.length < 1) {
  console.error('Usage: node drawio_to_png.mjs <input.drawio> [output.png]');
  process.exit(1);
}

const inputPath = path.resolve(args[0]);
const outputPath = args[1]
  ? path.resolve(args[1])
  : inputPath.replace(/\.drawio$/, '.png');

if (!fs.existsSync(inputPath)) {
  console.error(`File not found: ${inputPath}`);
  process.exit(1);
}

// Find Chromium
const chromiumPaths = [
  '/usr/bin/chromium-browser',
  '/usr/bin/chromium',
  '/usr/bin/google-chrome',
];
const executablePath = chromiumPaths.find(p => fs.existsSync(p));
if (!executablePath) {
  console.error('Chromium not found. Install chromium-browser.');
  process.exit(1);
}

// Read .drawio XML and build viewer HTML
const xml = fs.readFileSync(inputPath, 'utf8');
const escapedXml = JSON.stringify(xml);

const html = `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://viewer.diagrams.net/js/viewer-static.min.js"></script>
<style>body { margin: 0; background: white; }</style>
</head>
<body>
<div class="mxgraph" id="graph-container"></div>
<script>
(function() {
  var container = document.getElementById('graph-container');
  container.setAttribute('data-mxgraph', JSON.stringify({
    highlight: '#0000ff',
    nav: true,
    resize: true,
    xml: ${escapedXml}
  }));
  GraphViewer.processElements();
})();
</script>
</body>
</html>`;

// Start local HTTP server
const server = http.createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  res.end(html);
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const port = server.address().port;

// Launch headless Chromium
const browser = await puppeteer.launch({
  executablePath,
  headless: true,
  args: ['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
});

try {
  const page = await browser.newPage();
  await page.setViewport({ width: 2400, height: 1200 });
  await page.goto(`http://127.0.0.1:${port}/`, {
    waitUntil: 'networkidle0',
    timeout: 30000,
  });

  // Wait for SVG to render
  try {
    await page.waitForSelector('svg', { timeout: 15000 });
  } catch {
    console.error('Warning: SVG not found after 15s, taking screenshot anyway');
  }
  await new Promise(r => setTimeout(r, 2000));

  // Crop to content bounding box (with padding)
  const bbox = await page.evaluate(() => {
    const svg = document.querySelector('svg');
    if (!svg) return null;
    const rect = svg.getBoundingClientRect();
    return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
  });

  if (bbox && bbox.width > 0 && bbox.height > 0) {
    const pad = 10;
    await page.screenshot({
      path: outputPath,
      clip: {
        x: Math.max(0, bbox.x - pad),
        y: Math.max(0, bbox.y - pad),
        width: bbox.width + pad * 2,
        height: bbox.height + pad * 2,
      },
    });
  } else {
    await page.screenshot({ path: outputPath, fullPage: true });
  }
  console.log(`Saved: ${outputPath}`);
} finally {
  await browser.close();
  server.close();
}
