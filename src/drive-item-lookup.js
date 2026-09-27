function normalizeDriveItem(item) {
  const mimeType = item.mimeType || 'application/octet-stream';
  return {
    ...item,
    type: mimeType === 'application/vnd.google-apps.folder' ? 'folder' : 'file',
    size: item.size ?? '—',
  };
}

export async function findDriveFileByName(api, name) {
  if (!name || !name.trim()) return null;
  if (typeof api?.find_drive_files_by_name === 'function') {
    const result = await api.find_drive_files_by_name(name);
    const unique = new Map();
    for (const item of Array.isArray(result?.files) ? result.files : []) {
      if (item?.id && item.name === name) unique.set(item.id, item);
    }
    if (unique.size > 1) {
      throw new Error(`More than one Drive item is named “${name}”. Rename one item and try again so Cirava can target it safely.`);
    }
    const match = unique.values().next().value;
    return match ? normalizeDriveItem(match) : null;
  }

  if (typeof api?.list_drive_files !== 'function') return null;
  const result = await api.list_drive_files();
  const matches = (Array.isArray(result?.files) ? result.files : []).filter((item) => item?.id && item.name === name);
  if (matches.length > 1) {
    throw new Error(`More than one Drive item is named “${name}”. Refresh the list and try again.`);
  }
  return matches[0] ? normalizeDriveItem(matches[0]) : null;
}
