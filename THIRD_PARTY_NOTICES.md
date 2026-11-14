# Third-party notices — 0.7.11-rc2

Publisher: Brazzor. Component evidence was checked on 2026-11-09. Third-party
copyrights and terms remain in force; Microsoft binaries are not licensed under
this project's AGPL. The remaining SimConnect issue is stated below.

## Runtime components

| Component | Version | Retained terms / source evidence |
|---|---|---|
| CPython | 3.11.9 x64 | PSF license and its incorporated notices; exact official binary match |
| PyMuPDF / MuPDF | 1.28.2 / 1.28.2 | AGPLv3 route; exact upstream wheel and full MuPDF source |
| Python-SimConnect wrapper | 0.4.26 | Upstream AGPL license/metadata; exact wheel and sdist |
| ReportLab | 4.5.1 | BSD-style license, full sdist and supplied font notices |
| Pillow | 12.3.0 | MIT-CMU and detailed wheel/native dependency notices |
| charset-normalizer | 3.5.2 | MIT; exact wheel and sdist |
| Microsoft Visual C++ x64 CRT | 14.51.36247.0 | Unmodified stable VC/Redist files; Microsoft terms, not AGPL |
| Microsoft SimConnect.dll | Wheel-provided, SDK version not established | Microsoft proprietary; unresolved exact terms/combination basis |

The Python/MuPDF/Pillow binary file identities are recorded in
`docs/BINARY_SOURCE_MAP.json`. Sources and recorded upstream commits are listed in
`docs/SOURCE_COMPONENTS.json`. Build/source instructions are in `docs/SOURCE_BUILD.md`.

## Native library source coverage

- CPython: bzip2 1.0.8, XZ 5.2.5, libffi 3.4.4, OpenSSL 3.0.13 and zlib 1.3.1
  sources are included separately; other bundled sources such as Expat are in
  the CPython archive. Retained terms include Apache-2.0 (OpenSSL), MIT (libffi)
  and the original permissive bzip2/zlib/CPython notices.
- Pillow: FreeType 2.14.3 (FreeType license route), Brotli 1.2.0, LCMS 2.19.1,
  libjpeg-turbo 3.1.4.1, libpng 1.6.58, WebP 1.6.0, OpenJPEG 2.5.4, libtiff 4.7.1,
  XZ 5.8.3, zlib-ng 2.3.3, libavif 1.4.2, AOM 3.14.1 and dav1d 1.5.3 are included.
  Original copyright/license/patent notices are preserved. The runtime features
  and official wheel-build dependency recipe are used together for version evidence.
  Optional libimagequant and RAQM are absent from the observed runtime.
- MuPDF: the full source archive includes its bundled thirdparty directories,
  fonts and corresponding notices. Source notices are retained even for optional
  components; their presence alone is not a claim that each optional component
  is enabled in this binary.

Portions of this software are copyright © The FreeType Project
(www.freetype.org). All rights reserved.

`licenses/Native-source/inventory.json` maps copied source license/copyright/
patent texts to their original archive members and SHA-256 values.
`licenses/inventory.json` maps installed distribution license texts. Pillow's
large combined wheel LICENSE is retained verbatim; source notices supplement it.
ReportLab's DarkGarden GPL font exception and Bitstream Vera terms are retained;
the DarkGarden preferred font source is also in its sdist. This application's
release does not automatically impose AGPL licensing on user-generated reports.

## Microsoft runtime conditions

The three CRT files come from the installed stable Visual Studio Build Tools
`VC/Redist` tree; exact original paths/hashes are recorded in
`licenses/Microsoft-runtime/runtime.json`. The files are unchanged. Microsoft's
Redist list permits the listed files subject to the applicable Visual Studio
license terms. Use on Windows only, preserve Microsoft's notices and do not
misrepresent Microsoft endorsement. See the retained Windows-Python binary
conditions and Microsoft's original terms:

- https://learn.microsoft.com/en-us/visualstudio/releases/2026/redistribution
- https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files
- https://visualstudio.microsoft.com/license-terms/
- `licenses/Microsoft-runtime/CPython-WINDOWS-BINARY-CONDITIONS.txt`

Windows 10/11 supplies UCRT and API sets. This candidate no longer redistributes
copies of those OS files collected from an unrelated program on the build PC.

## Build-only packages

PyInstaller 6.22.3 (GPLv2-or-later with bootloader exception / selected Apache-2.0
files), pyinstaller-hooks-contrib 2026.9, altgraph 0.17.5 (MIT), packaging 26.3
(Apache-2.0 OR BSD-2-Clause), pefile 2024.8.26 (MIT), pywin32-ctypes 0.2.3
(BSD-style) and setuptools 65.5.0 (MIT) retain their copied notices and source
archives. Pip 24.0 is recorded as the existing environment's installer; it is not
intentionally included in the application. Collected build-tool notices do not
mean each whole tool is bundled inside the EXE.

## SimConnect component identity

The unmodified DLL comes from the official SimConnect 0.4.26 wheel and sdist:
58,368 bytes; SHA-256
`677fd3849d54e2a6831dc1aa348d974ead2255ec609fbf5830ef32bf0804b8bc`.

## Source access and primary references

Own source and collected upstream sources are separate, matched release assets.
Read SOURCE_ACCESS.md; publish the full source asset beside the binary and
verify its final URL before enabling public downloads. No flight-data upload
or disclosure is required to obtain source.

- https://pypi.org/project/SimConnect/0.4.26/
- https://github.com/odwdinc/Python-SimConnect/blob/master/LICENSE
- https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright
- https://github.com/python-pillow/Pillow/blob/main/LICENSE
- https://pyinstaller.org/en/stable/license.html
- https://docs.flightsimulator.com/html/Introduction/SDK_EULA.htm
- https://www.gnu.org/licenses/agpl-3.0.html
