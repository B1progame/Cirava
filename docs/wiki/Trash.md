# Restore files and manage Drive Trash

Cirava's **Drive → Trash** button opens the items currently in the signed-in Google account's Trash. The page also shows total storage use, the Drive-file portion, and the portion used by Trash when Google provides those values.

## Restore an item

1. Open **Drive**, then choose **Trash** in the toolbar.
2. Find the file or folder and check its name, date trashed, and size.
3. Choose **Restore** on that row. Cirava returns it to Drive; Google decides its original parent location.

Use **Refresh** if the list may have changed elsewhere. Restoring an item does not download it to this computer.

## Empty Trash

Choose **Empty trash** to review the permanent-deletion warning. Confirm only if you intend to permanently delete every item currently in the account's Trash. This cannot be undone. To remove just one item forever, use Google's Drive website; Cirava's row action is for restoring individual items.

## Storage numbers

The storage card shows Google-reported account usage and limit, along with Drive files and Trash when those separate figures are available. Google may omit a limit for accounts with unlimited storage, or omit component totals. Cirava displays unavailable values as such rather than estimating them. Deleting an item from Trash permanently is what releases storage held by that item; moving it to Trash alone may not.

## If Trash is unavailable

Reconnect the Google account and approve the full Drive permission. Cirava requests this access to manage the complete Trash and read account storage. Google marks this OAuth scope as restricted, so the OAuth consent configuration must meet Google's applicable requirements. See [Privacy and account access](Privacy-and-security) and [Google sign-in setup](Google-OAuth-Setup).
