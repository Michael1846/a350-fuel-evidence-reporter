# A350 Fuel Evidence Reporter

**0.7.11-rc2 — local Windows release-validation candidate, based on v0.7.10.**
Public release is on HOLD pending license/source clearance and acceptance tests.

Free, independent community software for the iniBuilds A350 in MSFS 2024.
Public publisher name: **Brazzor**. Selected private repository account: **Michael1846**.
Records SimConnect telemetry, direct per-engine fuel-flow LVars, N1 and anti-ice;
compares SimBrief planning with measured fuel; captures screenshots and exports
local CSV, PDF and evidence ZIP files. No automatic flight-data uploads.
SimBrief is contacted only when the user requests an online import.

## Windows use

Use the newly built Windows ZIP in `release/`. Extract the whole folder and run
`A350FuelReporter.exe`; keep `_internal` beside it. Python is bundled. The UI
opens on `http://127.0.0.1:8087`. Close the console with Ctrl+C when finished.

Data is stored at `%LOCALAPPDATA%\A350FuelReporter`, independently of the program
folder. See [Windows instructions](README-WINDOWS.txt) for migrating an existing
v0.7.10 data folder after making a backup, with both versions closed.
No automatic import of existing flight recordings is performed.

## English illustrated documentation

- [User Guide - installation, recording and manual evidence submission](docs/manuals/A350_Fuel_Evidence_Reporter_User_Guide_EN.pdf)
- [iniBuilds Data & Evidence Reference - CSV fields, sources and interpretation](docs/manuals/A350_Fuel_Evidence_Reporter_iniBuilds_Data_Reference_EN.pdf)

Creating a report or evidence ZIP only saves a local file. To report an issue,
attach the chosen package manually in the iniBuilds forum, Discord or another
support channel. The Reporter does not automatically send recordings or reports.
The explicitly requested SimBrief OFP fetch does not upload the recorded flight.

Known rc2 data-label issue: `true_track_deg` contains radians in the reviewed
acquisition path. Retain the original and derive degrees separately as described
in the technical guide. No code correction is included in this documentation update.

## Development and build

The inspected build uses Windows 10/11 x64 / CPython **3.11.9**, with exact dependencies
in `requirements-build.txt`. Create a virtual environment, install that file,
then run `scripts/prepare_windows_runtime.py`, `scripts/collect_licenses.py`, `scripts/run_checks.py` and
`scripts/package_release.py --build`. `build_windows_exe.bat` performs these steps.
The source-start script uses the pinned runtime dependencies.

Packaging exports only application code, static resources, tests, documentation,
license material and build scripts. It refuses data folders inside the binary
build and never copies recordings from the old installation. The Windows ZIP
includes `APPLICATION_SOURCE.zip`. Hashes and a binary file inventory accompany
it. The packaging command creates **local candidates**, with no upload/publishing.

## Release and licensing

`scripts/dependency_sources.py --download` retrieves exact upstream source
archives and records their hashes; `scripts/collect_source_notices.py` collects
native notices from the retrieved MuPDF source without executing archive content.
The expanded audit collects 33 source archives and matches every shipped native
binary to an official upstream artifact or the stable Microsoft Redist tree.
The full `CORRESPONDING_SOURCE.zip` is a separate release asset; see
[source access](SOURCE_ACCESS.md) and [source build](docs/SOURCE_BUILD.md).

- [Current license review and blockers](docs/LICENSE_REVIEW.md)
- [Release checklist](docs/RELEASE_CHECKLIST.md)
- [GitHub draft release procedure](docs/GITHUB_RELEASE.md)
- [Validation evidence](docs/VALIDATION.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)
- [Changelog](CHANGELOG.md)
- [Simulator flight acceptance checklist](FLIGHT_TEST_CHECKLIST.md)

Own application code is prepared under **AGPL-3.0-only**; see LICENSE and NOTICE.
Third-party terms remain applicable. APPLICATION_SOURCE.zip contains the own
application; the full source asset adds native/dependency sources, build inputs,
notices and hashes. The exact Microsoft SimConnect DLL's redistribution terms
and AGPL-combination basis remain open. This candidate has not been cleared by
the project for public release. Other acceptance tests remain separate tasks.

Exports are user-controlled local files. Review screenshots, OFP, remarks and OIS
attachments before sharing. Missing evidence remains advisory; it does not block
exports. No mandatory redaction or separate export modes were introduced.

Historical development notes and previous validation caveats are preserved in
[development history](docs/DEVELOPMENT_HISTORY.md). Automated checks do not replace
full simulator or clean-machine acceptance.

Independent project; not affiliated with or endorsed by iniBuilds, Airbus,
Microsoft or Navigraph. For simulation and software issue reporting only.
