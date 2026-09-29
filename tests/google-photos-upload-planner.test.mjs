import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const planner = readFileSync(new URL('../src/main.tsx', import.meta.url), 'utf8');
const photosPage = readFileSync(new URL('../src/google-photos-page.js', import.meta.url), 'utf8');

test('Google Photos upload entrypoints open the shared planner and carry selected local paths into it', () => {
  assert.match(photosPage, /cirava:open-upload-planner'[\s\S]{0,100}target:\s*'photos',\s*paths/);
  assert.match(photosPage, /openUploadPlanner\(chosen\.map\(\(item\) => item\.path\)\)/);
  assert.match(planner, /ciravaOpenDirectUploadPlanner\(target, detail\?\.paths \|\| \[\]\)/);
});

test('Photos planner uses the Google Photos library destination and Photos resumable batch bridge', () => {
  assert.match(planner, /02 · GOOGLE PHOTOS[\s\S]*?Google Photos library/);
  assert.match(planner, /createGooglePhotosUploadBatch\(\{ api, paths: state\.paths, startImmediately: true, albumTitle: photosAlbumTitle\(\) \}\)/);
  assert.match(planner, /createGooglePhotosUploadBatch\(\{ api, paths: state\.paths, startImmediately: false, albumTitle: photosAlbumTitle\(\) \}\)/);
  assert.match(planner, /Create a new album/);
  assert.match(planner, /data-cirava-photos-album-title/);
  assert.match(planner, /!testDataEnabled \|\| isPhotosUpload/);
});
