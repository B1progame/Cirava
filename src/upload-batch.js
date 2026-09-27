export async function createUploadBatch({ api, paths, destinationId, testUpload = false, chunkSize = 64 * 1024 * 1024, startImmediately = true }) {
  if (!api) throw new Error('The Cirava desktop bridge is not available.');
  if (testUpload) {
    if (typeof api.create_test_upload !== 'function') throw new Error('The test upload is unavailable in this Cirava build.');
    return startImmediately ? api.create_test_upload(destinationId, chunkSize) : api.create_test_upload(destinationId, chunkSize, false);
  }
  if (!Array.isArray(paths) || paths.length === 0) throw new Error('Choose at least one local file or folder.');
  if (typeof api.create_upload_batch !== 'function') throw new Error('The Cirava desktop bridge cannot queue uploads.');
  return startImmediately ? api.create_upload_batch(paths, destinationId, chunkSize) : api.create_upload_batch(paths, destinationId, chunkSize, false);
}
