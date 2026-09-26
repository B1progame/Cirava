import { useState, type ReactNode } from 'react';

type LordIconName = 'home' | 'drive' | 'transfers' | 'history' | 'folder' | 'scan' | 'diagnostics' | 'settings' | 'about';

const iconSources: Record<LordIconName, string> = {
  home: 'https://media.lordicon.com/icons/system/outline/63-home.gif',
  drive: 'https://media.lordicon.com/icons/system/outline/2513-data.gif',
  transfers: 'https://media.lordicon.com/icons/system/outline/89-file-plus.gif',
  history: 'https://media.lordicon.com/icons/system/outline/2451-receipt.gif',
  folder: 'https://media.lordicon.com/icons/system/outline/120-folder.gif',
  scan: 'https://media.lordicon.com/icons/system/outline/362-article.gif',
  diagnostics: 'https://media.lordicon.com/icons/system/outline/2513-data.gif',
  settings: 'https://media.lordicon.com/icons/system/outline/380-sliders-horizontal.gif',
  about: 'https://media.lordicon.com/icons/system/outline/56-file-text.gif',
};

export function LordIconNavIcon({ name, fallback }: { name: LordIconName; fallback: ReactNode }) {
  const [failed, setFailed] = useState(false);
  return <span className="lordicon-nav-icon" aria-hidden="true">
    {failed ? fallback : <img src={iconSources[name]} alt="" loading="lazy" decoding="async" onError={() => setFailed(true)} />}
  </span>;
}
