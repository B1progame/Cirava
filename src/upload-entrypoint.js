export function isDriveUploadEntrypoint(element) {
  if (!element?.matches?.('.page-heading .page-actions button, .heading-actions button')) return false;
  return element.textContent?.replace(/\s+/g, ' ').trim() === 'Upload';
}
