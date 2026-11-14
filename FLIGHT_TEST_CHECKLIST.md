# A350 Fuel Evidence Reporter — First Flight Test Checklist (v0.7.10)

## Before pushback

1. Launch the app from `start_windows.bat`, open **Flight & OFP**, and connect to MSFS. Check that the aircraft identity, version and SimVar diagnostics are plausible. Note any missing or unexpected values.
2. Import the current SimBrief OFP using the pilot ID or attach its PDF manually. Confirm **Live Time** and **Live Weather** in the app only if they are enabled in MSFS.
3. Use the **Evidence checklist** and capture the FMS FUEL & LOAD / fuel prediction screen **before pushback**. The screenshot timestamp should be tied to a valid GPS/SimConnect sample if available. Record FMS destination EFOB manually.
4. With both engines off, verify that the SimConnect connection remains active but **telemetry does not start**. Start engine 1 and verify the first 5-second sample appears; start engine 2 and confirm recording continues. Check FOB, FF1, FF2, GPS and flight status. After landing and engine shutdown, verify recording stops automatically after two consecutive polls, and resumes on engine restart without deleting previous data.

## During flight

5. Record multiple manual FMS destination EFOB measurements whenever needed. Add a remark and flight phase each time.
6. To document a before/after issue, create an evidence group, select it as the active hotkey group and press **Ctrl + Shift + F10** for each screenshot. Check that each image retains its own UTC/GPS/altitude/FOB/FF data.
7. Reorder images and write a group-level remark explaining the changes between Screenshot 1, 2, 3, etc. You may also add individual screenshot remarks.
8. For high fuel flow, attach the engine display and FMS FUEL & LOAD screenshots, and record a manual description of the flight phase.
9. If available, create an OIS autosave (.bin) at the time of an issue and upload it afterwards. Multiple autosaves may be linked to different event groups; **missing saves do not block recording or export**.
10. Review the route and event map. Verify that event markers show stored GPS positions and are not incorrectly snapped to the planned route.

## After landing

11. Record actual FOB when vacating the runway (not at the gate).
12. Generate the standard PDF and evidence ZIP. Verify UTC event order, waypoint fuel comparison, telemetry plots, map markers, screenshot group order and separate individual capture metadata.
13. Confirm both exports work even with missing `.bin` files or screenshots. Export the 5-second telemetry CSV and waypoint CSV if needed.
14. Confirm the app header displays version 0.7.10 and the standard fuel report works without a benchmark page.
15. Review the OFP redactions and every screenshot for sensitive personal information before sharing.

**Validation status:** Full MSFS 2024 / iniBuilds A350 v1.2.8 testing has not yet been performed. Document any runtime errors and compare fuel, wind and speed readings against the cockpit.


### Engine fuel-flow verification (v0.7.5)

1. With both engines shut down, connect to MSFS and open **Flight & OFP → Engine fuel-flow source diagnostics**. Confirm that engine combustion is `0` or otherwise inspect the warning.
2. Start engine 1, then engine 2. Confirm that each engine has its own non-zero measured value in kg/h (when the cockpit shows fuel flow) and that **Total Engine FF** is the sum. Compare against displayed cockpit values; readings are not considered validated solely because SimConnect returned a number.
3. Inspect both raw `TURB FF` and `ENG FF` in lb/h, the selected source, N1 and any diagnostics. A zero on one channel must not hide a positive value on the other channel.
4. Click **Download fuel-flow diagnostics (JSON)** while both engines are running. Share this file if the cockpit shows non-zero FF but the app still shows blank or zero values. No personal data should be included in remarks; review the file first.
5. Check `telemetry.csv` fields `engine1_ff_kg_h`, `engine2_ff_kg_h`, and `total_ff_kg_h`. Missing values must remain empty, not zero, when combustion indicates running but all SimVars are unusable.
6. Shut down both engines: automatic 5-second recording should pause as in v0.7.3. On restart, recording resumes without erasing existing data.


### Direct FF and N1 cross-check (v0.7.5)

1. With engines at idle, verify **N1 Engine 1 (%)** and **N1 Engine 2 (%)** in the dashboard against the aircraft's engine display. Note whether both values rise separately with throttle changes.
2. Confirm the 5-second CSV contains `engine1_n1_pct` and `engine2_n1_pct`. The standard PDF flight profile must contain a **separate N1 panel**.
3. If standard FF variables show zero with engines running, do **not** treat the zero as measured fuel flow. Expand the optional source adapter in **Flight & OFP**.
4. Obtain actual engine-specific variable names and units independently. The local file scanner yields **unverified candidates** only; aircraft archives may be encrypted. Configure names/units only after examining the simulator's active variables.
5. If both named values return positive data, compare each FF to the corresponding cockpit indicator at two stable thrust settings, check `FF Total = FF1 + FF2`, and download **Download fuel-flow diagnostics (JSON)** for inspection. Any mismatch must be investigated; positive does not mean validated.
6. If no named source can be proven, leave FF1 and FF2 blank. Do not replace them with N1-derived or FOB-derived estimates. N1 and all other telemetry must continue to work.
7. Shut down both engines and confirm telemetry stops automatically; on restart, verify it resumes and all captured data remain present.

