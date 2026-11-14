# Source access — 0.7.11-rc2

Publisher: Brazzor.

Every public binary release must offer these version-matched assets together,
free of charge and without requiring a flight-data upload:

- `APPLICATION_SOURCE.zip`: application code, UI, tests, build scripts and notices.
- `CORRESPONDING_SOURCE.zip`: the same application archive, pinned upstream source
  archives, native dependency sources, exact build-runtime inputs and a manifest.
- `SHA256SUMS.txt` and `release-manifest.json`: identity of the binary/source assets.

Extract the application-source archive and read `docs/SOURCE_BUILD.md` for the
build procedure. The full source archive is a separate download to keep the
Windows application download small. When provided beside the executable, the
local UI can serve the full archive through its Full source package link.

Private source repository: https://github.com/Michael1846/a350-fuel-evidence-reporter.
A public release/tag has not been published. Before any
public binary download is enabled, the publisher must check that the matching
full source archive is accessible at the same release and fill the final release
URL into this document. This is a publication step; no fake download URL is used.

The full source archive contains the application, collected upstream sources,
build inputs and component provenance. Proprietary Microsoft source code is not
part of the project source.
