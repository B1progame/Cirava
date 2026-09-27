export function isDriveUploadEntrypoint(element) {
  const label = element?.textContent?.replace(/\s+/g, ' ').trim();
  if (label === 'Upload' && element?.matches?.('.page-heading .page-actions button, .heading-actions button')) return true;
  return label === 'Upload files' && Boolean(element?.matches?.('.drive-empty button'));
}
