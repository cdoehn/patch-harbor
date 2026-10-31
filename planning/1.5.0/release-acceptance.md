# PatchHarbor 1.5.0 – RF-13: Versionsvorbereitung und Abschlussnachweise

Bundle 070 bereitet genau den Versionscommit
`chore(release): prepare PatchHarbor 1.5.0 acceptance [RF-13]` vor.
Die Basis ist das vollständig geprüfte tatsächliche Result von Bundle 069,
Commit `b555a3614f962a19b94244918486fc87021a829d`, sauber und auf `dev` gepusht.
RF-00 bis RF-12 sind damit bestätigt: 13 Planpositionen und 14 Plancommits.
Dieses Dokument ist ein Arbeitsnachweis des vorhandenen Plans, keine zusätzliche
normative Spezifikation und keine Behauptung des eigenen künftigen Apply-Erfolgs.

## Inhalt und erhaltene Verträge

- Einzige Produktcodeänderung ist `patchharbor.__version__ = "1.5.0"`.
  Setuptools, normale CLI, Watcher und Core-PYZ verwenden weiterhin diese
  zentrale Quelle. Der unabhängige Release-Prüfwert im Packaging-E2E wechselt
  ebenfalls auf 1.5.0; sämtliche Verhaltensfälle und Parameter bleiben erhalten.
- Aktuelle README-, Installations-, Result- und Chat-Hinweise sowie die
  Produktversionsangaben der drei getrennten Normdateien werden angeglichen.
  Historische Pläne, Refactoring-Messdaten, CI-Belege und ursprüngliche
  1.4.0-Artefakte bleiben unverändert und als solche erkennbar.
- Öffentliche API, CLI-Verhalten, numerische Fehler, Resultformat 3,
  Runtime-Metadatenformat 2, Patch-/Environment-/Handoff-Format 1,
  Fingerprintverfahren und die vier Bindungswerte ändern sich nicht.
  Die Chat-Dokumentversion 1.5.0 ist keine Änderung des Handoff-JSON-Schemas.
- Core-PYZ und öffentliche API behalten CPython >=3.10, das Profil ohne Watcher,
  geschlossene Rezeptvarianten, Ressourcenlimits und den sicheren Runtime-Fallback.
  Das normale Installations-Wheel enthält weiter CLI und Watcher; sdist bleibt.
- Ereignisgesteuerter Watcher, fünf Sekunden Quiet-Time, No-follow/Handle-/DACL-
  Schutz, CIFS-Budget und atomare Veröffentlichung bleiben unverändert.
  Der Quellenwechsel aktualisiert keine laufende globale Installation.

## Änderungsauswahl und Development-Nachweise

Die vorhandenen Verhaltenstests laufen parallel mit zwölf Workern; keine lokale
Vollsuite und kein serieller Lauf. Auswahl:

- `tests/test_packaging_e2e.py`: unabhängiger Versionswert, gebaute Metadaten,
  Wheel-/sdist-/PYZ-Inventare, pipx, CLI, API und installierter Watcher.
- `tests/test_runtime_packaging.py`: normale Offline-Installationswege,
  drei kanonische Generationen, Eigenressourcen und gleichversionige Ersetzung.
- `tests/test_runtime_pyz.py`, `tests/test_pyz_resources.py`,
  `tests/test_pyz_result_e2e.py`, `tests/test_pyz_measurements.py`:
  Rezept/Identitäten/Bytes, eigener Importursprung, Result/pack/Apply und
  repräsentative Größen-/Speichernachweise. Keine pauschale Leistungszusage.
- `tests/test_compatibility_140.py`, `tests/test_python_variants.py`,
  `tests/test_python_compat.py`: unveränderte Originalartefakte, geschlossene
  Varianten, Syntax-/Adapter-/Fehlerverträge. Lokales 3.14 ersetzt keine nativen
  3.10-/3.11- oder Windows-Läufe.
- `tests/test_pyz_bootstrap.py`, `tests/test_result3_embedded_bootstrap.py`,
  `tests/test_bootstrap_generation.py`, `tests/test_release_audit.py`:
  tatsächliche ausführbare Ressourcen, Herkunft, Built-in-Anleitung und Buildgrenzen.
- `tests/test_handoff_commit_sequence.py` und die 23 privaten Verhaltenstests
  des exakt ausgelieferten Entrypoints: Commit-Gates, Teilfortschritt,
  gebundene Ergebnisse und genau ein abschließender normaler Push.

