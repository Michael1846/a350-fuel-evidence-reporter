# Changelog

## 0.7.11-rc2 — 2026-11-09

- Assemble 33 pinned source archives and version-specific native license evidence.
- Match native binaries to official upstream artifacts.
- Select CRT files from official stable Microsoft Redist, avoiding unrelated PATH copies.
- Use Windows 10/11 system UCRT/API sets; add full-source access instructions.
- Preserve an explicit unresolved SimConnect licensing item; no public release clearance.

## 0.7.11-rc1 — 2026-11-09, local validation candidate

- Prepare AGPLv3 project licensing, installed dependency notices and release gates.
- Store new user data outside the application directory, preserving upgrade data.
- Add local Host/Origin/JSON request checks and an exclusive Windows listener.
- Close old CSV read handles before atomic schema migration on Windows.
- Add visible license, notices and matching application-source links.
- Pin inspected build versions; package own source and binary hashes with the EXE.
- Keep local evidence exports, telemetry behavior and screenshot workflow.

Public release is on HOLD pending detailed license/source clearance, publisher
identity, clean-machine validation and simulator acceptance.

## 0.7.10 — imported baseline

Standard flight analysis only, runtime version identification, no-store UI;
existing fuel-flow, N1, anti-ice, screenshots, SimBrief, PDF, CSV and ZIP features.
See docs/DEVELOPMENT_HISTORY.md for original development notes and limitations.
