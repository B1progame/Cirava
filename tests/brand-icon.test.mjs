import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const read = (path) => readFile(new URL(path, import.meta.url), 'utf8');

test('dark-mode branding does not replace the canonical Cirava PNG with another logo variant', async () => {
  const css = await read('../src/ui-fixes.css');
  assert.doesNotMatch(css, /html\[data-theme=['"]dark['"]\]\s+\.brand-mark[\s\S]{0,350}cirava-logo\.svg/);
});

test('the user-approved logo and Easter-egg video are present', async () => {
  const [logo, video] = await Promise.all([
    readFile(new URL('../public/cirava-logo.png', import.meta.url)),
    readFile(new URL('../public/cirava-startup.mp4', import.meta.url)),
  ]);
  assert.ok(logo.length > 1000);
  assert.ok(video.length > 1000);
});

test('visible brand surfaces use the user-approved logo asset', async () => {
  const files = [
    '../index.html', '../README.md', '../src/ui-fixes.css',
    '../packaging/build_msix.ps1', '../packaging/generate_installer_panel.ps1',
  ];
  for (const path of files) {
    const content = await read(path);
    assert.ok(content.includes('cirava-logo.png'), `${path} should use the approved Cirava logo`);
  }
});

test('hovering the brand plays the supplied video above the static approved logo', async () => {
  const source = await read('../src/main.tsx');
  const css = await read('../src/ui-fixes.css');
  assert.match(source, /ciravaInstallBrandEasterEgg/);
  assert.match(source, /cirava-startup\.mp4/);
  assert.match(source, /brand-mark-video-easter-egg/);
  assert.match(source, /video\.loop\s*=\s*true/);
  assert.match(source, /pointerout/);
  assert.match(css, /\.brand-mark[\s\S]*?position:\s*relative/);
  assert.match(css, /\.brand-mark-video-easter-egg[\s\S]*?object-fit:\s*cover/);
  assert.match(source, /prefers-reduced-motion:\s*reduce/);
});

test('the initial boot screen uses the approved static logo and does not autoplay the Easter egg', async () => {
  const html = await read('../index.html');
  assert.match(html, /<img src="\/cirava-logo\.png" alt="" \/>/);
  assert.doesNotMatch(html, /<video[^>]+cirava-startup\.mp4/);
});
