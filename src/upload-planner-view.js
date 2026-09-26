function formatUploadSize(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit += 1; }
  return `${value >= 100 ? Math.round(value) : value.toFixed(1)} ${units[unit]}`;
}

function localName(path) {
  return String(path).split(/[\\/]/).filter(Boolean).at(-1) || String(path);
}

export function getUploadSelectionView(paths = [], summary, testUpload = false) {
  if (testUpload) {
    return {
      kind: 'test',
      title: 'Cobalt launch kit',
      detail: '20 GB upload · uses your Drive storage quota',
      fileNames: ['Created locally only after you hold to upload.'],
      fileCount: 1,
      totalSize: '20 GB',
    };
  }

  const fileCount = Number(summary?.files) || paths.length;
  if (!paths.length || !fileCount) {
    return {
      kind: 'empty',
      title: 'Choose files or a folder',
      detail: 'Nothing starts until you hold Start upload.',
      fileNames: [],
      fileCount: 0,
      totalSize: 'No files selected',
    };
  }

  const folderCount = Number(summary?.folders) || 0;
  const totalSize = formatUploadSize(Number(summary?.bytes) || 0);
  const title = fileCount === 1 && paths.length === 1
    ? localName(paths[0])
    : `${fileCount} file${fileCount === 1 ? '' : 's'} selected`;
  const folderDetails = folderCount ? ` · from ${folderCount} folder${folderCount === 1 ? '' : 's'}` : '';

  return {
    kind: 'files',
    title,
    detail: `${totalSize} total${folderDetails}`,
    fileNames: paths.slice(0, 3).map(localName),
    fileCount,
    totalSize,
  };
}
