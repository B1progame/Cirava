import { useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, CheckCircle2, Clock3, FolderPlus, Pause, Play, RefreshCw, ScanLine, Search, ShieldCheck, Sparkles } from 'lucide-react';
import { getBridge } from '../../bridge';
import { addedItems, formatScanBytes, scanDriveTree, type ScanItem, type ScanResult } from './scanRepeat';
import './scan-repeat.css';

const INTERVALS = [15, 30, 60] as const;
function timeLabel(timestamp: number | null): string { if (!timestamp) return 'Not scanned yet'; return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }

export function ScanRepeatPage({ onToast, onError }: { onToast: (message: string) => void; onError: (message: string) => void }) {
  const api = getBridge();
  const [scan, setScan] = useState<ScanResult | null>(null);
  const [newItems, setNewItems] = useState<ScanItem[]>([]);
  const [scanning, setScanning] = useState(false);
  const [repeat, setRepeat] = useState(false);
  const [intervalSeconds, setIntervalSeconds] = useState<(typeof INTERVALS)[number]>(30);
  const [folderName, setFolderName] = useState('');
  const [creatingFolder, setCreatingFolder] = useState(false);
  const [lastError, setLastError] = useState('');
  const controller = useRef<AbortController | null>(null);
  const repeatTimer = useRef<number | null>(null);
  const scanInFlight = useRef(false);

  const runScan = async () => {
    if (!api || scanInFlight.current) return;
    scanInFlight.current = true;
    controller.current?.abort();
    const nextController = new AbortController(); controller.current = nextController;
    setScanning(true); setLastError('');
    try { const result = await scanDriveTree(api, 'root', nextController.signal); setNewItems(addedItems(scan?.items ?? [], result.items)); setScan(result); }
    catch (error) { if (!(error instanceof DOMException && error.name === 'AbortError')) { const message = error instanceof Error ? error.message : 'Drive scan failed'; setLastError(message); onError('Scan could not finish. Check the Drive connection and try again.'); } }
    finally { scanInFlight.current = false; setScanning(false); }
  };

  useEffect(() => { if (!repeat || !api) return undefined; void runScan(); repeatTimer.current = window.setInterval(() => void runScan(), intervalSeconds * 1000); return () => { if (repeatTimer.current) window.clearInterval(repeatTimer.current); repeatTimer.current = null; }; }, [repeat, intervalSeconds, api]);
  useEffect(() => () => { controller.current?.abort(); if (repeatTimer.current) window.clearInterval(repeatTimer.current); }, []);

  const status = useMemo(() => {
    if (!api) return { tone: 'warning', label: 'Desktop engine required', copy: 'Open Cirava desktop to scan the real Drive.' };
    if (scanning) return { tone: 'active', label: 'Scanning Drive', copy: 'Walking folders and indexing files…' };
    if (scan?.truncated) return { tone: 'warning', label: 'Scan capped safely', copy: 'The scan reached its safety limit.' };
    return { tone: 'ready', label: scan ? 'Baseline ready' : 'Ready for your first scan', copy: scan ? `Last scan at ${timeLabel(scan.scannedAt)}.` : 'Create a snapshot, then repeat to see what changed.' };
  }, [api, scan, scanning]);

  const createFolder = async () => {
    const name = folderName.trim(); if (!name || !api || creatingFolder) return; setCreatingFolder(true);
    try { await api.create_drive_folder(name, 'root'); setFolderName(''); onToast(`Folder created · ${name}`); void runScan(); }
    catch (error) { onError(error instanceof Error ? error.message : 'Could not create the Drive folder.'); }
    finally { setCreatingFolder(false); }
  };

  return <section className="page scan-repeat-page">
    <header className="scan-repeat-heading"><div><span className="eyebrow"><span className="eyebrow-line" />Workflow</span><h2>Scan &amp; repeat.</h2><p>Keep a living snapshot of your Drive and spot new work the moment it arrives.</p></div><div className="scan-heading-meta"><span className={`scan-live-dot ${scanning ? 'is-active' : ''}`} />{scanning ? 'Reading Drive' : 'Drive monitor'}</div></header>

    <section className="scan-repeat-hero" data-tone={status.tone}>
      <div className="scan-hero-copy"><div className="scan-status-pill"><span className="scan-pill-icon">{status.tone === 'active' ? <RefreshCw className="spin" size={15} /> : status.tone === 'ready' ? <CheckCircle2 size={15} /> : <AlertCircle size={15} />}</span><span>{status.label}</span><small>{status.copy}</small></div><span className="scan-hero-kicker">{scan ? 'Your workspace has a baseline' : 'A calmer way to watch your files'}</span><h3>{scan ? 'Nothing important slips past you.' : 'See what changed, at a glance.'}</h3><p>Scan folder metadata without downloading or changing a single file. Cirava remembers the snapshot and highlights additions on the next pass.</p><div className="scan-hero-actions"><button className="scan-primary-action" onClick={() => void runScan()} disabled={!api || scanning}><ScanLine size={17} /> {scanning ? 'Scanning Drive…' : scan ? 'Scan again' : 'Start first scan'}</button>{scan && <span className="scan-last-run">Last checked {timeLabel(scan.scannedAt)}</span>}</div><div className="scan-hero-trust"><span><ShieldCheck size={15} /> Metadata only</span><span><Sparkles size={15} /> Bounded and resumable</span></div></div>
    <div className="scan-hero-visual"><div className="scan-visual-header"><span>Workspace snapshot</span><strong>{scan ? 'Updated' : 'Waiting'}</strong></div><div className="scan-orbit"><div className="scan-orbit-ring ring-one" /><div className="scan-orbit-ring ring-two" /><span className="scan-orbit-point-track scan-orbit-point-track--outer" aria-hidden="true"><i className="scan-orbit-dot dot-one" /></span><span className="scan-orbit-point-track scan-orbit-point-track--inner" aria-hidden="true"><i className="scan-orbit-dot dot-two" /></span><div className="scan-orbit-core"><ScanLine size={28} /></div></div><strong className="scan-visual-title">{scan ? `${scan.files + scan.folders} items indexed` : 'Ready to map your Drive'}</strong><span className="scan-visual-copy">{scan ? `${newItems.length} new item${newItems.length === 1 ? '' : 's'} since the previous scan` : 'Start a scan to create your first baseline'}</span></div>
    </section>

    <div className="scan-repeat-grid"><section className="panel scan-control-card"><div className="panel-head"><div><span className="eyebrow">01 · Baseline</span><h3>Take a snapshot</h3></div><Search size={18} /></div><p className="panel-copy">Cirava reads names, folders, and sizes only, then stores a lightweight comparison point.</p><div className="scan-card-footer"><span><ShieldCheck size={15} /> Nothing is downloaded</span><button className="scan-card-link" onClick={() => void runScan()} disabled={!api || scanning}>Scan now <span>↗</span></button></div></section><section className="panel scan-control-card"><div className="panel-head"><div><span className="eyebrow">02 · Watch</span><h3>Repeat automatically</h3></div><Clock3 size={18} /></div><div className="repeat-toggle-row"><div><strong>{repeat ? 'Repeating scans' : 'Manual checks'}</strong><span>{repeat ? `Every ${intervalSeconds} seconds` : 'Turn this on to keep watching'}</span></div><button className={`repeat-toggle ${repeat ? 'is-on' : ''}`} onClick={() => setRepeat((value) => !value)} disabled={!api} aria-pressed={repeat} aria-label={repeat ? 'Pause repeating scans' : 'Start repeating scans'}>{repeat ? <Pause size={15} /> : <Play size={15} />}</button></div><div className="interval-picker"><span>Cadence</span>{INTERVALS.map((value) => <button key={value} className={intervalSeconds === value ? 'selected' : ''} onClick={() => setIntervalSeconds(value)} disabled={scanning}>{value}s</button>)}</div></section><section className="panel scan-control-card"><div className="panel-head"><div><span className="eyebrow">03 · Organize</span><h3>Create a destination</h3></div><FolderPlus size={18} /></div><p className="panel-copy">Make a clean Drive folder without leaving this workflow. Your next scan includes it automatically.</p><div className="create-folder-row"><input value={folderName} onChange={(event) => setFolderName(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void createFolder(); }} placeholder="New folder name" aria-label="New Drive folder name" disabled={!api || creatingFolder} /><button className="secondary" onClick={() => void createFolder()} disabled={!api || !folderName.trim() || creatingFolder}><FolderPlus size={16} /> {creatingFolder ? 'Creating…' : 'Create'}</button></div></section></div>

    <section className="panel scan-results"><div className="panel-head"><div><span className="eyebrow">Live result</span><h3>{newItems.length ? `${newItems.length} new item${newItems.length === 1 ? '' : 's'} found` : scan ? 'Workspace inventory' : 'Your first snapshot is waiting'}</h3></div><span className="scan-result-meta">{scan ? `Scanned ${timeLabel(scan.scannedAt)}` : 'No baseline yet'}</span></div>{scan ? <><div className="scan-stat-grid"><div><strong>{scan.files}</strong><span>Files</span></div><div><strong>{scan.folders}</strong><span>Folders</span></div><div><strong>{formatScanBytes(scan.bytes)}</strong><span>Total size</span></div><div><strong>{newItems.length || '—'}</strong><span>New since last scan</span></div></div>{newItems.length > 0 && <div className="scan-new-list">{newItems.slice(0, 8).map((item) => <div className="scan-new-item" key={itemKey(item)}><span className="scan-new-dot" /><div><strong>{item.name}</strong><span>{item.path} · {item.isFolder ? 'Folder' : formatScanBytes(item.bytes)}</span></div></div>)}{newItems.length > 8 && <span className="scan-more">+ {newItems.length - 8} more additions</span>}</div>}</> : <div className="scan-empty-result"><div className="scan-empty-icon"><ScanLine size={22} /></div><div><strong>Scan once to establish your baseline</strong><span>New files and folders will appear here as a calm, readable change list.</span></div><button className="scan-card-link" onClick={() => void runScan()} disabled={!api}>Create baseline <span>↗</span></button></div>}{lastError && <div className="scan-error"><AlertCircle size={15} /> {lastError}</div>}</section>
  </section>;
}
function itemKey(item: ScanItem): string { return item.id || item.path; }
