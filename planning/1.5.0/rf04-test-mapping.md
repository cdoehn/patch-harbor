# RF-04: Testzuordnung und erlaubte Architekturänderungen

Basis: bestätigtes Bundle 059, Commit `ab1d6d5dae0d6f013c91775e9308dfe86ef6d848`.
Produktcode, Tools, Skripte, CI, die drei Normdateien und eingefrorene 1.4.0-
Artefakte bleiben bytegleich. Tests auf Textdarstellung werden entfernt;
Verhaltensverträge werden erhalten. Kein Skip/Xfail wird ergänzt.

## Entfernte oder ersetzte Testkennungen

Jede folgende alte Kennung hatte genau einen Fall. Die bestehenden genannten
Verhaltenstests bleiben erhalten. Ihre Funktion wird nicht durch eine bloße
Dokumentationsprüfung ersetzt.

| Alte Kennung | Entscheidung / Verhaltensnachweis |
| --- | --- |
| `tests/test_chat_contract.py::test_chat_contract_is_canonical_versioned_and_compact` | Prosa, Überschriften, konkrete Vertragsversion und Whitespace-/gitattributes-Layout entfallen. UTF-8, echte kanonische Herkunft und Größenbudget: neuer `test_canonical_contract_can_be_loaded_and_rendered_without_execution`; Fehler-/Lineending-Fälle bleiben in `test_bundle_handoff.py`. |
| `tests/test_chat_contract.py::test_chat_manifest_and_resource_contract_match_runtime_constants` | Neuer `test_documented_patch_manifest_validates_against_a_real_reference` prüft das echte Beispiel über die öffentliche API. Ressourcenlimits und Marker-Ablehnungen bleiben in `test_resource_policy.py`, `test_patch_manifest.py` und `test_result_format3.py`; ihre Textdarstellung und JSON-Schlüsselreihenfolge sind keine Laufzeitverträge. |
| `tests/test_chat_contract.py::test_chat_public_commands_are_real_and_use_correct_optionality` | Neuer `test_public_commands_accept_documented_arguments_and_reject_missing_or_unknown_ones` prüft Parser-Verhalten einschließlich Suffix, optionaler Zielpfade und numerischem Fehlercode. Die wörtliche Textblock-Gleichheit entfällt. |
| `tests/test_chat_contract.py::test_chat_contract_distinguishes_manual_explicit_and_watcher_selection` | `test_api.py::test_manual_and_automatic_apply_share_core_but_keep_distinct_scopes` und reale Auswahlfälle in `test_exchange_e2e.py`; die gleiche Auswahlregel muss nicht in identischen Sätzen stehen. |
| `tests/test_chat_contract.py::test_chat_and_spec_share_commit_warning_stop_and_ui_contracts` | Reine redaktionelle Prüfung von Chat-Arbeitsanweisungen und Ausgabeprosa entfällt. Keine neue Laufzeit-Kommit-/Chatsteuerung wird eingeführt. |
| `tests/test_chat_contract.py::test_patch_delivery_contract_is_single_artifact_and_backup_safe` | Chat-Ausgabetext entfällt. Die tatsächlichen Sicherheitsverträge bleiben in `test_pack_candidate.py`, `test_pack_sources.py`, `test_pack_api.py` und `test_bundle_handoff_e2e.py::test_template_failure_publishes_no_incomplete_bundle` geprüft. |
| `tests/test_chat_contract.py::test_delivery_contract_has_no_superseded_single_footer_rule` | Reiner historischer UI-/Prosa-Check entfällt; keine Produktfunktion betroffen. |
| `tests/test_chat_contract.py::test_warning_and_stop_finish_without_creating_second_artifacts` | Wortlaut einer Chat-Anweisung entfällt; kein ausführbarer Produktpfad wurde mit diesem Test ausgeführt. Atomare Veröffentlichung bleibt durch Pack-/Result-Publikationstests abgedeckt. |
| `tests/test_chat_contract.py::test_bundle_number_is_shared_with_successful_entrypoint_only` | Chat-Bundle-Nummer und Überschriften sind Arbeitsanweisungen, keine neue vom Core auszuwertende Semantik; reiner Prosa-Check entfällt. |
| `tests/test_chat_contract.py::test_generic_chat_contract_delegates_test_policy_and_allows_commit_sequences` | Textformulierungen der Zuständigkeitsregeln entfallen als Test. Tatsächliche 0/1/mehrere Commits, Diagnose, Dry-Run und Teilfortschritte bleiben in `test_compatibility_140.py` und `test_pack_examples.py` erhalten. |
| `tests/test_chat_contract.py::test_canonical_template_path_and_renderer_remain_the_handoff_source` | Funktionsnamen im Quelltext entfallen. Tatsächliche Herkunft, frisches Lesen, installierte Ressourcen und Fremdverzeichnis-Ablehnung: `test_bundle_handoff.py::test_source_template_is_canonical_and_not_read_from_cwd`, `test_template_is_read_fresh_and_missing_or_bad_template_fails`, `test_installed_template_is_resolved_from_distribution_file_record`; echte Installation: `test_packaging_e2e.py`. |
| `tests/test_chat_contract.py::test_chat_contract_carries_retry_filename_and_identifier_presentation` | Retry-Verhalten bleibt in `test_exchange_e2e.py`; unbekanntes `--retry-failed` wird im neuen Parser-Test abgelehnt. Dateinamensvertrag bleibt in `test_bundle_suffix.py` und `test_bundle_suffix_e2e.py`. Verkürzte Anzeige und Erläuterungswortlaut sind keine maschinenlesbare Bindung. |
| `tests/test_chat_contract.py::test_result_bundle_and_responsibility_boundaries_match_spec_and_readme` | README-/Spec-Prosa entfällt. Tatsächliche Bundles, Repositorybindung und Ausführungsgrenzen: `test_bundle_handoff_e2e.py`, `test_pack_examples.py`, `test_compatibility_140.py` und bestehende Result-E2E-Fälle. |
| `tests/test_chat_contract.py::test_chat_contract_remains_documentation_not_runtime_orchestration` | Verbot bestimmter Zeichenketten in Produktquellen entfällt. Neuer passiver Render-Test sperrt Prozess/Netz; `test_architecture.py::test_bundle_handoff_is_passive_output_not_chat_or_commit_orchestration` und `test_api.py::test_public_import_has_no_cli_environment_or_stream_side_effects` bleiben. |
| `tests/test_chat_contract.py::test_archive_contract_has_no_blanket_prohibition_conflicting_with_maintenance` | Wortlaut entfällt. Tatsächliche Auswahl/Archivierung und Erhalt fremder/ungültiger/unbestätigter Bundles: `test_exchange_archive_e2e.py` und `test_repository_configuration_acceptance.py::test_shared_exchange_archives_only_the_owning_repositories_bundles`. |
| `tests/test_release_audit.py::test_runtime_module_inventory_matches_the_release_architecture` | Doppelte Liste entfernen; die unabhängige explizite Sicherheits-Allowlist in `test_packaging_e2e.py::test_runtime_file_allowlist_matches_source_tree` bleibt unverändert. Keine Ableitung der erwarteten Liste aus dem getesteten Artefakt. |
| `tests/test_release_audit.py::test_automatic_apply_discovery_stays_in_the_core_application_boundary` | Literal vorkommende Funktionsnamen entfallen. Tatsächliche manuelle/globale/explicit Auswahl: `test_exchange_e2e.py`; Schichtgrenzen: AST-Graph in `test_architecture.py`. |
| `tests/test_release_audit.py::test_result_bundle_defaults_use_local_configuration_not_legacy_paths` | `test_repository_configuration_acceptance.py::test_explicit_output_uses_valid_target_config_without_exchange`, `test_explicit_output_never_bypasses_damaged_local_config`, `test_config_writes_preserve_existing_replay_ledger` und frische Environment-Daten in `test_bundle_handoff_e2e.py` ersetzen Quelltextfragmente. |
| `tests/test_release_audit.py::test_release_documents_exist_at_their_canonical_paths` | Historische Plan-Dateinamenslisten entfallen. Aktuell deklarierte installierte Ressourcen werden weiter im verbleibenden Release-Test gelesen und im echten Build/Install-E2E geprüft. Alte Dokumente selbst bleiben unverändert. |
| `tests/test_release_audit.py::test_v111_commit_plan_has_one_consistent_consolidated_sequence` | Reiner Prosa-/Reihenfolgecheck eines abgeschlossenen historischen Plans entfällt; kein Laufzeitverhalten betroffen. |
| `tests/test_release_audit.py::test_exchange_apply_lifecycle_is_core_owned_and_published_around_execution` | Funktionsnamen und Nichtvorkommen von unlink/rmtree-Primitiven in bestimmten Dateien entfallen. Echte Crash-/Recovery-Grenzen: `test_exchange_recovery_e2e.py`; konservative Archivierung: `test_exchange_archive_e2e.py`; Retry/Result-Fehler: `test_exchange_e2e.py`; Core-Zuständigkeit bleibt im Importgraph. |
| `tests/test_release_audit.py::test_watcher_is_only_global_lifecycle_and_repository_aware_core_apply` | README/Quelltextfragmente und historische Dateinamen entfallen. `test_watcher_api.py::test_worker_calls_public_automatic_api_once_and_transports_report`, `test_watcher_worker_e2e.py::test_real_worker_does_not_import_cli_and_keeps_raw_script_output`, `test_repository_configuration_acceptance.py::test_real_worker_reloads_target_config_and_ignores_wrong_exchange` und AST-Grenzen bleiben. |
| `tests/test_release_audit.py::test_v121_release_retains_completed_v111_history` | Historischer Version-/Plan-/README-Text entfällt als Test; Produktversion und installierte Metadaten werden weiter tatsächlich in `test_packaging_e2e.py` geprüft. Keine historischen Nachweise umgeschrieben. |
| `tests/test_bundle_suffix.py::test_suffix_documentation_carries_full_chat_and_configuration_contract` | Reiner Chat-/README-/Spec-Wortlaut entfällt. Alle übrigen Suffix-Tests einschließlich ungültiger Werte, atomarem Konfigurationserhalt und Lock bleiben; `test_bundle_suffix_e2e.py` prüft reale Erzeugung/Auswahl. |
| `tests/test_architecture.py::test_application_is_the_only_core_workflow_orchestrator` | Ersetzt durch `test_application_layer_can_share_workflows_without_reverse_dependencies`: API darf Application und fachlich benannte application_*-Module nutzen; Rückabhängigkeiten und Präsentations-/Exitstatuskopplung bleiben verboten. Eine einzige konkrete Datei ist keine Architekturpflicht mehr. |

