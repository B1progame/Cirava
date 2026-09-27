export type CiravaBridge = {
  boot_state: () => Promise<{ configured: boolean; authenticated: boolean }>;
  save_google_configuration: (clientId: string, clientSecret?: string) => Promise<{ ok: boolean }>;
  validate_google_configuration: (clientId: string) => Promise<{ ok: boolean; checks: Record<string, boolean> }>;
  begin_google_login: () => Promise<{ ok: boolean; authenticated: boolean }>;
  get_account_profile: () => Promise<{ name: string; email: string; photoUrl: string; driveName: string }>;
  sign_out: () => Promise<{ ok: boolean }>;
  load_preferences: () => Promise<Record<string, string>>;
  save_preferences: (values: Record<string, string>) => Promise<{ ok: boolean; saved: string[] }>;
  get_archive_compression_status: () => Promise<{ enabled: boolean; installed: boolean; provider: string; license: string }>;
  set_archive_compression_enabled: (enabled: boolean) => Promise<{ enabled: boolean; installed: boolean; provider: string; license: string }>;
  prepare_compressed_upload: (localPaths: string[], level?: number) => Promise<{ archive_path: string; archive_name: string; original_bytes: number; archive_bytes: number; saved_bytes: number; saved_percent: number; files: number }>;
  pick_files: () => Promise<string[]>;
  pick_folder: () => Promise<string[]>;
  pick_save_path: (filename: string) => Promise<string | null>;
  summarize_local_paths: (localPaths: string[]) => Promise<{ files: number; folders: number; bytes: number; items: number }>;
  create_test_upload: (parentId?: string, chunkSize?: number, startImmediately?: boolean) => Promise<unknown[]>;
  list_drive_files: (parentId?: string, query?: string) => Promise<unknown>;
  find_drive_files_by_name: (name: string) => Promise<{ files: Array<Record<string, any>> }>;
  list_trashed_drive_files: () => Promise<{ files?: Array<Record<string, unknown>> }>;
  restore_drive_file: (driveFileId: string) => Promise<{ id: string; status: string }>;
  empty_drive_trash: () => Promise<{ status: string }>;
  get_storage_quota: () => Promise<{ limit?: string; usage?: string; usageInDrive?: string; usageInDriveTrash?: string }>;
  list_shared_drives: () => Promise<{ drives?: Array<{ id: string; name: string }> }>;
  select_shared_drive: (driveId?: string) => Promise<{ shared_drive_id: string | null }>;
  create_drive_folder: (name: string, parentId?: string) => Promise<{ id: string; name: string; parent_id: string }>;
  create_drive_file: (name: string, parentId?: string, mimeType?: string, content?: string) => Promise<{ id?: string; name: string; parent_id: string; mime_type: string }>;
  trash_drive_file: (driveFileId: string) => Promise<{ id: string; status: string }>;
  download_drive_folder_zip: (driveFolderId: string, localPath: string) => Promise<{ status: string; local_path: string; files: number; bytes: number }>;
  download_drive_folder_zip_by_name: (folderName: string, localPath: string) => Promise<{ status: string; local_path: string; files: number; bytes: number }>;
  read_drive_file: (driveFileId: string, mimeType?: string, maxBytes?: number) => Promise<{ id: string; content: string; bytes: number; mime_type: string }>;
  update_drive_file: (driveFileId: string, content: string, mimeType?: string) => Promise<{ id: string; status: string; bytes: number }>;
  export_drive_file: (driveFileId: string, localPath: string, mimeType: string) => Promise<{ status: string; local_path: string; bytes?: number }>;
  create_upload: (localPath: string, parentId?: string, chunkSize?: number, startImmediately?: boolean) => Promise<unknown>;
  create_upload_batch: (localPaths: string[], parentId?: string, chunkSize?: number, startImmediately?: boolean) => Promise<unknown[]>;
  create_download: (driveFileId: string, localPath: string, size: number, segmentSize?: number, workers?: number, expectedMd5?: string, conflictPolicy?: "ask" | "skip" | "replace" | "keep-both", startImmediately?: boolean) => Promise<unknown>;
  start_transfer: (transferId: string) => Promise<unknown>;
  start_queued_transfers: () => Promise<{ started: number; ids: string[] }>;
  pause_transfer: (transferId: string) => Promise<unknown>;
  cancel_transfer: (transferId: string) => Promise<unknown>;
  resume_transfer: (transferId: string) => Promise<unknown>;
  retry_transfer: (transferId: string) => Promise<unknown>;
  list_transfers: () => Promise<unknown[]>;
  set_transfer_priority: (transferId: string, priority: "low" | "normal" | "high") => Promise<unknown>;
  reorder_transfers: (transferIds: string[]) => Promise<{ ok: boolean; count: number }>;
  clear_history: () => Promise<{ cleared: number }>;
  remove_transfer: (transferId: string) => Promise<{ removed: string }>;
  reveal_local: (transferId: string) => Promise<{ opened: string }>;
  open_drive_file: (transferId: string) => Promise<{ url: string }>;
  get_transfer_limit: () => Promise<{ mbps: number }>;
  set_transfer_limit: (mbps: number) => Promise<{ mbps: number }>;
  measure_connection_speed: (sampleBytes?: number) => Promise<{ bytes: number; seconds: number; mbps: number; mib_per_second: number }>;
  get_upload_concurrency: () => Promise<{ workers: number }>;
  set_upload_concurrency: (workers: number) => Promise<{ workers: number }>;
  check_for_update: (manifestUrl: string, currentVersion?: string) => Promise<{
    available: boolean;
    version: string;
    current_version: string;
    release_notes: string[];
    release_notes_markdown: string;
    update_type: 'installer' | 'in_place';
    in_place_available: boolean;
  }>;
  stage_update: (manifestUrl: string, currentVersion?: string) => Promise<{
    staged: boolean;
    path: string;
    version: string;
    update_type: 'installer' | 'in_place';
  }>;
  restart_staged_update: (stagedPath: string, updateType: 'installer' | 'in_place') => Promise<{
    started: boolean;
    path: string;
    update_type: 'installer' | 'in_place';
  }>;
};

declare global {
  interface Window { pywebview?: { api?: CiravaBridge } }
}

export function getBridge(): CiravaBridge | null {
  try {
    const api = window.pywebview?.api;
    return api && typeof api.boot_state === 'function' ? api : null;
  } catch {
    return null;
  }
}

export function hasBridgeApi(): boolean {
  try {
    const api = window.pywebview?.api as unknown;
    return Boolean(api && (typeof api === 'object' || typeof api === 'function'));
  } catch {
    return false;
  }
}
