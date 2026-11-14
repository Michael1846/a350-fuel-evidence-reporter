# Release-Checkliste — 0.7.11-rc2

Technische Releaseabnahme: nachstehende Prüfungen separat abschließen. Keine Flugdaten hochladen.
Ein Häkchen setzt einen konkreten Nachweis voraus.

## Vorbereitung

- [x] Englische bebilderte Benutzeranleitung (16 Seiten) und separate iniBuilds-
      Datenreferenz (13 Seiten) erstellt und alle Seiten visuell geprüft;
      siehe `docs/ENGLISH_GUIDES.md`.
- [ ] Vor finalem Release die falsche Einheit im Feldnamen `true_track_deg`
      versioniert korrigieren und Dokumentation/CSV-Migration abstimmen. rc2 liefert
      hier Radiant; beide PDFs dokumentieren die nötige Umrechnung.

- [x] v0.7.10 als Basis identifiziert; Originalinstallation unverändert.
- [x] Arbeitskopie ohne Flugdaten, Konfiguration, Token oder alte EXE erstellt.
- [x] AGPL-Lizenztext und installierte Drittanbieter-Lizenzdateien gesammelt.
- [x] Datenpfad von Programmordner getrennt; Übernahme alter Daten dokumentiert.
- [x] Lokale Host-/Origin-/Content-Type-Prüfungen und exklusiver Windows-Port ergänzt.
- [x] Sichtbare Lizenz-, Hinweise- und Quellcode-Links ergänzt.
- [x] Feste Abhängigkeitsversionen und Build-/Paket-Skripte vorbereitet.
- [x] Alle 80 automatischen Tests erfolgreich; Ergebnis in `docs/VALIDATION.md`.
- [x] Windows-EXE neu gebaut und ausschließlich synthetisch geprüft.
- [x] Anwendungscode- und Windows-ZIP mit SHA-256-Manifesten erzeugt; Abschlussprüfung
      des finalen Pakets siehe `docs/VALIDATION.md` und lokalen Prüfbericht.
- [x] Zwölf passende Python-Quellarchive gegen PyPI-SHA-256 geprüft; zusätzliche
      CPython-/MuPDF-Quellen und 34 native Lizenztexte gesammelt.
- [x] Quellenpaket auf 33 Archive einschließlich nativer Codecs und vollständiger
      Build-Rezepte erweitert; zusätzliche 150 Quell-Lizenzhinweise erfasst.
- [x] Jede ausgelieferte DLL/PYD einem offiziellen Paket oder stabilen Microsoft-
      Redist zugeordnet; unklare Programmsuchpfad-Laufzeitkopien entfernt.
- [x] Paket für eigenen Code und gesammelte abhängige Quellen samt Build-Anleitung,
      Herkunftsübersicht und Dateiprüfsummen zusammengestellt.

## Vor öffentlicher Veröffentlichung erforderlich

- [ ] Beim GitHub-Release den passenden vollständigen Quellen-Download neben dem
      Binärdownload veröffentlichen und Erreichbarkeit/Versionszuordnung testen.
- [x] Native Unterkomponenten/Fonts/Laufzeiten mit ihren vorhandenen Lizenztexten
      und Quellnachweisen erfasst.
- [x] Öffentlicher Herausgebername: Brazzor (vom Nutzer bestätigt).
- [ ] Öffentliche Kontaktadresse und Codeherkunft bestätigt.
- [x] Privates GitHub-Zielrepository unter Michael1846 erstellt:
      `Michael1846/a350-fuel-evidence-reporter`; Herausgeber bleibt Brazzor.
- [ ] Vorbereitete Projektdateien importiert und Repository-Inhalt/Historie auf
      persönliche Flugdateien geprüft; Zugriff der GitHub-Verbindung noch ausstehend.
- [ ] Tag und Commit stimmen mit Quellarchiv und Build überein.
- [ ] Neuer Standardnutzer-PC/saubere Windows-VM ohne Python: Start, UI, PDF, ZIP,
      CSV, lokale Quellen-/Lizenzanzeige und Beenden erfolgreich getestet.
- [ ] Windows-Sicherheitsprüfung durchgeführt und Ergebnis dokumentiert.
- [ ] Unterstützte Python-/Abhängigkeitsversionen und bekannte Sicherheitslücken
      geprüft; 3.11.9 ist die reproduzierte Ausgangsumgebung, keine Aktualitätsfreigabe.
- [ ] Cold & Dark → Engine Start → kompletter Flug → Shutdown geprüft.
- [ ] FF1/FF2, N1, Anti-Ice einzeln gegen Cockpit in mehreren Flugphasen geprüft.
- [ ] Automatischer Start/Stopp und Unterbrechung/Neustart ohne Datenverlust geprüft.
- [ ] Mehrmonitor-Screenshots/Hotkey/Minimierung geprüft; gespeicherte Metadaten korrekt.
- [ ] SimBrief-Vergleich, OFP, CSV, PDF und Evidence-ZIP anhand desselben Flugs geprüft.
- [ ] Upgrade durch Austausch des Programmordners mit vorhandenen Benutzerdaten geprüft.
- [ ] Englische Releasebeschreibung und bekannte Einschränkungen überprüft.
- [ ] GitHub-Release zuerst als Entwurf vorbereiten; veröffentlichen nach Freigabe.

Keine Funktion darf durch ein fehlendes OIS-Autosave oder unvollständige Evidence
pauschal den lokalen Export verhindern. Es gibt keinen obligatorischen Upload,
keine erzwungene Anonymisierung und keine neu eingeführten getrennten Exportmodi.