## Änderungen innerhalb erhaltener Tests

- `test_release_entry_point_and_runtime_dependency_contract_are_exact` behält
  strukturierte TOML-Verträge für Einstiegspunkte, leere Runtime-Abhängigkeiten,
  Ressourcen und Backend. Deklarierte Funktionen werden aufrufbar importiert,
  Ressourcen gelesen. Quelltextfragmente des Buildskripts entfallen; echte
  Wheel-/sdist-/pipx-Installation und exakte Ressourcenbytes bleiben im
  Packaging-E2E erhalten. Die unabhängige Paketdatei-Allowlist bleibt ausdrücklich.
- `test_bundle_handoff.py`: vier reine Wortlautassertions entfallen (Chat-Laufzeit,
  configured_shell als Textfragment, unbekannter Pfad/System). Environment-JSON
  bleibt exakt geprüft; bei unbekannten/unsicheren Pfaden dürfen weiterhin keine
  ausführbaren Beispiele entstehen. Shell-/PowerShell-Quoting und Fence-Injection
  bleiben Sicherheitsprüfungen, keine Prosa- oder Layoutvorgaben.
- `test_architecture.py`: derselbe reale Modulgraph bleibt azyklisch und stdlib-only.
  Importe werden statisch, auch verschachtelt, relativ und mit Alias aufgelöst;
  ein Kommentar oder String ist kein Import. Es wird kein Produktmodul ausgeführt.
  Ein tatsächliches Submodul in `from package import child` zählt als eigene Kante;
  normale Symbolimporte gehören zu ihrem Modul. Implizite Paketinitialisierung
  erzeugt keine erfundenen Zyklen. Fehlende/generische Scope-Module bleiben erkannt.
