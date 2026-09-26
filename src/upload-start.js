export async function startUploadWithFeedback({ createBatch, navigate, onStatus = () => {} }) {
  onStatus('Creating a resumable upload…');
  try {
    const created = await createBatch();
    if (!Array.isArray(created) || created.length === 0) throw new Error('No files were found in the selected paths.');
    onStatus(`${created.length} upload${created.length === 1 ? '' : 's'} queued. Opening Transfers…`);
    const navigated = await navigate();
    if (navigated === false) onStatus(`${created.length} upload${created.length === 1 ? '' : 's'} queued. Open Transfers to monitor progress.`);
    return created;
  } catch (error) {
    onStatus(error instanceof Error ? error.message : 'Could not queue the upload.');
    throw error;
  }
}
