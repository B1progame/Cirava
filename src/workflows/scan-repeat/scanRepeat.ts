import type { CiravaBridge } from '../../bridge';

export const DRIVE_FOLDER_MIME = 'application/vnd.google-apps.folder';
export const DEFAULT_SCAN_ROOT = 'root';

export type ScanItem = {
  id: string;
  name: string;
  path: string;
  mimeType: string;
  bytes: number;
  modifiedTime: string;
  isFolder: boolean;
};

export type ScanResult = {
  items: ScanItem[];
  folders: number;
  files: number;
  bytes: number;
  scannedAt: number;
  truncated: boolean;
};

type DriveResponse = { files?: Array<Record<string, unknown>> };

function stringValue(value: unknown, fallback: string): string {
  return typeof value === 'string' && value.length > 0 ? value : fallback;
}

function numberValue(value: unknown): number {
  const parsed = typeof value === 'number' ? value : Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

/**
 * Walks Drive one folder at a time. The visited set protects against malformed
 * parent graphs and the item cap keeps a repeated scan bounded and cancellable.
 */
export async function scanDriveTree(
  api: Pick<CiravaBridge, 'list_drive_files'>,
  rootId = DEFAULT_SCAN_ROOT,
  signal?: AbortSignal,
  options: { maxItems?: number; maxDepth?: number } = {},
): Promise<ScanResult> {
  const maxItems = options.maxItems ?? 10_000;
  const maxDepth = options.maxDepth ?? 24;
  const items: ScanItem[] = [];
  const visitedFolders = new Set<string>();
  let truncated = false;

  const walk = async (folderId: string, parentPath: string, depth: number): Promise<void> => {
    if (signal?.aborted) throw new DOMException('Scan cancelled', 'AbortError');
    if (depth > maxDepth || visitedFolders.has(folderId)) {
      truncated = true;
      return;
    }
    visitedFolders.add(folderId);
    const payload = await api.list_drive_files(folderId);
    const files = (payload as DriveResponse).files ?? [];
    for (const raw of files) {
      if (signal?.aborted) throw new DOMException('Scan cancelled', 'AbortError');
      if (items.length >= maxItems) {
        truncated = true;
        return;
      }
      const id = stringValue(raw.id, `${folderId}:${items.length}`);
      const name = stringValue(raw.name, 'Unnamed item');
      const mimeType = stringValue(raw.mimeType, 'application/octet-stream');
      const isFolder = mimeType === DRIVE_FOLDER_MIME;
      const path = parentPath ? `${parentPath}/${name}` : name;
      items.push({
        id,
        name,
        path,
        mimeType,
        bytes: numberValue(raw.size),
        modifiedTime: stringValue(raw.modifiedTime, 'Unknown'),
        isFolder,
      });
      if (isFolder) await walk(id, path, depth + 1);
    }
  };

  await walk(rootId, '', 0);
  const folders = items.filter((item) => item.isFolder).length;
  const files = items.length - folders;
  return { items, folders, files, bytes: items.reduce((total, item) => total + item.bytes, 0), scannedAt: Date.now(), truncated };
}

export function itemKey(item: Pick<ScanItem, 'id' | 'path'>): string {
  return item.id || item.path;
}

export function addedItems(previous: ScanItem[], current: ScanItem[]): ScanItem[] {
  const known = new Set(previous.map(itemKey));
  return current.filter((item) => !known.has(itemKey(item)));
}

export function formatScanBytes(bytes: number): string {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) { value /= 1024; index += 1; }
  return `${value >= 100 ? Math.round(value) : value.toFixed(1)} ${units[index]}`;
}

