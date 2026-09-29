import test from 'node:test';
import assert from 'node:assert/strict';
import { getGooglePhotosNavigationPlacement } from '../src/google-photos-page.js';

function nav(label, parent = null) {
  return { textContent: label, className: 'nav-item', parentElement: parent };
}

test('Google Photos can be placed before Settings when Drive is not mounted yet', () => {
  const settings = nav('Settings');
  const sidebar = {
    querySelectorAll: () => [settings],
    lastElementChild: settings,
  };

  assert.deepEqual(getGooglePhotosNavigationPlacement(sidebar), {
    anchor: settings,
    position: 'before',
    className: 'nav-item',
  });
});

test('Google Photos stays directly after Drive when the Drive navigation exists', () => {
  const drive = nav('Drive');
  const settings = nav('Settings');
  const sidebar = { querySelectorAll: () => [drive, settings], lastElementChild: settings };

  assert.deepEqual(getGooglePhotosNavigationPlacement(sidebar), {
    anchor: drive,
    position: 'after',
    className: 'nav-item',
  });
});
