A350 Fuel Evidence Reporter 0.7.11-rc2
Public publisher: Brazzor
WINDOWS RELEASE CANDIDATE — SEE TECHNICAL VALIDATION CHECKLIST

1. Extract the complete ZIP into a new folder.
2. Run A350FuelReporter.exe. Keep the _internal folder beside it.
3. Your browser opens http://127.0.0.1:8087. Close this version with Ctrl+C
   in its console. Close old Reporter instances before launching another version.
4. Python is bundled. No Python installation is needed for this build.
5. Requires Windows 10/11 x64; live simulator functions require MSFS and the iniBuilds A350.

Data: %LOCALAPPDATA%\A350FuelReporter
Updating the application folder does not delete this data.
Advanced/testing override: A350_REPORTER_DATA_DIR (absolute directory).

MIGRATING v0.7.10
Close both versions. Back up the complete old data folder first. Copy its CONTENTS
to %LOCALAPPDATA%\A350FuelReporter before starting this candidate for the first time.
The old folder may be beside app.py or beside the old EXE in dist\A350FuelReporter.
Choose the one containing your actual case. If the target already holds a flight,
back it up and resolve which case to keep; do not merge or overwrite blindly.
No automatic import, deletion or upload of old recordings is performed.

Exports are local files. Review screenshots, remarks, OFP and OIS attachments
before sharing. SimBrief access is optional and requires an explicit import.
There is no mandatory anonymization or upload.

Own application source: APPLICATION_SOURCE.zip (also linked in the browser UI).
Full source asset: CORRESPONDING_SOURCE.zip, provided as a separate release download.
Source access/build instructions: SOURCE_ACCESS.md and docs\SOURCE_BUILD.md.
Unsigned build. No clean Windows VM or full simulator flight is certified by this
package. See docs\RELEASE_CHECKLIST.md and docs\VALIDATION.md for actual checks.