Bericht, Log und Exitcode-Quittung liegen im projektspezifischen Exchange unter
`reports/patchharbor-refactoring-070-selected.json`, `.log` und `.completion.json`.
Die Paketprüfung bindet tatsächliche Quellbytes, Worker-Collection, Testphasen,
Exitstatus und vollständige Berichtshashes. Skips bleiben explizit; fehlende
native Bedingungen werden nicht in Erfolg umgedeutet. Keine Tests auf Prosa.

## Lokale Artefakte und Commitbindung

Der vorhandene `scripts/build_release.py` erzeugt unter dem ignorierten
Development-Arbeitsverzeichnis `build/refactoring-070-release-150/release-artifacts/`:

- `patchharbor-1.5.0-py3-none-any.whl`
- `patchharbor-1.5.0.tar.gz`
- `patchharbor-1.5.0.pyz`

Der zusätzliche lesende Artefaktreview prüft Versions-/Python-Metadaten,
Entrypoints, vollständig inventarisierte kanonische PYZ-Bytes, Herkunfts-ID,
Watcherausschluss, übereinstimmende Ressourcen und alle Dateihashes.
Er dokumentiert Größen, SHA-256, Content-ID, Python-/Buildumgebung und die
vollständige Development-Quellbindung unter
`reports/patchharbor-refactoring-070-release-build.json`, mit eigenem Log und
Exitcode-Quittung. Kandidaten werden nicht installiert oder als Release publiziert.

Der lokale Build entsteht **vor** dem tatsächlichen Apply-Commit. Er erhält
deshalb keine erfundene Endcommit-SHA; der Referenzcommit bezeichnet seine
Ausgangsbasis, die Quellbindung den vorbereiteten Endzustand. Das erfolgreiche
Result muss später exakt das vorbereitete Inventar und den tatsächlichen
Versionscommit bestätigen. Der manuelle CI-Build liefert zusätzlich seine
eigene genaue Commit-, Plattform-, Interpreter- und Artefaktbindung. Unterschiedliche
Distributionsarchive werden über ihre jeweiligen Hashes bezeichnet; identische
Versionsstrings allein sind kein Gleichheitsbeweis. Build-Hashes stehen außerhalb
der gebauten Ressourcen und erzeugen keine zirkuläre Selbstbindung.

## Offene Abschlussabnahme

| Nachweis | Stand beim Erstellen dieses Bundles |
| --- | --- |
| RF-00 bis RF-12: tatsächliche Applies, volle parallele Gates und Push | bestätigt; letzter Commit oben |
| RF-13-Apply, Versionscommit und einmaliger Push | offen; erst das tatsächliche Result bestätigt sie |
| RF-13-Development-Auswahl und lokale Kandidaten | vor Veröffentlichung vollständig prüfen; externe Berichte binden das tatsächliche Ergebnis |
| Manuelle native CI auf dem tatsächlichen finalen 1.5.0-Commit | offen; ausschließlich Christian startet sie |
| CIFS-Praxis für resultrelevante Umbauten oder passend zugeordneter vorhandener Nachweis | offen; nicht aus historischen Versionsfreigaben oder lokalen Fault-Injection-Tests abgeleitet |
| Vollständiger lesender Abschlussreview gemäß Commitplan §6 | offen bis alle verlangten Nachweise vorliegen |

Nach erfolgreichem Apply startet Christian den bestehenden manuellen Workflow
auf dem tatsächlichen gepushten `dev`-Commit. Die Eingabe `expected_commit`
kann dessen vollständige SHA binden; keine verkürzte oder vorab angenommene SHA.
Codex, Watcher und Entrypoint dispatchen oder wiederholen keine CI.
Der lesende Review prüft Run-ID/URL, exakten Commit, alle zwölf katalogisierten
Jobs einschließlich Windows/PowerShell, CPython 3.10/3.11 und bestehender
3.12/3.14-/Docker-Lanes, ihre Artefakte und jede vorgeschriebene Nachweisvariante.
Die Definition bleibt `tools/acceptance-catalog.json`; keine zweite manuelle Matrix.

Nach bestätigtem RF-13-Apply sind die vorgesehenen Implementierungscommits
abgearbeitet. Fehlende externe Abschlussnachweise erzeugen keinen spekulativen
Folgepatch und keinen neuen Plan. Der bestehende Plan bleibt bis zu seiner
nachgewiesenen Abnahme offen. Ein späterer lesender Bericht kann ihn ohne
zusätzlichen Commit schließen. Erforderliche Korrekturen brauchen wiederum
passende neue Results und Nachweise auf dem korrigierten Endstand.

Tag, GitHub Release, Paketindex-Upload, Hostinstallation und Dienstneustart
bleiben getrennte Nutzeraufträge. Dieses Bundle führt keine dieser Aktionen aus.
