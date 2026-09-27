export function createArchiveUploadFlow(api) {
  let prepared = null;

  const keyFor = (paths) => JSON.stringify(Array.isArray(paths) ? paths.map(String) : []);

  return {
    clear() { prepared = null; },
    async preview(paths, level = 5) {
      if (!Array.isArray(paths) || paths.length === 0) throw new Error('Choose files or a folder before previewing compression.');
      if (typeof api?.prepare_compressed_upload !== 'function') throw new Error('Open Cirava desktop and enable 7-Zip in Settings first.');
      prepared = null;
      const result = await api.prepare_compressed_upload(paths, Number(level));
      if (!result?.archive_path || !Number.isFinite(Number(result.archive_bytes))) throw new Error('7-Zip did not return a prepared archive. Try again or turn compression off.');
      prepared = { source: keyFor(paths), ...result };
      return prepared;
    },
    uploadPaths(paths) {
      if (prepared && prepared.source === keyFor(paths) && prepared.archive_path) return [prepared.archive_path];
      return paths;
    },
    getPrepared(paths) { return prepared?.source === keyFor(paths) ? prepared : null; },
  };
}

export function formatArchiveSavings(preview) {
  if (!preview) return '';
  const size = (bytes) => {
    const value = Math.max(0, Number(bytes) || 0);
    return value >= 1024 ** 3 ? `${(value / 1024 ** 3).toFixed(2)} GB` : `${(value / 1024 ** 2).toFixed(1)} MB`;
  };
  const saved = Math.max(0, Number(preview.saved_bytes) || 0);
  if (!saved) return `Archive: ${size(preview.archive_bytes)} · this selection did not compress smaller.`;
  return `Archive: ${size(preview.archive_bytes)} · saves ${size(saved)} (${Number(preview.saved_percent) || 0}%).`;
}
