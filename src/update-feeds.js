const defaultRepository = 'B1progame/Cirava';

export function getUpdateFeeds(env = {}) {
  const repository = env.VITE_CIRAVA_GITHUB_REPOSITORY || defaultRepository;
  return {
    release: env.VITE_CIRAVA_STABLE_MANIFEST_URL
      || env.VITE_CIRAVA_UPDATE_MANIFEST_URL
      || `https://github.com/${repository}/releases/latest/download/update-manifest.json`,
    beta: env.VITE_CIRAVA_BETA_RELEASES_API_URL
      || `https://api.github.com/repos/${repository}/releases?per_page=100`,
  };
}

export function getUpdateFeed(channel, feeds) {
  return channel === 'beta' ? feeds.beta : feeds.release;
}
