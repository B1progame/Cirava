export async function createUploadBatch({ api, paths, destinationId, destinationDriveId = null, testUpload = false, chunkSize = 64 * 1024 * 1024, startImmediately = true }) {
  if (!api) throw new Error('The Cirava desktop bridge is not available.');
  if (testUpload) {
    if (typeof api.create_test_upload !== 'function') throw new Error('The test upload is unavailable in this Cirava build.');
    return startImmediately ? api.create_test_upload(destinationId, chunkSize) : api.create_test_upload(destinationId, chunkSize, false);
  }
  if (!Array.isArray(paths) || paths.length === 0) throw new Error('Choose at least one local file or folder.');
  if (typeof api.create_upload_batch !== 'function') throw new Error('The Cirava desktop bridge cannot queue uploads.');
  return api.create_upload_batch(paths, destinationId, chunkSize, startImmediately, destinationDriveId);
}

export async function createGooglePhotosUploadBatch({ api, paths, startImmediately = true, albumTitle = null }) {
  if (!api) throw new Error('The Cirava desktop bridge is not available.');
  if (!Array.isArray(paths) || paths.length === 0) throw new Error('Choose at least one photo or video.');
  if (typeof api.create_google_photos_upload_batch !== 'function') throw new Error('Google Photos upload is unavailable. Reconnect Google and check its API setup.');
  const cleanAlbumTitle = albumTitle === null ? null : String(albumTitle).trim();
  if (cleanAlbumTitle !== null && !cleanAlbumTitle) throw new Error('Enter a name for the Google Photos album.');
  const records = await api.create_google_photos_upload_batch(paths, startImmediately, cleanAlbumTitle);
  if (!Array.isArray(records) || records.length === 0) throw new Error('No supported photos or videos were added to the upload.');
  return records;
}
