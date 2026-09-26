export function getReleasePresentation(version, explicitChannel) {
  const normalizedVersion = String(version || '').trim();
  const channel = explicitChannel === 'beta'
    ? 'beta'
    : explicitChannel === 'release'
      ? 'release'
      : /-(?:[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)/.test(normalizedVersion)
        ? 'beta'
        : 'release';

  return {
    channel,
    badge: channel === 'beta' ? 'beta' : 'Stable',
    version: channel === 'beta' && !normalizedVersion.includes('-')
      ? `${normalizedVersion} beta`
      : normalizedVersion,
    productLabel: channel === 'beta' ? 'Desktop beta' : 'Desktop',
  };
}
