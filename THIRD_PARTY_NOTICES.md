# Third-party software notices

## 7-Zip

Cirava can optionally download and install 7-Zip when a user turns on **Settings → 7-Zip archive compression**. Cirava does not claim ownership of 7-Zip. The component is downloaded from the official 7-Zip download page, and its Authenticode signature is checked before installation. It is installed under the current user's Cirava data directory; Cirava does not bundle it in the application installer.

7-Zip is Copyright © 1999–2026 Igor Pavlov. Most 7-Zip source files are licensed under the GNU Lesser General Public License (LGPL); some files have separate licenses, and the RAR-related files have an additional unRAR restriction. The exact terms and source are maintained by the 7-Zip project:

- [7-Zip license and distribution terms](https://github.com/ip7z/7zip/blob/main/DOC/License.txt)
- [7-Zip official downloads](https://www.7-zip.org/download.html)
- [7-Zip FAQ for application developers](https://www.7-zip.org/faq.html)

The license for Cirava's own code does not apply to 7-Zip or override any 7-Zip license. Users can disable the optional integration in Cirava Settings at any time. Disabling it stops Cirava's archive features but does not uninstall the separately installed 7-Zip files.
