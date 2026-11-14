# A350 Fuel Evidence Reporter v0.7.10 — Multi-monitor screenshot auto-detection, Fuel Evidence and Flight Analytics

## Status

Local Windows-oriented Python application with a browser-based user interface and SimConnect integration. This is a source-code prototype, **not a verified Windows standalone executable**. Live operation with MSFS 2024 and the iniBuilds A350 v1.2.8 remains **unverified**. All user-facing screens, status messages, checklist labels, documents, and generated report headings are intended to be in English.

## Features

- **Connect to MSFS & arm recording:** connect to SimConnect, identify aircraft title/model and installed add-on version when discoverable, and display variable diagnostics. Automatically begin recording when at least one engine is running, stop when both engines have shut down (two consistent status polls), and resume on restart. The SimConnect connection and screenshot functions remain available with engines off. Record flight telemetry approximately every 5 seconds while engines run, including fuel on board, engine fuel flow, position, speed, altitude, wind and vertical speed. Check actual value accuracy against the cockpit.
- **SimBrief:** optionally import the latest OFP, route and available fuel planning fields with your SimBrief pilot ID. An OFP PDF can also be uploaded manually.
- **Waypoint fuel checks:** record actual vs. planned FOB at geolocated waypoints. Store waypoint checks separately from continuous telemetry. GPS matching does not confirm the currently active FMS leg.
- **Evidence checklist:** preflight FMS fuel prediction, FMS destination EFOB at pushback, repeated enroute EFOB observations, engine FF screenshots, actual runway-vacating FOB, and OIS `.bin` saves. Required fields depend on the selected report category. Missing attachments produce warnings **without preventing telemetry, PDF or ZIP exports**.
- **Screenshots and remarks:** use **Ctrl + Shift + F10** on Windows to capture the foreground window with the most recent available SimConnect sample. Manually uploaded images do not inherit a fictitious historical GPS position. Add individual remarks and group multiple screenshots in a custom before/after order. Each retains its own UTC/GPS/FOB/FF context.
- **Event groups:** attach multiple screenshots, FMS observations and any number of OIS autosaves to a single event. Choose the event's GPS anchor when more than one capture is available.
- **Route & evidence overview:** planned SimBrief route, actual recorded GPS track with missing segments preserved, event markers at recorded coordinates, and a UTC-sorted timeline.
- **Standard iniBuilds PDF/ZIP:** flight summary, route and evidence map, waypoint fuel analysis, flight profile, chronological evidence entries with linked screenshot groups, evidence completeness notes and PDF bookmarks. Export a separate evidence ZIP with CSVs, OFP and attached `.bin` files. Incomplete cases remain exportable.

## Installation on Windows

1. Extract the ZIP into a dedicated folder. To migrate a previous flight from v0.6/v0.7, back up its `data/` directory, then copy it to the new directory **while the app is closed**. Existing `case.json` data fields remain compatible.
2. Install **Python 3.11 or 3.12, 64-bit**.
3. Double-click `start_windows.bat`. On first launch, it creates `.venv` and installs dependencies from `requirements.txt` (internet required for installation). The local app opens at `http://127.0.0.1:8087`.
4. Select **Flight & OFP**. Optionally import SimBrief, connect to MSFS and check SimVar diagnostics. Verify simulator time/weather settings manually.
5. Use **Evidence checklist** for preflight tasks. During the flight, capture screenshots using **Ctrl + Shift + F10**, add remarks and repeated manual FMS EFOB readings in **Screenshots & FMS**.
6. Review route points and event marker locations under **Route & events**, then generate reports under **Report & Export**.

## Safety, privacy and limitations

