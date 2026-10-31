# RF-11 – CI-Matrix und fachliche Nachweise zentral pflegen

Basis: bestätigtes Result 067, Commit `35af08c9c38482c1974102f5ac902e629fa11f01`.
Bundle 068 bereitet genau einen Commit vor; Apply, volles paralleles Commit-Gate
und Push dieses Schritts sind noch offen. Produktversion bleibt 1.4.0 bis RF-13.

## Vereinfachung und erhaltene Grenzen

- Ein gemeinsamer JSON-Katalog ersetzt doppelte Matrixdaten im Workflow und
  Auswerter, die unabhängige Windows-Selektion und aktuelle Namenslisten für
  Pflichtnachweise. `tools/acceptance_catalog.py` stellt die kleinen gemeinsamen
  Projektionen bereit; `tools/acceptance_evidence.py` bewertet bestandene Varianten.
- Zwölf Jobs mit gleichen Anzeigenamen, Runnern, Python-Versionen, PowerShell-
  Varianten, Artefaktnamen und Suite-Umfängen. Drei deterministisch erzeugte
  Matrixblöcke; keine neue CI-Lane oder Laufzeitabhängigkeit.
- Python-/Shell-/Commit-/Source-Bindung, native Gates, Paketrollen und Hashes,
  Fehlerrückgaben, vollständige Worker-/Collection-/Phasenprüfung, ZIP-Budgets
  und GET-only-Auswertung bleiben verbindlich. Kein automatischer Dispatch/Retry.
- Stabile IDs werden am realen Test deklariert. Alle bisherigen Testnamen,
  Parameterwerte und fachlichen Testkörper bleiben erhalten. Darstellung und
  Testdateinamen sind keine aktuelle Abnahmeidentität mehr.
- Versionswechsel betreffen ausschließlich interne Nachweise: Test und Build
  Format 2, CI-Review Format 3. Historische Version 1 wird ausdrücklich getrennt
  gelesen, nicht in einen angeblich neuen Nachweis umgeschrieben.
- Kein Produktcode, Watcher, Runtime, Bootstrap, eingefrorenes Artefakt oder
  normative Spezifikation wird geändert. Aktuelle Implementierung bleibt getrennt
  von RF-12-Dokumentationsbereinigung und RF-13-Version/Abschlussabnahme.

## Änderung und Nachweis

| Vertrag | Prüfungen |
| --- | --- |
| Unveränderte zwölf Lanes und Suite-Umfänge | Katalog-/Workflow-/Runner-Verhaltenstests, explizite Plattform-/Python-/Shell-Mengen |
| Deterministischer Generator, Check ohne Schreiben, keine Änderung anderer Schritte | Drift-, Boundary- und Idempotenzfälle |
| Artefaktrollen und versionierte Build-/Testbindung | echter Capture-Aufruf mit kontrolliertem Builder; CI-Artefaktfehlerfälle |
| Vollständige parametrisierte Pflichtnachweise und Umbenennung | neuer CI-Nachweis mit allen Testpfaden/Funktionen umbenannt; fehlende, doppelte, übersprungene Varianten |
| Workertransport und Verlust/Widerspruch | echte kleine xdist-Läufe mit zwei/vier Workern, inklusive Fehlerläufen |
| Historische Belege, kein stiller Formatwechsel | unveränderte historische CI-Fixtures und neutrale Format-1-/Format-2-Prüfungen |
| Funktionierende reale markierte Tests und Produktpakete | vorhandene Installations-/PYZ-/Pack-/Handoff- und native Kompatibilitätstests |

Alte Workflow-Assertions prüfen jetzt die ausgewerteten Matrixwerte anstelle
von deren früherer Inline-Schreibweise. Testnamen/Collection bleiben erhalten;
neue Fälle kommen hinzu. Kein Test auf Farben, README-Prosa oder Markdown.

## Lokale Auswahl

Development führt nur die folgende Auswahl und die privaten Tests des konkreten
Entrypoints parallel mit zwölf Workern aus. Bericht, Prozess-Exitcode,
Quellbindung und Vergleich zur vorherigen Vollcollection werden im Exchange
dokumentiert. Das ist kein Vollsuite-Nachweis. Apply führt die vollständige
parallele Suite vor seinem einzigen Commit und abschließenden Push aus.
Native Windows-/weitere Interpreter-Nachweise bleiben Aufgabe der ausschließlich
von Christian gestarteten manuellen CI; lokale Skips werden nicht umgedeutet.

- `tests/test_acceptance_catalog.py`
- `tests/test_proof_evidence.py`
- `tests/test_handoff_ci.py`
- `tests/test_github_actions.py`
- `tests/test_test_evidence.py`
- `tests/test_test_runner.py`
- `tests/test_test_mode_verification.py`
- `tests/test_parallel_execution.py`
- `tests/test_docker_integration_runner.py`
- `tests/test_release_audit.py`
- `tests/test_architecture.py`
- `tests/test_architecture_boundaries.py`
- `tests/test_python_compat.py`
- `tests/test_pyz_result_e2e.py`
- `tests/test_runtime_packaging.py`
- `tests/test_packaging_e2e.py`
- `tests/test_python_variants.py`
- `tests/test_runtime_bootstrap.py`
- `tests/test_python_compat_windows.py`
- `tests/test_bootstrap_python_compat.py`
- `tests/test_handoff_commit_sequence.py`
- `tests/test_chat_contract.py`
- `tests/test_bundle_handoff.py`
