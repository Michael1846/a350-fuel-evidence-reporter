# Source access — 0.7.11-rc2

Publisher: Brazzor. Application license: GNU AGPL version 3 only. Third parties
retain their licenses; Microsoft binaries are not relicensed under the AGPL.

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

The GitHub repository/tag has not yet been selected or published. Before any
public binary download is enabled, the publisher must check that the matching
full source archive is accessible at the same release and fill the final release
URL into this document. This is a publication step; no fake download URL is used.

This candidate's technical source collection has been assembled. The Microsoft
SimConnect binary's applicable redistribution terms and AGPL-combination basis
remain unresolved. The filename CORRESPONDING_SOURCE describes the intended
release asset; it does not assert that the proprietary DLL has source available
or that its source is exempt without a valid licensing basis. See
`docs/LICENSE_REVIEW.md` for the precise open point.
