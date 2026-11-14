# English release documentation - 0.7.11-rc2

Two separately downloadable PDFs are provided in `output/pdf/` and copied to
`release/0.7.11-rc2/Documentation/`:

- `A350_Fuel_Evidence_Reporter_User_Guide_EN.pdf`: 16 pages covering installation,
  connection, sources, recording, screenshots, manual FMS observations, evidence
  groups, route checks, export, CSV locale handling, recovery and cockpit examples.
- `A350_Fuel_Evidence_Reporter_iniBuilds_Data_Reference_EN.pdf`: 13 pages covering
  ZIP contents, acquisition, all 37 telemetry columns, quality flags, time bases,
  waypoint matching, screenshot context, import examples and an example review.

UI screenshots show an isolated synthetic case. Cockpit examples and selected
reported values come from the owner's three screenshots and six-page example
report supplied for this documentation. These two example datasets are distinct.
No flight files were uploaded or sent to a third party.

The accompanying `A350FuelReporter-0.7.11-rc2-English-Documentation.zip` is a
separate release asset. The application executable is unchanged.
Technical acceptance checks remain separately documented.

An additional complete Windows package now includes both PDFs:
`A350FuelReporter-0.7.11-rc2-windows-x64-LOCAL-RC-WITH-GUIDES.zip`.
It preserves the executable and runtime files byte-for-byte and adds the two
guides, their documentation metadata/checksums and START-HERE.txt.
The executable hash is unchanged. Verification completed successfully; see
`release-manifest-with-guides.json` and `SHA256SUMS-WITH-GUIDES.txt` beside it.

## Unit issue identified during review

In the rc2 acquisition path, `true_track_deg` copies `GPS_GROUND_TRUE_TRACK`
requested in radians by Python-SimConnect 0.4.26. The degree suffix is misleading.
Both guides direct reviewers to retain the original and derive a separate degree
column with `(radians * 180 / pi) % 360`. Resolve the program/schema issue in a
versioned code change before a final public release, and update the guides with
that release. No application or CSV behavior was changed in this documentation task.

## Validation

All 29 pages were rendered and visually reviewed. Page counts, text bounds,
embedded images, PDF links and complete CSV field coverage were checked. Layout
review and document hashes are recorded in the documentation QA manifest.
