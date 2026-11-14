# Validation — 0.7.11-rc2, 2026-11-09

Publisher: Brazzor. Technical validation results and acceptance checks are
recorded below.

## Completed checks

| Check | Observed result |
|---|---|
| Regression suite | 80 tests passed on Windows x64 / CPython 3.11.9 in 5.359 seconds |
| Full-source endpoint | Missing archive handled; multi-chunk synthetic archive served with correct content length |
| Local request boundaries | Invalid Host/Origin/cross-site requests, wrong token and non-JSON posts rejected |
| Existing Windows fixes | Exclusive port ownership and old CSV migration regression checks pass |
| Final Windows build | PyInstaller 6.22.3, pinned environment, official stable x64 Microsoft CRT inputs |
| CRT signatures | All three copied CRT DLLs have valid Microsoft Authenticode signatures |
| Native mapping | 36 shipped DLL/PYD files; all 36 matched to official wheels, official CPython or stable VC/Redist |
| Removed accidental inputs | UCRT/API-set copies from an unrelated application are excluded; Windows 10/11 provides them |
| EXE startup | Started hidden with system-only PATH and no PYTHONPATH/PYTHONHOME; browser disabled for test |
| Packaged UI/legal/source guide | Version, UI, AGPL, notices, application source and full-source instructions served |
| Packaged exports | Synthetic metadata save, PDF, evidence ZIP and both CSV endpoints succeeded |
| Data location | Synthetic case stored only in isolated external data directory |
| Duplicate instance | Second instance exits with port-conflict notice; original remains reachable |
| Source collection | 33 source archives verified against recorded hashes; upstream/build recipe identities retained |

The tested final EXE SHA-256 is
`cb3b77618e2ab0e8cb8013766da2c11fe43207a964f7873fb33e36bc4b117e94`.
Raw evidence: audit/tests.log, audit/test-result.json, audit/pyinstaller.log,
audit/exe-smoke.json and audit/build-inputs.json. Native/source evidence:
BINARY_SOURCE_MAP.json, SOURCE_COMPONENTS.json and licenses inventories.

Final assets are in release/0.7.11-rc2. SHA256SUMS.txt identifies application
source, Windows ZIP, full source ZIP and the release manifest. The final package
verification report is generated after assembly in audit/source-package-verification.json.

## Limits

The EXE ran on the development PC, which already has Python and MSFS installed.
System-only PATH testing is not a clean Windows VM test. No live simulator
connection/flight, new screenshot, hotkey acceptance or external SimBrief import
was performed here. All flight data was synthetic and local. Existing user
recordings were not imported, changed or uploaded.

Upstream native sources and wheel identities are supplied, but independent native
rebuilds and byte-identical reproduction of every upstream wheel were not claimed.
Microsoft SimConnect.dll's exact redistribution/AGPL-combination basis remains
open. Public source-download availability must be verified when GitHub is set up.
No malware verdict, EXE signature or SmartScreen reputation is asserted.