- CLI und Application dürfen ihre Fachaufgaben auf benannte `cli_*` bzw.
  `application_*`-Module verteilen. Bestehende negative Domänen-/Präsentations-/
  Prozessgrenzen gelten für diese Familien mit. Exakte positive Kanten zu einzelnen
  Plattformhelfern sowie identische Importmengen sind keine Pflicht mehr;
  native Primitive bleiben in den Plattformpaketen und Execution verwendet keine
  direkten POSIX-/Windows-Implementierungen. Dateiidentität, Symlinks, Creation-Time,
  Locks und Prozessbereinigung bleiben in ihren unveränderten Verhaltenstests.
- Watcher bleibt außerhalb des Core, nutzt dessen öffentliche API und isoliert
  Subprozesse in der Apply-Grenze. Verbot einzelner Funktionsnamen/Quelltextstrings
  entfällt. Die echten Worker-/CLI-/Scheduling-Tests prüfen Delegation, alte
  Konfigurationen, Ereignisse, Quiet-Time, Unterbrechung und Idle-Verhalten.
  Pack/Inspect/Validate und Handoff bleiben passiv (bestehende Prozess-/Netzsperren).
- Archivbeweise bleiben von Ausführung/CLI getrennt; numerische Exitcodes bleiben
  außerhalb der Fachlogik. API-Seiteneffekte und explizites CWD werden durch
  `test_api.py::test_public_import_has_no_cli_environment_or_stream_side_effects`
  und `test_relative_source_uses_explicit_cwd_without_chdir` geprüft, nicht durch
  das Nichtvorkommen der Zeichenketten `sys.exit` oder `os.chdir`.

