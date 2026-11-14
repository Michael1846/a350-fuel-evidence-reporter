# GitHub release preparation

Candidate title: **A350 Fuel Evidence Reporter 0.7.11-rc2 — local release validation**

Public publisher name: **Brazzor**, supplied by the owner on 2026-11-09.
Verified connected GitHub account: **Michael1846**. The owner selected this account
for a **private** repository on 14 November 2026. Brazzor remains the publisher.
Selected repository name: `a350-fuel-evidence-reporter`.

Private repository created on 14 November 2026:
https://github.com/Michael1846/a350-fuel-evidence-reporter

The source import is being completed through the authenticated GitHub browser.
Application code is already present; supporting folders and documentation follow.
No tag, uploaded binary or public release has been created.

2. Choose the public repository under the intended account and add a public contact.
3. Import only the application source tree. Exclude recordings, `data/`, virtual
   environments, builds, test output and binary archives. Review staged paths and
   the full initial history for tokens and personal data.
4. Commit the exact reviewed source, identify its commit SHA, tag the version,
   and build using the documented Windows x64 environment. Record that SHA in
   the release manifest (`--commit` argument to packaging script).
5. Create a prerelease **draft** with the Windows ZIP, own application-source ZIP,
   complete dependency-source material/access instructions, SHA256SUMS.txt and
   manifest. GitHub's automatic source archive alone does not include dependency
   sources and is not assumed sufficient.
6. Verify clean-machine and simulator acceptance, links and matched sources.
   Publish after the technical release checks are completed and the owner authorizes publication.

Additional documentation asset prepared on 14 November 2026:
`A350FuelReporter-0.7.11-rc2-English-Documentation.zip`, containing the 16-page
illustrated user guide and 13-page iniBuilds data reference. Publish the PDFs as
separate assets as well if preferred. See `docs/ENGLISH_GUIDES.md` for verification
and the rc2 true-track unit-label issue discovered during documentation review.

## English release-description draft

Published by **Brazzor**.

A free, independent Windows tool for recording and reporting fuel evidence from
the iniBuilds A350 in Microsoft Flight Simulator 2024. Includes SimConnect
telemetry, direct fuel-flow sources, N1, engine anti-ice, SimBrief comparison,
screenshots, CSV exports and PDF/evidence reports.

This candidate adds release documentation, a stable user-data directory, local
webserver request checks and application-source access. Flight exports
remain local. Users choose whether and with whom to share them. An optional
SimBrief import contacts SimBrief only when requested.

Extract the entire Windows ZIP and run A350FuelReporter.exe. Keep `_internal`
beside the executable. Python is bundled. Data is stored under
`%LOCALAPPDATA%\A350FuelReporter`. Existing v0.7.10 flights must be migrated using
the documented backup-and-copy procedure while both versions are closed.

This is an unsigned Windows release candidate. Clean-machine validation and
full simulator acceptance remain separate technical checks.

Independent community project. Not affiliated with or endorsed by iniBuilds,
Airbus, Microsoft or Navigraph. For simulation only.
