# Download files or folders

## Download a file

1. Open **Drive** and browse to the item.
2. Hold the item's **Download** action until it confirms. A quick click is intentionally ignored to prevent an accidental download.
3. Choose where to save it when Cirava asks.
4. Open **Transfers** to follow progress or pause and resume the download.

Cirava downloads file data in ranges and checks the completed file against Drive's checksum when one is available. If a connection fails, completed ranges can be reused when the transfer resumes.

## Download a folder

Hold **Download as ZIP** for a folder, then select where to save the archive. Cirava gathers the folder contents into a ZIP while downloading file ranges concurrently. Large folders can take time and need enough free disk space for the archive and temporary work.

If **Settings → 7-Zip archive compression** is enabled, Cirava recognizes its own marked archives, verifies them, and extracts them into a new folder after download. Other ZIP files are not automatically extracted.

Google Docs, Sheets, and Slides are cloud-native documents rather than ordinary binary files. Cirava exports those documents to a supported format instead of downloading them as raw file bytes. The available export formats depend on the document type.
