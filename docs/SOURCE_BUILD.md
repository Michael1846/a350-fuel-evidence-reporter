# Source build — 0.7.11-rc2

Publisher: Brazzor. Intended platform: Windows 10/11 x64. No MSFS or SDK source,
private flight data, simulator installation or Python virtual environment is
redistributed as project source.

## Build the Windows application

1. Extract APPLICATION_SOURCE.zip into a new work folder.
2. Install CPython 3.11.9 x64 and stable Microsoft Visual Studio C++ Build Tools
   with the x64 VC Redist component. The compiler and Windows SDK are general
   build tools, obtained under their own terms; they are not AGPL source assets.
3. Create a virtual environment and install requirements-build.txt. The five
   runtime Wheels used by this build are preserved in the full source package
   under binary-build-inputs/wheels, with hashes. The remaining build-tool
   versions are pinned and their source archives are included.
4. Run scripts/prepare_windows_runtime.py. This reads the installed stable
   Visual Studio VC/Redist tree and copies three unmodified x64 CRT DLLs into
   build-inputs/msvc-runtime, recording their hashes and original Redist paths.
   For an exact CRT-input match, the archived binary-build-inputs/microsoft-crt
   files can be used under their retained Microsoft terms; verify runtime.json.
5. Run scripts/collect_licenses.py, then scripts/run_checks.py.
6. Run scripts/package_release.py --build --output release/local-rebuild.
   Keep the complete resulting A350FuelReporter folder; do not move the EXE alone.
7. To reassemble the full source asset, restore upstream-sources into
   release/dependency-sources, source-evidence/fetch.json into
   audit/license-audit/fetch.json, and binary-build-inputs/wheels into that same
   audit/license-audit directory. These are supplied inside the full source ZIP.
   Then run scripts/assemble_source_package.py --inventory-only and reassemble
   using --release pointing to the prepared application-release directory.

build_windows_exe.bat automates the normal installed-tool build. A rebuilt EXE
need not be byte-identical because PE timestamps and packaging metadata vary.
Build-input hashes prevent a package from silently claiming to match stale code.
The current verification results are in VALIDATION.md.

## Modify/rebuild third-party native libraries

The upstream source archives are unmodified, retained in upstream-sources, and
identified by SOURCE_COMPONENTS.json. Extract into separate directories, preserving
all original notices. These are upstream build entry points, not claims that
independent native rebuilds were performed during this audit:

- **CPython 3.11.9**: PCbuild/readme.txt and PCbuild/build.bat. PCbuild/python.props
  records bzip2 1.0.8, XZ 5.2.5, libffi 3.4.4, OpenSSL 3.0.13 and zlib 1.3.1.
  Pinned source snapshots from python/cpython-source-deps are included. Other
  CPython native sources, including bundled Expat, are in the CPython archive.
  Use the documented external-directory layout and a licensed Windows SDK/MSVC.
- **PyMuPDF 1.28.2 / MuPDF 1.28.2**: PyMuPDF setup.py/pyproject.toml and the full
  MuPDF archive, including thirdparty source directories, generated-binding
  sources and Make/Makethird/Windows build files. PYMUPDF_SETUP_MUPDF_BUILD can
  select the extracted MuPDF source tree. Follow upstream instructions for SWIG
  and the Windows compiler rather than substituting a different MuPDF version.
- **Pillow 12.3.0**: its full repository snapshot includes .github/dependencies.json,
  wheel workflows, winbuild/build.rst and winbuild/build_prepare.py, which the
  PyPI source archive alone did not include in full. Use --architecture AMD64,
  --depends to select the supplied dependency cache, and disable libimagequant
  and RAQM to match the observed wheel features. Build recipes/patches are in
  that full snapshot. The zlib-ng source snapshot must be renamed/arranged as
  the versioned archive/directory expected by the upstream script if necessary.
- **AVIF dependencies**: libavif 1.4.2 ext/aom.cmd and ext/dav1d.cmd / CMake modules
  pin AOM 3.14.1 and dav1d 1.5.3. These sources are separately included. The
  dav1d tag resolves to the same commit reported by the binary. NASM, Meson and
  CMake are general build tools and remain external prerequisites.
- **Python-SimConnect**: the exact 0.4.26 sdist contains the wrapper Python sources
  plus a proprietary SimConnect.dll. The latter is not native source code and
  is a separate binary component.
- **ReportLab/charset-normalizer** and build tools: the pinned sdists include
  upstream build metadata; follow their original instructions. ReportLab also
  includes the preferred DarkGarden font source (.sfd); fonts not collected into
  this Windows binary are not claimed to be runtime components.

No changes to upstream native code are introduced by this project. Supplying
source/build recipes and proving a wheel's byte identity are distinct from
independently reproducing that upstream binary. Microsoft CRT/OS library source
is not included or claimed; those libraries retain their own redistribution terms.
