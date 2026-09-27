import test from 'node:test';
import assert from 'node:assert/strict';
import { runWithDriveFolderName } from '../src/drive-create-dialog.js';

test('folder create action receives the custom name without changing other prompts', () => {
  const calls = [];
  const targetWindow = {
    prompt(message, fallback) {
      calls.push([message, fallback]);
      return 'PDF';
    },
  };
  const originalPrompt = targetWindow.prompt;
  let folderName;

  const intercepted = runWithDriveFolderName('  Project files  ', () => {
    folderName = targetWindow.prompt('Create folder in this folder', 'Untitled');
    const exportFormat = targetWindow.prompt('Export format: PDF, DOCX, TXT, XLSX, or CSV', 'PDF');
    assert.equal(exportFormat, 'PDF');
  }, targetWindow);

  assert.equal(intercepted, true);
  assert.equal(folderName, '  Project files  ');
  assert.deepEqual(calls, [['Export format: PDF, DOCX, TXT, XLSX, or CSV', 'PDF']]);
  assert.equal(targetWindow.prompt, originalPrompt);
});

test('temporary custom folder name is restored even if the create action throws', () => {
  const targetWindow = { prompt: () => 'native' };
  const originalPrompt = targetWindow.prompt;

  assert.throws(() => runWithDriveFolderName('Folder', () => { throw new Error('failed'); }, targetWindow), /failed/);
  assert.equal(targetWindow.prompt, originalPrompt);
});
