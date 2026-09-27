export type UpdateChannel = 'release' | 'beta';
export type UpdateFeeds = Record<UpdateChannel, string>;
export function getUpdateFeeds(env?: Record<string, string | undefined>): UpdateFeeds;
export function getUpdateFeed(channel: UpdateChannel, feeds: UpdateFeeds): string;
