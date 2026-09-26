export type CiravaBridge = {
  boot_state: () => Promise<{ configured: boolean; authenticated: boolean }>;
  save_google_configuration: (clientId: string, clientSecret?: string) => Promise<{ ok: boolean }>;
  validate_google_configuration: (clientId: string) => Promise<{ ok: boolean; checks: Record<string, boolean> }>;
  begin_google_login: () => Promise<{ ok: boolean; authenticated: boolean }>;
  get_account_profile: () => Promise<{ name: string; email: string; photoUrl: string; driveName: string }>;
  sign_out: () => Promise<{ ok: boolean }>;
  load_preferences: () => Promise<Record<string, string>>;
  save_preferences: (values: Record<string, string>) => Promise<{ ok: boolean; saved: string[] }>;
  pick_files: () => Promise<string[]>;
  pick_folder: () => Promise<string[]>;
  pick_save_path: (filename: string) => Promise<string | null>;
  summarize_local_paths: (localPaths: string[]) => Promise<{ files: number; folders: number; bytes: number; items: number }>;
  create_test_upload: (parentId?: string, chunkSize?: number) => Promise<unknown[]>;
  list_drive_files: (parentId?: string, query?: string) => Promise<unknown>;
  list_shared_drives: () => Promise<{ drives?: Array<{ id: string; name: string }> }>;
  select_shared_drive: (driveId?: string) => Promise<{ shared_drive_id: string | null }>;
  create_drive_folder: (name: string, parentId?: string) => Promise<{ id: string; name: string; parent_id: string }>;
  create_drive_file: (name: string, parentId?: string, mimeType?: string, content?: string) => Promise<{ id?: string; name: string; parent_id: string; mime_type: string }>;
  trash_drive_file: (driveFileId: string) => Promise<{ id: string; status: string }>;
  read_drive_file: (driveFileId: string, mimeType?: string, maxBytes?: number) => Promise<{ id: string; content: string; bytes: number; mime_type: string }>;
  update_drive_file: (driveFileId: string, content: string, mimeType?: string) => Promise<{ id: string; status: string; bytes: number }>;
  export_drive_file: (driveFileId: string, localPath: string, mimeType: string) => Promise<{ status: string; local_path: string; bytes?: number }>;
  create_upload: (localPath: string, parentId?: string, chunkSize?: number) => Promise<unknown>;
  create_upload_batch: (localPaths: string[], parentId?: string, chunkSize?: number) => Promise<unknown[]>;
    create_download: (driveFileId: string, localPath: string, size: number, segmentSize?: number, workers?: number, expectedMd5?: string, conflictPolicy?: "ask" | "skip" | "replace" | "keep-both") => Promise<unknown>;
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
  check_for_update: (manifestUrl: string, currentVersion?: string) => Promise<{ available: boolean; version: string; current_version: string; release_notes: string[] }>;
  stage_update: (manifestUrl: string, currentVersion?: string) => Promise<{ staged: boolean; path: string; version: string }>;
  restart_staged_update: (stagedPath: string) => Promise<{ started: boolean; path: string }>;
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
