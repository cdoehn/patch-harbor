# RF-09 – Apply-Ablauf und Result-Abschluss trennen

Basis: bestätigtes Result 065, Commit `2e6d1622ab3f67f1bfd071ee189720fc77f7346b`.
Bundle 066 bereitet einen Commit vor; sein tatsächlicher Apply, das vollständige
parallele Commit-Gate und der Push sind noch nicht bestätigt.

## Zuständigkeiten und gemeinsame Abschlusslogik

| Modul | Zuständigkeit |
| --- | --- |
| `application_apply.py` | Paketauflösung, sicherer Repository-Preflight, Ressourcensicherung, Mutation, Entrypoint und manueller/automatischer Apply-Einstieg |
| `application_results.py` | Result-Erstellung und Abschluss aus dem Mutation-Gate, Execution-Ergebnis, Attempt-/Commit-Nachweise und manuelle Bundle-Anforderung |
| `application.py` | Stabile Fassade für `api.py`, statische Inspektion und vorhandene Script-Eingaben |

Apply ruft Result-Abschluss und die bestehenden Exchange-Abläufe auf. Der
Result-Abschluss greift auf die vorhandenen Domain-Dienste und bei manuellen
Bundles auf Exchange-Wartung zurück. Es gibt keinen Rückimport in die Fassade,
kein neues Workflow-Framework, keine neue Fehlerhierarchie und keine zweite
RunReport-/Statusimplementierung.

20 der 21 bisherigen Funktionen bleiben inhaltlich unverändert. Im Preflight
teilen nur State-Mismatch und Paket-/Payload-Vorbereitungsfehler eine lokale
Funktion für ihren gleichen Result-Abschluss. Sie läuft weiterhin innerhalb
derselben Repository-Sperre und bei Vorbereitungsfehlern vor dem Aufräumen der
privaten Eingaben. Der Producer wird unverändert vor Observern, Payload-Writes
und Entrypoint festgehalten. Bestehende explizite Ausnahmeursachen bleiben
erhalten; es werden weder weitere Fehler abgefangen noch Fehler neu klassifiziert.

## Bewusst erhaltene Unterschiede

- Ein nicht aufgelöstes Repository erzeugt weiterhin den bestehenden
  unaufgelösten RunReport; kein künstlicher Snapshot und kein Mutation-Gate.
- Vor-Mutationsfehler, Fehler bei der zweiten Zustandsprüfung, unsichere
  Payload-Ziele und teilweise geschriebene Dateien behalten ihre jeweiligen
  Result-Kontexte. Kein Rollback und kein behaupteter Entrypoint-Start.
- Ein Dry-Run veröffentlicht sein unverändertes Result ohne Mutation oder
  Entrypoint. Automatischer Scope, Sperr- und No-Candidate-Status bleiben gleich.
- Entrypoint-Fehler, Timeout und Abbruch behalten Exitcode, Rohlog und primäres
  Ergebnis auch dann, wenn die Result-Veröffentlichung zusätzlich fehlschlägt.
- Result und Digest werden weiterhin vor dem terminalen Attempt-Nachweis
  veröffentlicht. Bei einem Fehler danach wird das bereits veröffentlichte
  Result weder ersetzt noch ein zweites unter gleichem Namen erzeugt.
- Erfolgreiche Ausführung behauptet ohne belastbaren Git-/Snapshotnachweis
  keinen Commit. Diagnosepakete mit null Commits und echte Mehr-Commit-Abläufe
  einschließlich Teilfortschritt bleiben unterstützt.
- Die Domain-Implementierung der Result-Erzeugung/-Veröffentlichung, ihr
  CIFS-Retry-/Integritätsablauf, RunReport, CLI-Statusadapter und Fehler bleiben
  bytegleich. Ein Linux-Test ersetzt keinen neuen nativen CIFS-/Windows-Nachweis.

## Verhaltensnachweise