## Neue Fälle und vollständiger Collection-Abgleich

| Neue Testfunktion | Fälle |
| --- | ---: |
| `tests/test_chat_contract.py::test_canonical_contract_can_be_loaded_and_rendered_without_execution` | 1 |
| `tests/test_chat_contract.py::test_documented_patch_manifest_validates_against_a_real_reference` | 1 |
| `tests/test_chat_contract.py::test_public_commands_accept_documented_arguments_and_reject_missing_or_unknown_ones` | 1 |
| `tests/test_architecture.py::test_application_layer_can_share_workflows_without_reverse_dependencies` | 1 |
| `tests/test_architecture_boundaries.py::test_import_edges_resolve_real_modules_without_executing_source` | 9 |
| `tests/test_architecture_boundaries.py::test_package_relative_import_resolves_from_initializer` | 1 |
| `tests/test_architecture_boundaries.py::test_workflow_can_be_split_without_moving_into_cli_or_domain` | 3 |
| `tests/test_architecture_boundaries.py::test_workflow_layer_rejects_reverse_and_presentation_dependencies` | 6 |
| `tests/test_architecture_boundaries.py::test_orchestration_cannot_hide_in_a_domain_service` | 1 |
| `tests/test_architecture_boundaries.py::test_aliases_cannot_hide_a_cycle_in_split_workflows` | 2 |

Es entfallen 25 alte Einzelkennungen; 26 Fälle kommen hinzu (darunter 22 kleine
adversarielle Architekturbeispiele). Erwartete Produkt-Collection: 3356 →
3357 Fälle. Der vollständige parallele Bericht wird gegen den Bericht
von Bundle 059 abgeglichen: exakt diese entfernten Kennungen, exakt die angegebenen
Fallzahlen pro neuer Funktion, keine weiteren Verluste. Die unveränderten 23
privaten Übergabe-Prüffälle kommen nur beim Development-Gate hinzu; sie gehören
nicht zur Produkt-Collection. Bestehende Plattform-Skips bleiben transparent.

## Bewusst nicht vorgezogene Arbeiten

Die deklarativen Docker-/CI-Rezeptchecks in `test_docker_integration_runner.py`
bleiben für RF-11 bestehen; ihre Nachweis-/Matrixumstellung wird hier nicht
vorweggenommen. Ebenso bleiben funktionale Paket-Allowlists und exakte
maschinenlesbare Schemas Sicherheitsverträge. Der historische Text in den
bestehenden Plänen und Spezifikationsdateien wird nicht umgeschrieben.