- **[Unverified]** Real SimConnect data accuracy and aircraft build detection for iniBuilds A350 1.2.8, Windows global hotkey, and fullscreen screenshot capture require testing on a live simulator.
- A readable SimVar may still disagree with the cockpit. Direct LVar reading is available. The user has identified `L:INI_FUEL_FLOW1` and `L:INI_FUEL_FLOW2` and checked their kg/s output against the A350 ECAM. Both are enabled by default for new configurations. These are user-tested readings, not manufacturer-certified across versions. An existing saved `data/engine_sources.json` is preserved without modification.
- Uploaded screenshots may reveal personal details and are **not automatically redacted**. The OFP can be redacted using configured text terms; review all exported materials before sharing.
- A file captured after takeoff cannot be automatically treated as verified preflight evidence. Exports are never blocked for missing evidence.
- The app is for flight simulation and software bug reporting only, not real-world navigation or aircraft performance certification.

## Technical modules

`app.py` (API/server), `simbridge.py` (SimConnect), `simbrief_client.py` (OFP), `telemetry_store.py` (5-second CSV), `evidence_checklist.py` (evidence checklist), `evidence_groups.py` (grouped evidence), `evidence_capture.py` (screenshot hotkey), `event_timeline.py` (UTC/event IDs), `route_map.py` (GPS lines/markers), `report_v07.py` (PDF), `static/` (web UI), `tests/` (automated tests).

See `FLIGHT_TEST_CHECKLIST.md` for the detailed first-flight acceptance checks.

## Windows EXE build compatibility fix (introduced in v0.7.2)

The internal file `workflow.py` has been renamed to `evidence_checklist.py`. PyInstaller's `hook-workflow.py` targets a third-party distribution named `workflow` and previously attempted to load absent distribution metadata for our local `workflow.py`, aborting the build with `PackageNotFoundError: No package metadata was found for workflow`. This application now avoids that name collision.

