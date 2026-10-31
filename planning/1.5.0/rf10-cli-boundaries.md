# RF-10 – CLI-Parser und wiederholte Befehlsrahmen bereinigen

Basis: bestätigtes Result 066, Commit `5fa1ad3cbf1ac2ae1b0d0eb1d5812c10ca3d53de`.
Bundle 067 bereitet einen Commit vor. Sein tatsächlicher Apply, vollständiges
paralleles Commit-Gate und Push sind noch nicht bestätigt.

## Modulgrenzen und Vereinfachung

| Modul | Zuständigkeit |
| --- | --- |
| `cli.py` | Unveränderter öffentlicher Entrypoint `main`, UTF-8-Standardstreams, Argumentanalyse und explizite Befehlsauswahl |
| `cli_parser.py` | Exakte Argumenttypen, Abkürzungsverbot und fünf Gruppen: Konfiguration, Repository/Registry, Paketprüfung/Pack, Bundle/Apply und Dateisystem-Runner |
| `cli_commands.py` | Vorhandene Aufrufe der öffentlichen API, eigene Pack-/Apply-/Runner-Fehlergrenzen und gemeinsamer Konfigurationsbefehl |
| `cli_output.py` | Observer-Lebensdauer, Stream-Zuordnung, bestehende JSON-Hüllen und Abschlussdarstellung sowie gemeinsame Query-/Bundle-Fehlerausgabe |

Die Parsergruppen führen dieselben Anweisungen in derselben Reihenfolge aus.
Optionstypen, Defaults, gegenseitige Ausschlüsse, Abkürzungsverbot und die
interne Automatic-/Pfadgrenze bleiben erhalten. `main` bleibt eine explizite
Auswahl ohne Dispatch-Registry oder neues Command-Framework. Seine fünf
gemeinsamen Ausgabeparameter werden einmal aus dem normalisierten Namespace
gebildet; befehlsspezifische Argumente bleiben sichtbar am jeweiligen Aufruf.

Vier Konfigurationsfunktionen werden zu einer gemeinsamen Grenze für den
ausgewählten API-Aufruf, seinen Observer, Domain-Fehler und das Ergebnis.
`show` bekommt keine zusätzlichen Argumente; Setzen, `--clear` und explizite
leere Werte behalten ihre bisherigen Argumente. Pfade werden nicht durch eine
Shell interpretiert. Die API wird je Befehl genau einmal aufgerufen.

Inspection/Validation, Registry, Context und Bundle verwenden eine gemeinsame
Fehlerausgabe. JSON-Version 1 bleibt für Registry/Context/Bundle, Version 2 für
Inspection/Validation. Ein Fehler erhält dieselbe Kategorie und denselben
Exitcode; stdout enthält im JSON-Modus genau das strukturierte Ergebnis.
Bundle-Notfalldiagnostik bleibt ein zusätzlicher eigener Schritt auf stderr.

Pack behält seine besondere Grenze für bereits veröffentlichte Dateien und
anschließende Schreib-/Flush-/Abbruchfehler. Apply bleibt an den unveränderten
RunReport gebunden; Script-Runner, Rohlogs, Interrupt-/Timeout-Status und
Observer-Aufräumen werden nicht in die Query-Ausgabe eingegliedert.

Die öffentliche API, Application-/Domain-Code, Watcher, Formatmodelle,
Bootstrap-Programmquelle, Originalartefakte und drei Normdateien bleiben
bytegleich. Wheel und Core-PYZ enthalten die drei neuen CLI-Module; kein
Watcher wird in die Core-PYZ aufgenommen. Keine neue Laufzeitabhängigkeit.

## Nachweiszuordnung

| Vertrag | Verhaltenstests |
| --- | --- |
| Exakte Konfigurationsargumente einschließlich leerer Werte, keine Shell-/CWD-Änderung, einmaliger API-Aufruf und Observer | 16 Varianten in `test_cli_boundaries.py` |
| Fehlerstatus und kein falsches Konfigurationsergebnis | acht Varianten derselben Datei |
| Getrennte JSON-Versionen, Fehlerkategorien, stdout/stderr, genau ein Dokument | zehn Varianten derselben Datei |
| Keine still akzeptierten Optionen/Abkürzungen, ungültige Kombinationen, nichtendliche Timeouts | vorhandene CLI-/API- und Pack-CLI-Verhaltenstests |
| Reale Registrierung, lokale Konfiguration und Context/Bundle/Apply-Resultate | bestehende Repository-/Konfigurations-/Apply-/Bundle-CLI-E2E |
| Reference-Bindung und sichere Paketprüfung/-Erzeugung, Ausgabefehler nach Veröffentlichung | vorhandene Inspection-/Reference-/Pack-CLI-/Pack-Beispieltests |
| Redirected UTF-8, rohe Kindprozesslogs, Abbruch/Timeout und Verzeichnis-/ZIP-/stdin-Eingaben | CLI-/Run-Log-/Input-/Apply-Verhaltenstests |
| Installierte Entrypoints und eigene PYZ außerhalb des Checkouts | echte Packaging-/Runtime-/PYZ-Roundtrips und Pack-Beispiele |
| Azyklische CLI-Helfer ausschließlich über die öffentliche API, CPython-3.10-Syntax und Versionsgrenzen | Architektur-/Boundary-/Python-Kompatibilitäts- und Variantentests |

Bestehende Testnamen, Parameter und fachliche Assertions bleiben erhalten.
Nur die Fehlereinspeisung für die Apply-Abschlussausgabe folgt dem neuen
Lookup-Ort. Die enge Paketdateiliste erhält die drei neuen Core-Module.
Die neuen Tests prüfen keine Farben, Spinner, Tabellen, Hilfetexte oder Prosa.

Development führt ausschließlich die folgende Auswahl plus private Tests des
konkreten Entrypoints parallel aus. Ergebnisbericht, Collection, Exitcode und
Quellbindung liegen im Exchange. Dies ist kein vollständiges Development-Gate.
Apply führt die volle parallele Suite vor dem einzigen Commit aus, danach genau
einen normalen Push. CI wird ausschließlich von Christian gestartet. Lokale
Skips ersetzen keine nativen Windows-/Interpreter-Nachweise.

- `tests/test_cli.py`
- `tests/test_cli_api.py`
- `tests/test_cli_boundaries.py`
- `tests/test_cli_e2e.py`
- `tests/test_configuration_e2e.py`
- `tests/test_bundle_suffix_e2e.py`
- `tests/test_registry_e2e.py`
- `tests/test_context_e2e.py`
- `tests/test_repository_configuration_e2e.py`
- `tests/test_patch_inspection.py`
- `tests/test_patch_inspection_errors.py`
- `tests/test_reference_validation.py`
- `tests/test_reference_validation_errors.py`
- `tests/test_pack_cli.py`
- `tests/test_pack_examples.py`
- `tests/test_api.py`
- `tests/test_api_e2e.py`
- `tests/test_pyz_result_e2e.py`
- `tests/test_packaging_e2e.py`
- `tests/test_runtime_packaging.py`
- `tests/test_python_variants.py`
- `tests/test_python_compat.py`
- `tests/test_architecture.py`
- `tests/test_architecture_boundaries.py`
- `tests/test_chat_contract.py`
- `tests/test_bundle_handoff.py`
- `tests/test_apply_repository.py`
- `tests/test_apply_repository_e2e.py`
- `tests/test_result_bundle_e2e.py`
- `tests/test_run_log.py`
- `tests/test_input.py`
- `tests/test_zip_input.py`
- `tests/test_directory_input.py`
