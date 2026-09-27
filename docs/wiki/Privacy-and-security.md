# Privacy and account access

Cirava signs in through Google's desktop OAuth flow with authorization code and PKCE. Its Drive access uses the `drive.file` scope. Google still applies the signed-in account's permissions, storage limits, and API quotas.

OAuth tokens stay on this Windows device and are protected with Windows DPAPI. Cirava does not need your Google password. Do not share tokens, sign-in codes, or client secrets. A desktop client ID is entered during setup; a client secret, if Google gives you one, should remain private and local.

Uploads use resumable Drive sessions. Downloads use range requests where supported. Cirava stores transfer state locally so interrupted work can be recovered. Its optional 20 GB test file is uploaded to your Drive and consumes real Drive storage. It is not a free or local benchmark.

For the exact implementation and security boundaries, see the repository's [security model](https://github.com/B1progame/Cirava/blob/main/SECURITY.md). To report an issue, remove account identifiers, file names, access tokens, and private screenshots from logs before sharing them.