## Engine Anti-Ice 1 / 2 validation (v0.7.6)

- [ ] Connect with both engine anti-ice switches OFF; confirm live Engine 1/2 = OFF and check the selected LVar sources.
- [ ] Switch only ENG 1 ANTI ICE ON. Confirm Engine 1 = ON while Engine 2 remains OFF. Note time UTC and save a screenshot of the overhead panel.
- [ ] Switch ENG 2 ANTI ICE ON. Confirm both = ON; take another screenshot.
- [ ] Switch both OFF, independently, checking the two readings return to OFF.
- [ ] Examine **Engine Anti-Ice 1 / 2 – Source Diagnostics**. If a `CONFLICT_CHECK_COCKPIT` warning appears, export fuel-flow diagnostics JSON and record the overhead indication. Do not silently assume which source is correct.
- [ ] Confirm both states and source columns are present in the 5-second CSV, per-screenshot context, and standard PDF state-observation table.
- [ ] Confirm engine shut-down still stops the 5-second recorder, while the SimConnect live diagnostics stay available.
- [ ] Verify the actual readings against the iniBuilds A350 1.2.8 overhead panel; passing automated tests is not a real-aircraft compatibility claim.


### v0.7.7 – Engine fuel-flow LVar discovery

- [ ] Open Flight & OFP → Engine fuel-flow source diagnostics. Check `iniBuilds raw` for both engines.
- [ ] Confirm `L:INI_FUEL_FLOW1` responds to ENG 1 changes; evaluate `L:INI_FUEL_FLOW2` independently for ENG 2.
- [ ] Compare raw readings to the ECAM engine FF display and establish units (not just plausible magnitude).
- [ ] Use the Fill candidates button, select confirmed units, then Save direct FF sources.
- [ ] Check selected source, FF1, FF2, FF Total and the 5-second telemetry CSV.
- [ ] If raw values are zero or missing, export diagnostics JSON. Do not infer FF from corrected FF or N1.

## v0.7.8 multi-monitor screenshot verification
- [ ] Start MSFS on a secondary monitor, Reporter browser on the primary monitor.
- [ ] Confirm FMS & Evidence displays the detected MSFS monitor and its correct resolution.
- [ ] Click Capture screenshot + GPS while the browser has focus; confirm it captures the MSFS display, not the browser display.
- [ ] Press Ctrl+Shift+F10 from a different application; confirm that it still targets the MSFS monitor.
- [ ] Move MSFS to another monitor and repeat; detection must follow the window.
- [ ] Minimize MSFS: automatic capture must report an error instead of saving an unrelated display.
- [ ] Verify explicit individual-monitor fallback works with negative desktop coordinates.
- [ ] Confirm screenshot GPS/fuel data and group remarks remain unchanged, and the display source appears in the ZIP screenshot_contexts.json.
- [ ] Inspect the captured image for any obscuring windows or black/fullscreen artifacts before sharing the PDF.


### v0.7.9 checks
- [ ] With engines running, verify Engine 1/2 FF in **kg/h** against the ECAM. The default sources are `L:INI_FUEL_FLOW1/2`, source unit **kg/s**; `FF Total = FF1 + FF2`.
- [ ] Toggle each Engine Anti-Ice switch independently and check **Flight & OFP** and **Telemetry** show the same ON/OFF state. The CSV uses 1/0 for new samples and remains compatible with older 1.0/0.0 values.
- [ ] If upgrading an existing `data` folder, open Engine FF source settings and confirm both previously saved units are **kg/s**. Old rows are preserved, never rescaled.

### v0.7.10 checks
- [ ] The interface header and `http://127.0.0.1:8087/api/version` both report **0.7.10**.
- [ ] No Real-World Benchmark menu, page or separate benchmark PDF remains.
- [ ] SimBrief/OFP comparisons, route markers, screenshot groups, 5-second telemetry, FF, N1 and anti-ice remain operational.
- [ ] The existing flight case and its evidence remain after copying the `data` folder while the application is closed.
- [ ] If a previously built EXE is used, rebuild it and fully close any old Reporter process first.
