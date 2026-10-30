# RF-08 – Konfiguration und Exchange-Ermittlung isolieren

Basis: bestätigtes Result 064, Commit `d4210e7a2ae85fc85b50aedddecd1ce24bb414d1`.
Bundle 065 bereitet einen Commit vor. Sein tatsächlicher Apply, das vollständige
parallele Commit-Gate und der Push sind noch nicht bestätigt.

## Zuständigkeiten

| Modul | Aufgabe |
| --- | --- |
| `application_configuration.py` | Registrierung, lokale Konfiguration, Repository-Kontext und gemeinsamer geschützter Schreibablauf für Exchange, Suffix und Archivnamen |
| `application_exchange.py` | Konfigurierte physische Ziele und Kontrollpfade, Readiness, manueller/automatischer Scope, Discovery, Kandidatenauswahl und Revalidierung, Exchange-Wartung und Attempt-Receipts |
| `application.py` | Fassade für `api.py`; bestehende Apply-/Result- und Script-Orchestrierung bis RF-09 |

Die Abhängigkeitsrichtung lautet API → Application-Fassade → Exchange-/
Konfigurationsabläufe → bestehende Domain-/Plattformdienste. Der Exchange-Ablauf
nutzt dieselbe Pfadpolicy wie die Konfiguration. Es gibt keinen Rückimport in
die Fassade, keine neuen Laufzeitabhängigkeiten und keine zweite Discovery im
Watcher. `api.py`, CLI und Watcher bleiben bytegleich. Die zwei Module sind
normale Core-Quellen und werden auch in Wheel und PYZ transportiert.

Die 50 bisherigen Funktionen/Klassen werden genau einmal weitergeführt.
Ihre Körper bleiben strukturell identisch. Die bestehende gemeinsame
Konfigurationsänderung hält weiterhin erst die Registry-, dann die Repository-
Sperre bis nach Revalidierung und Veröffentlichung. Die Trennung fügt keine
neuen Locks oder Caches ein und verkürzt keine Sperrlebensdauer.

Discovery liest die Konfiguration unter der Registry-Sperre, scannt einen
geteilten physischen Exchange einmal und prüft Registry, Konfiguration und
Verzeichnisidentität nach Auswahl/Materialisierung erneut. Die Mutation erfasst
ihren Attempt erst nach ihrer bestehenden erneuten Identitätsprüfung. Manual
Retry, automatisches Replay-Verhalten, Scope und die Sortierung nach mtime_ns,
normalisiertem Dateinamen und Pfad bleiben unverändert.

## Prüfumfang und bestehende Verhaltensnachweise

| Vertrag | Ausgewählte Nachweise |
| --- | --- |
| Lokale Einstellungen, Unterverzeichnisse, Registrierung und Fehler ohne Reparatur | Konfigurations-, Context-, Registry- und Registrierungsverhaltenstests; Repository-Konfiguration E2E/Acceptance |
| Registry-/Repository-Sperren bis zur Veröffentlichung; konkurrierende Änderung abweisen | vorhandene Konfigurations-/Suffix-Tests und Watch-Readiness-/Apply-Tests |
| Gemeinsame Exchange-Pfade einmal scannen, falsche Bindung ablehnen, genau einen Kandidaten deterministisch auswählen | Exchange-Discovery und Repository-/Watch-Targets E2E |
| Advisory Watch-Control-Pfade ohne Scan/Hashing; veraltete Targets und ersetzte Verzeichnisse abweisen | Watch-Targets E2E, Watcher-API und Event-Loop-E2E |
| Attempt-/Result-Receipts, Abbruch und Recovery; kein Retry durch Dry-Run | Exchange-State, Archive-/Recovery-E2E, Apply-Tests |
| Fehlerkategorien, stabile API/CLI und statische Inspektion ohne Mutationen | API-Vertrag, API-, Konfigurations-CLI-, Patch-/Reference-Inspection-Tests |
| Modulgrenzen ohne Zyklus, Python-3.10-Syntax und keine neue externe Abhängigkeit | vorhandene Architektur-/Boundary- und Python-Kompatibilitätstests |
| Vollständige Quelle in Wheel/PYZ; alte 1.4.0-Artefakte unverändert lesbar | reale Packaging-/PYZ-Roundtrips, Kompatibilitäts- und Handofftests |

Bestehende Fehlersimulationen werden am neuen Lookup-Ort installiert; Assertions,
Testnamen und Parameter bleiben erhalten. Insbesondere bleiben echte Prozess-
abbrüche nach Result-Publikation und fehlgeschlagene Replay-Persistierung wirksam.
Die enge erwartete Paketdateiliste erhält nur die zwei neuen Core-Module.
Es werden keine Tests für Prosa, Darstellung oder exaktes Quelltextlayout ergänzt.

Development führt ausschließlich diese Auswahl plus private Tests des konkreten
Entrypoints parallel aus. Ergebnisbericht, Collection, Exitcode und Quellbindung
liegen im Exchange; dies ist kein Vollsuite-Nachweis. Die vollständige parallele
Suite läuft im Apply vor dem einzigen Commit, gefolgt von einem normalen Push.
CI startet ausschließlich Christian. Lokale Skips ersetzen keine nativen
Windows- oder anderen Interpreter-Nachweise.

- `tests/test_configuration.py`
- `tests/test_configuration_e2e.py`
- `tests/test_repository_configuration_e2e.py`
- `tests/test_repository_configuration_acceptance.py`
- `tests/test_bundle_suffix.py`
- `tests/test_bundle_suffix_e2e.py`
- `tests/test_registration.py`
- `tests/test_context.py`
- `tests/test_registry_e2e.py`
- `tests/test_api.py`
- `tests/test_api_contract.py`
- `tests/test_watch_targets_e2e.py`
- `tests/test_watcher_api.py`
- `tests/test_watcher_event_loop_e2e.py`
- `tests/test_exchange.py`
- `tests/test_exchange_state.py`
- `tests/test_exchange_e2e.py`
- `tests/test_exchange_archive_e2e.py`
- `tests/test_exchange_recovery_e2e.py`
- `tests/test_apply_repository.py`
- `tests/test_apply_repository_e2e.py`
- `tests/test_apply_mutation.py`
- `tests/test_patch_inspection.py`
- `tests/test_reference_validation.py`
- `tests/test_packaging_e2e.py`
- `tests/test_runtime_pyz.py`
- `tests/test_pyz_result_e2e.py`
- `tests/test_compatibility_140.py`
- `tests/test_architecture.py`
- `tests/test_architecture_boundaries.py`
- `tests/test_python_compat.py`
- `tests/test_bundle_handoff.py`
- `tests/test_result_bundle_e2e.py`