| Vertrag | Vorhandene ausgewählte Tests |
| --- | --- |
| Lock-Lebensdauer, State-Mismatch, Interpreter-/Payload-Preflight und private Eingaben | Apply-Repository, Apply-Mutation, Apply-Repository-E2E |
| Fehlerpriorität, Unterbrechung, Timeout, Resultfehler und Notfall-Rohlogs | RunReport-Matrix und reale Apply-Prozesse |
| Pinning vor Änderungen an Installation/Quellen | Result-Runtime-Writer und PYZ-Result-Resources |
| Bereits publiziertes Result, Digest und Wiederanlauf ohne falschen Erfolg | echte Crash-/Recovery-E2E, Exchange-State, Watch-Targets und Event-Loop-E2E |
| Null, ein oder mehrere Commits und fehlgeschlagenes Zwischen-Gate ohne Push | echte Handoff-Commit-Sequenzen und unveränderte 1.4.0-Originalartefakte |
| Publikationsfehler, typisierte CIFS-Wiederholung und bytegenaue Verifikation | Result-Bundle-Publication, Result-Runtime-Publication und Result-3-Publication-Policy |
| Stabile öffentliche API/CLI, Result-Dokumente und Script-Runner | API-Vertrag/E2E, Resultformat 3, Eingabe-/ZIP-/Verzeichnisverhalten |
| Statische Inspektion ohne Apply und fehlende native Bindung weiterhin ablehnen | Patch-/Reference-Inspection |
| Azyklische Module, Python-3.10-Syntax, Core-PYZ ohne Watcher und vollständige Paketierung | Architektur, Python-Kompatibilität, echte Packaging-/PYZ-Roundtrips |

Testnamen, Parameter und fachliche Assertions bleiben erhalten; nur die
Fehlereinspeisung folgt dem tatsächlich verwendeten globalen Namen im neuen
Modul. Die erwartete Paketdateiliste erhält ausschließlich die zwei neuen
Core-Module. Die öffentliche API, CLI, Watcher und drei Normdateien bleiben
unverändert. Es entfallen keine Tests; neue Prosa-/Layouttests gibt es nicht.

Development prüft ausschließlich die folgende Auswahl plus die privaten Tests
des konkreten Entrypoints parallel. Collection, Outcomes, Exitcode und
Quelldateibindung stehen im Exchange-Bericht; dies ist kein Vollsuite-Nachweis.
Apply führt die vollständige parallele Suite vor dem einzigen Commit aus und
pusht erst danach einmal normal. Keine seriellen Gates; CI nur durch Christian.
Skips werden nicht als bestandene native Nachweise dargestellt.

- `tests/test_apply_repository.py`
- `tests/test_apply_repository_e2e.py`
- `tests/test_apply_mutation.py`
- `tests/test_run_report.py`
- `tests/test_result_runtime_writer.py`
- `tests/test_pyz_result_resources.py`
- `tests/test_result_bundle_e2e.py`
- `tests/test_result_runtime_publication.py`
- `tests/test_result3_publication_policy.py`
- `tests/test_result_bundle_publication.py`
- `tests/test_exchange_recovery_e2e.py`
- `tests/test_exchange_state.py`
- `tests/test_watch_targets_e2e.py`
- `tests/test_watcher_event_loop_e2e.py`
- `tests/test_api.py`
- `tests/test_api_contract.py`
- `tests/test_api_e2e.py`
- `tests/test_patch_inspection.py`
- `tests/test_handoff_commit_sequence.py`
- `tests/test_compatibility_140.py`
- `tests/test_pyz_result_e2e.py`
- `tests/test_packaging_e2e.py`
- `tests/test_architecture.py`
- `tests/test_architecture_boundaries.py`
- `tests/test_python_compat.py`
- `tests/test_reference_validation.py`
- `tests/test_result_format3.py`
- `tests/test_input.py`
- `tests/test_zip_input.py`
- `tests/test_directory_input.py`
