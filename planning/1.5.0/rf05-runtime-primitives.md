# RF-05: Gemeinsame Runtime-Daten und gezielte Development-Prüfung

Basis: bestätigtes Bundle 060, Commit `afce2628e9c1d85baa7726ec29a308de3d4d5ad2`.
RF-05 entfernt noch keine unterstützten Leser oder Profile. Öffentliche API,
Paket-/Resultfelder, Fehlerkategorien und Version 1.4.0 bleiben erhalten.

| Bisheriger Eigentümer | Neue Zuständigkeit | Erhaltener Vertrag |
| --- | --- | --- |
| `runtime_wheel.py` | `runtime_profile.py` | Rezept-Einträge, RuntimeDataError/RuntimeLimitError, kanonische JSON-/SHA-256-Regeln, Muster und gemeinsame Ressourcenpfade |
| `result_runtime.py` | `result_runtime_metadata.py` | Metadatenpfad/-limit, erlaubte unavailable-Gründe, RuntimeFile und geschlossene Deskriptorprüfung |
| `runtime_wheel.py` | `wheel_record.py` | Deterministische Wheel-RECORD-Bytes; keine eigene Ressourcen-/Profilpolitik |
| Getrennte Build-Loader | privater, an den Backend-Quellbaum gebundener Loader | Kein Import fremder Installation/CWD-Pakete oder des Paketinitialisierers; Namensraum wird auch bei Fehlern entfernt |

Die verschobenen Daten-/Validierungsfunktionen behalten ihre bisherigen
Funktionskörper und Fehler. Profilabhängige Pfade, Limits, Required-Inventare,
Capabilities, Identitätsalgorithmen und Materialisierung verbleiben in den
jeweiligen Profilmodulen. Zwei Prüfungen an unterschiedlichen zeitlichen
Sicherheitsgrenzen werden nicht zusammengezogen. Alte interne Importnamen
bleiben in den Legacy-Modulen als dieselben importierten Definitionen erreichbar.
PYZ und aktuelle Result-Ressourcen importieren dafür diese Legacy-Module nicht mehr.

Die aktuelle Wheel-Installation enthält weiterhin Watcher und Core; die Core-PYZ
enthält weiterhin keinen Watcher. Der Build benötigt den alten Runtime-Wheel-
Reader nicht mehr zur RECORD-Erzeugung. Der eigenständige Legacy-Reader nutzt
RECORD bis zu seiner geplanten Entfernung in RF-06 weiterhin. Keine neuen
Runtime-Abhängigkeiten und kein neuer Paket-/Rezept-/Resultformatstand.

## Verhalten und Sicherheitsnachweise

- Ein frischer isolierter Prozess sperrt beide Legacy-Reader beim Import der
  aktuellen PYZ-/Ressourcenpfade. Die statische Architekturprüfung deckt auch
  transitive Rückabhängigkeiten ab.
- Die bytegepinnten Originaldaten aus RF-02 bleiben unverändert. Ein zusätzlicher
  Fall liest und materialisiert die originale 1.4.0-PYZ bytegleich und vergleicht
  ihre gespeicherte Produzentenidentität. Prozess-/Netzaufrufe sind dabei gesperrt.
- Der aktuelle Builder wird mit ausschließlich seinen vier Datenhelfern geprüft,
  ohne Legacy-Reader und Paketinitialisierer. Fremde Installation/CWD-Pakete sind
  gesperrt. Fehlende einzelne Helfer führen zum Fehler; kein Ersatzimport.
  RECORD-Pfade, Größen und Hashes werden unabhängig an den erzeugten Bytes geprüft.
- Bestehende Profil-, Descriptor-, Ressourcenlimit-, Pfad-/Rechte-, Fehler-,
  Build-/Installations- und unabhängige PYZ-/API-/CLI-Durchstiche bleiben bestehen.
  Die explizite Packaging-Allowlist wird um genau drei neue Runtime-Dateien ergänzt.
- Acht neue Fälle, keine entfernten Testfälle und keine neuen Skip/Xfail-Regeln.

## Auswahl statt lokaler Vollsuite

Gemäß Nutzerentscheidung vom 29. Oktober läuft Development nur die folgende
änderungsbezogene Auswahl parallel. Sie deckt die verschobenen Definitionen,
alle direkten Profilverbraucher, Build/Installation, eingefrorene 1.4.0-Verträge,
Referenzvalidierung und die aktuellen Übergabe-Ressourcen ab. Kein Vollsuite-
Nachweis wird daraus abgeleitet. Der Controller-Bericht muss die komplette
Auswahl, alle Worker-Enden und die Bindung an diesen Quellstand bestätigen.
Die ausgewählten bisherigen Node-IDs werden gegen den vollständigen Bericht
von Bundle 060 abgeglichen; ausschließlich die acht aufgeführten neuen Fälle
kommen hinzu. Weitere Produktbereiche prüft der Watcher mit der vollständigen
parallelen Suite vor dem Apply-Commit. Native Windows/andere Interpreter und CI
werden hier nicht als ausgeführt behauptet; CI startet nur Christian.

- `tests/test_architecture.py`
- `tests/test_architecture_boundaries.py`
- `tests/test_runtime_profiles.py`
- `tests/test_runtime_pyz.py`
- `tests/test_runtime_artifact.py`
- `tests/test_runtime_robustness.py`
- `tests/test_runtime_packaging.py`
- `tests/test_pyz_resources.py`
- `tests/test_pyz_result_resources.py`
- `tests/test_result_format2.py`
- `tests/test_result_format3.py`
- `tests/test_result_format3_consumers.py`
- `tests/test_result_runtime_writer.py`
- `tests/test_result_runtime_roundtrip.py`
- `tests/test_pyz_result_e2e.py`
- `tests/test_packaging_e2e.py`
- `tests/test_pack_examples.py`
- `tests/test_compatibility_140.py`
- `tests/test_reference_validation.py`
- `tests/test_reference_validation_errors.py`
- `tests/test_runtime_permissions.py`
- `tests/test_python_compat.py`
- `tests/test_python_variants.py`
- `tests/test_producer_compatibility.py`
- `tests/test_bundle_handoff.py`
- `tests/test_chat_contract.py`
- `tests/test_release_audit.py`

Zusätzlich prüft Development die unveränderten 23 privaten Übergabefälle gegen
den tatsächlich erzeugten Entrypoint. Der Entrypoint führt im Apply weiterhin
`python tools/run_tests.py --suite all --report ...` aus und committet/pusht
nur nach geprüftem vollständigem parallelen Nachweis auf unveränderten Quellen.