**Rebuild:** run `build_windows_exe.bat` from the freshly extracted current release folder (with the simulator closed or open). A successful build writes `dist\A350FuelReporter\A350FuelReporter.exe`. Move the whole `dist\A350FuelReporter\` directory if distributing the EXE; do not copy the .exe alone. The Python-based `start_windows.bat` remains available and does not require making an EXE.

This fix is checked by static analysis and application unit tests on Linux. A real PyInstaller build on Windows must still be verified on a Windows PC.

## Automatic engine-based telemetry start/stop (v0.7.3)

Click **Connect to MSFS & arm recording** while engines are off. The app stays connected and provides aircraft identity, diagnostics, screenshot capture, SimBrief import, and manual FMS observations, but writes no 5-second telemetry or GPS waypoint checkpoints until **at least one engine** is detected running. When **both engines are off** for two consecutive SimConnect samples, recording pauses automatically. If either engine restarts, recording resumes using the existing flight data without clearing prior samples.

Engine detection queries `ENG COMBUSTION:1/2` (fallback `GENERAL ENG COMBUSTION:1/2`) and engine FF. FF is used as a fallback because some third-party aircraft expose incomplete standard variables; N1 alone is deliberately not accepted because of possible windmilling. If no reliable running signal is available, recording does **not** start automatically and the UI displays the detector state. Actual detection requires a live A350 test. A new recording segment does not calculate derived burn across the engine-off interval.


## Per-engine fuel-flow acquisition and diagnostics (v0.7.4)

This release fixes two code-level issues in v0.7.3:

1. Python-SimConnect 0.4.26's `AircraftRequests.get("...:1")` and `get("...:2")` dynamically redefine a shared indexed request. Engine 1 and Engine 2 now use permanently separate read-only `Request` objects for each indexed SimVar, including combustion and N1.
2. The old fuel-flow fallback accepted a zero from `TURB ENG FUEL FLOW PPH` and never checked `ENG FUEL FLOW PPH`. Both PPH signals are now inspected; positive `ENG FUEL FLOW PPH` is selected if the turbine flow signal is zero/missing. If both PPH sources are unavailable, `ENG FUEL FLOW GPH` can be converted using the *actual* `FUEL WEIGHT PER GALLON` SimVar, when both report usable values. No density default is fabricated.

Go to **Flight & OFP → Engine fuel-flow source diagnostics** to inspect original PPH/GPH values, combustion flag, N1, selected source and warning codes per engine. Use **Download fuel-flow diagnostics (JSON)** while connected and engines running. If all standard sources return zero/missing while combustion is active, the app reports `MISSING_WHILE_RUNNING`. Engine 1/2 FF and their sum remain blank instead of displaying fabricated values. If two simultaneously positive sources disagree by more than 15%, a diagnostic note requests a cockpit comparison.

The CSV and normal iniBuilds PDF retain existing structures and semantics; only genuinely acquired FF values appear in engine FF and total FF fields. Engine on/off recording remains controlled by combustion with FF fallback. **Live iniBuilds A350 compatibility remains unverified** until the simulator test. Source diagnostics can show whether an aircraft-specific LVar adapter is required; no private LVar name is assumed.

To update from v0.7.3: exit the old program, back up `data/`, extract v0.7.4 into a **new folder**, migrate `data/` if desired, then launch `start_windows.bat` or rebuild the EXE with `build_windows_exe.bat`. A prebuilt EXE is not included. Use the new EXE rather than an older `dist/` directory after rebuilding.


## Direct aircraft FF sources and N1 (v0.7.5)

The user-supplied iniBuilds A350 diagnostic showed **combustion=1** and **N1 around 85.35% on both engines**, with zero from `TURB ENG FUEL FLOW PPH`, `ENG FUEL FLOW PPH` and `ENG FUEL FLOW GPH`. Therefore the standard SimVars **must not** be represented as actual engine fuel flow. N1 is already measured directly using indexed `TURB ENG N1:1` and `TURB ENG N1:2`; this version also displays N1 on the main dashboard and renders both engines in the 5-second flight profile and standard PDF. The CSV fields are `engine1_n1_pct` and `engine2_n1_pct`. Per-engine FF source provenance is also stored per sample as `engine1_ff_source` and `engine2_ff_source`. This is an actual SimConnect reading, not an estimate.

A **read-only, optional, independently indexed LVar adapter** is available at **Flight & OFP → Aircraft-specific direct engine fuel-flow source**. It reads configured aircraft variable names through SimConnect and supports explicit units `kg/h`, `lb/h`, `kg/min`, `lb/min`, `kg/s`, `lb/s`; no fixed conversion factor or variable name is guessed. The resulting per-engine values can populate FF1, FF2 and total FF, telemetry CSV, screenshots and the PDF, **only if configured variables exist and return valid values**. The diagnostic shows the exact source and status `DIRECT_LVAR_UNVERIFIED` until verified against the engine display. A name that returns zero/missing does not count as a valid reading, and corrected/normalized FF is *not* substituted for actual FF.

**How to identify a real iniBuilds variable:** With the MSFS aircraft installed, you can optionally use the **Search locally installed aircraft files** control to find candidate `L:` or `Z:` names in readable files. This scan is read-only, cannot inspect encrypted aircraft systems, cannot discover every runtime LVar and does not validate matches. Alternatively inspect active LVars using an appropriate external MSFS LVar diagnostic utility with known readout access; compare candidate values against the corresponding cockpit FF indication in at least two distinct engine states, then configure each engine's verified name and unit. Neither a guessed name nor an unchanging positive value proves fuel-flow accuracy. If no candidate is available, keep FF1/FF2 blank rather than guessing.

The live diagnostics JSON includes both N1 values, configured custom variable names, raw returns, selected sources, and status for each engine. Do not distribute the source profile as a universal A350 reference without validating it against the specific aircraft version.

**Test plan:** connect with both engines off; start engine 1 and verify N1 responds while telemetry starts; start engine 2 and compare both displayed N1 values with the cockpit. Confirm CSV and PDF N1 lines follow the values over time. If discovered, configure each engine FF source, compare its live kg/h conversion against the cockpit at idle and a higher stable thrust setting, then download the diagnostics JSON and verify both `ff...` fields and provenance. Ensure `FF Total = FF1 + FF2` only when both are available. Confirm shutdown stops telemetry and restarting resumes without a discontinuous burn calculation.

**Current validation boundary:** unit tests for per-engine request creation, conversion and telemetry pass in this environment; **the precise iniBuilds A350 FF variables are still not verified in a real simulator**. Windows/PyInstaller execution is also unverified.

## v0.7.6: engine anti-ice switch states

Both engine anti-ice states are captured independently while connected to MSFS:
`L:INI_ENG_ANTI_ICE1_STATE` / `L:INI_ENG_ANTI_ICE2_STATE` are the manufacturer-documented iniBuilds A350 switch-state LVars (from the official February 2025 A350 LVar listing). The reader also queries the documented MSFS 2024 SimVars `ENG ANTI ICE:1/2` and `GENERAL ENG ANTI ICE POSITION:1/2`. Requests have fixed engine indices; there is no write/control action.

The dashboard displays **ON**, **OFF**, or **N/A** with the selected source. A diagnostic table exposes all three readings; `CONFLICT_CHECK_COCKPIT` warns when their states disagree. An **OFF** reading is accepted as a real zero-state indication, not treated as a missing value. However, a SimConnect value does not independently prove the overhead-panel indication, that a bleed-air valve is physically open, or that ice protection is effective. The live iniBuilds 1.2.8 integration must be checked in the cockpit.

The existing engine-running recording gate is unchanged: status reads continue on the live connection, whereas the CSV is saved only every five seconds while recording is armed and at least one engine is running. The CSV includes numeric columns `engine1_antiice`, `engine2_antiice` (0/1 or blank) plus `engine1_antiice_source`, `engine2_antiice_source`. These columns are added automatically to older cases without removing existing records. New screenshots retain their own original ON/OFF/unknown values and provenance. Standard English PDF reports include an anti-ice state summary, first observed state and subsequent observed changes (in UTC), and the individual anti-ice states per screenshot. This does not affect standard flight analysis or evidence exports.

Source documentation: https://forum.inibuilds.com/topic/25015-key-lvars-list-a350/ and https://docs.flightsimulator.com/msfs2024/retail/programming-apis/simvars/aircraft-simvars/aircraft-engine-variables/


### v0.7.7 – Historical: iniBuilds fuel-flow candidate probe (superseded by v0.7.9)

The independent read-only probe polls `L:INI_FUEL_FLOW1` (reported by a tester) and `L:INI_FUEL_FLOW2` (parallel candidate, existence **not independently verified**) during the live SimConnect session. Open **Flight & OFP → Engine fuel-flow source diagnostics** to see the raw value and probe status. A value of zero does not establish that an LVar exists. At that point the units had not yet been checked against the cockpit; see v0.7.9 for the user-confirmed kg/s mapping.

The probe **does not** automatically fill FF1/FF2. To activate recording, first compare the raw values to ECAM under stable engine conditions and identify their unit. Then click **Fill INI_FUEL_FLOW1 / INI_FUEL_FLOW2 candidates**, explicitly choose the correct units for both engines, and click **Save direct FF sources**. Confirm FF1 and FF2 against cockpit readings; the evidence ZIP retains the source configuration.

**Do not use engine `Corrected FF` or N1 as a substitute for fuel flow.** Recording, reports, and older `data/` folders remain compatible. If neither candidate returns valid data, export the diagnostic JSON and keep investigating. No in-simulator end-to-end verification has been performed for these names.

## v0.7.8 – Automatic MSFS display screenshots on multi-monitor PCs

**Default screenshot target: `MSFS monitor (automatic, recommended)`.** The app uses the native Windows top-level window list to identify the Microsoft Flight Simulator 2024 / 2020 game process and its non-minimized main window. `MonitorFromWindow` selects the monitor that contains the greatest portion of the simulator window; `GetMonitorInfoW` supplies the monitor's exact desktop coordinates. Each screenshot uses Pillow `ImageGrab.grab(bbox=..., all_screens=True)`, including negative X/Y coordinates for monitors to the left or above the primary screen. The target is evaluated anew for each screenshot, so moving MSFS between displays is supported.

The **Ctrl+Shift+F10 hotkey** always uses automatic MSFS monitor detection, regardless of which application has keyboard focus; the browser **Capture screenshot + GPS** button uses the area selected in the dropdown, now defaulting to automatic mode. Manual fallbacks include an individual detected Windows display (added dynamically), the active window, the primary monitor, or all monitors. The detected MSFS display and its resolution appear above the capture controls, updated every five seconds. The selected monitor and method are preserved inside the individual screenshot's JSON context and evidence report.

**Safety:** If MSFS is minimized, cannot be identified, or has multiple ambiguous windows, automatic capture aborts with a clear error; it never silently captures the browser or another monitor. No automatic/background screenshot is taken: a screenshot still requires an explicit button or hotkey action. The display capture is pixel-based: if another window obscures the simulator on the same monitor, that overlay may be visible. Windows exclusive fullscreen or GPU-protected content can produce a black screenshot; use a manual screenshot upload if that happens. The detector does not move/focus the simulator and does not manipulate Windows display settings.

**Test:** With MSFS on a secondary display, open the Reporter on the primary display. In **FMS & Evidence** verify `Auto-detected MSFS display: ...`, then click **Capture screenshot + GPS** from the browser and press **Ctrl+Shift+F10** while a different app is active. Both should capture the MSFS monitor. Move MSFS to another screen and repeat; the status should follow the game. Minimize MSFS and repeat: auto capture must fail without recording the browser. Test the explicit manual display option if auto detection does not work with your custom window configuration. The Python unit tests cover selection, negative coordinates, failed detection and saved display provenance. A real multi-monitor Windows/MSFS test is still **unverified** in this environment.


## v0.7.8.1 - Version label correction

Corrects an outdated hard-coded `Version 0.7.4` label in the HTML header. The screenshot and monitoring features from v0.7.8 were already included; this patch does not add data-collection capabilities. Rebuild a previously created Windows EXE for the corrected label to appear, and close older instances using the same localhost port.


## v0.7.9 – User-confirmed iniBuilds FF defaults and Anti-Ice CSV display

On a **new** installation without `data/engine_sources.json`, both fuel-flow sources are automatically set to `L:INI_FUEL_FLOW1` / `L:INI_FUEL_FLOW2`, each in **kg/s**. Per-engine kg/h values use `raw × 3600`; total FF is their sum. This mapping was checked by the user against the iniBuilds A350 ECAM in MSFS 2024, but has not been independently verified for other aircraft versions. Standard FF SimVars and corrected FF remain diagnostic only when they return zero or non-equivalent readings. Source provenance stays in the CSV and diagnostics.

Existing saved `data/engine_sources.json` settings are **never overwritten**. If you previously configured `INI_FUEL_FLOW1/2` using the wrong `kg/h` unit, change each engine unit to `kg/s` via **Flight & OFP → Aircraft-specific direct engine fuel-flow source**, then save. Old telemetry values are not recalculated, since they reflect the settings at their actual capture time; be careful when analyzing historical incorrectly scaled rows.

The recent-telemetry table now accepts Anti-Ice `0`, `1`, `0.0`, `1.0` and equivalent numeric strings, correctly showing **OFF/ON**. New telemetry CSV rows store the anti-ice switch state as integer **0** or **1**, while the older saved CSV rows are kept unchanged and remain readable. Missing/invalid readings show **N/A**, not OFF. The PDF and screenshot context continue to include anti-ice status and source.

## v0.7.10 – Standard flight analysis only / reliable version identification

The optional Real-World Benchmark page, its endpoints, its separate PDF report and simulator-history archiving are removed. The standard SimBrief-vs-actual flight analysis, route/evidence map, telemetry CSV, engine FF, N1, anti-ice, screenshots, checklists and normal PDF/ZIP exports remain unchanged. Old `historical_simulator_flights.json` files are not deleted or modified by this release.

The header displays the running backend version instead of relying on a hard-coded label. `GET /api/version` returns the current application version. The server responds to pages and JavaScript with `Cache-Control: no-store`. The console also prints the application version at startup.

**Important when using a Windows EXE:** Rebuild it with `build_windows_exe.bat` for each update. Stop old A350FuelReporter processes before starting the new build; merely replacing the source folder does not modify an existing EXE. Restart and use Ctrl+F5 in the browser. Back up and reuse the complete `data` directory to retain flight records.
