# RF-06B: Abbau und Verhaltenstest-Zuordnung

Basis ist das tatsächliche Result 062, Commit `220c0af2189cebe29ae2c991c4a6afb65dc3cc1f`.
Bundle 063 bereitet einen Commit vor; Apply, vollständiges paralleles Gate und
Push dieses Zustands sind noch nicht bestätigt. Produktversion bleibt 1.4.0
bis zum vorgesehenen Versionsschritt RF-13.

## Produktänderungen und erhaltene Verträge

- Der native Reader unterstützt ausschließlich Result 3. Writer deklarieren `[3]`;
  originale 1.4.0-Capabilities `[1, 2, 3]` bleiben ebenso gültig. Keine alten
  Fixture-/Artefaktbytes, Identitäten oder Hashes werden passend umgeschrieben.
- Result-Wheel-Reader/Provider/Installations-Bootstrap, der alte Wheel-Rezept-
  Generator und die zusätzliche geladene Wheel-Identität entfallen. Die normale
  Wheel-/sdist-Installation, RECORD-Generierung und der separate Watcher bleiben.
  RECORD wird nur noch im Buildbackend erzeugt; der bisherige Laufzeithelfer
  `wheel_record.py` entfällt aus Core und PYZ.
- Pack bindet ausschließlich den eigenen PYZ-Provider oder den schon vorhandenen
  begrenzten Source-Pfad. Defekte eigene Ressourcen dürfen keine fremde
  Installation oder Referenz-Anleitung auswählen. Die ausschließlich für Result 1
  benötigte Erfindung fehlender Handoff-Daten entfällt.
- Alte Results sind keine Referenz-, Archivierungs- oder Recovery-Erfolgsbelege.
  Der PYZ-Bootstrap behandelt sie als nicht unterstützt, ohne Ersatz-Ausführung.
  Technisch nicht verfügbare aktuelle PYZs behalten ihren dokumentierten Fallback;
  Vorprüfung, native Referenzprüfung und Authentizität bleiben unterschiedliche Aussagen.
- Die zwei geschlossenen Python-Anforderungsvarianten des weiterhin gültigen
  PYZ-Rezeptvertrags bleiben Datenverträge. Ein Produktversionsraten oder eine
  künstliche Sperre gültiger Format-3-Daten ist nicht eingeführt. Die alten
  ausführbaren Format-1/2-Reader-Fixtures und positive Vorwärtsprüfung eines
  eingefrorenen 1.3.0-Readers entfallen. Gepinnte alte Result-ZIPs bleiben negative Datenfixtures.
- CPython >=3.10, Windows-Handle-/ACL-Schutz, Ressourcenlimits, sichere Pfade,
  unveränderte Fehlerkategorien, atomare Veröffentlichung und alle vier
  Repositorybindungswerte bleiben erhalten. Die drei Normdateien bleiben getrennt.

## Tests statt ungeprüfter Löschung

Die folgenden Zuordnungen decken jede entfernte oder verschobene Testfunktion ab.
Ein Ziel bezeichnet sämtliche parametrischen Fälle dieser Funktion; der lokale
Nachweis muss diese Funktionen tatsächlich ausführen. Wheel-spezifische Installer-,
RECORD- und Requirements-Parser-Fälle entfallen mit dem nicht mehr vorhandenen
Runtime-Wheel-Vertrag. Deren allgemeine Sicherheitsziele bleiben bei PYZ und
normaler Installation geprüft. Es werden keine Legacy-Produktimplementierungen
zur Erhaltung alter positiver Tests in Testhilfen kopiert.

Gemeinsame Referenzfixtures erzeugen nun aktuelle Result-3-Daten. Erfolg, Fehler,
Dirty-Zustand, SHA-1/SHA-256, Zeit-/Statuskonsistenz und passive Handoff-Daten
bleiben geprüft. Positive Result-1/2- und fehlende-Handoff-Kombinationen entfallen;
fehlender Handoff bleibt ein negativer Result-3-Schemafall. Originale 1.4.0-Fixtures
unter `tests/fixtures/compatibility_140/` bleiben bytegleich.

Der uv-Nachweis behält seine CI-Kennung
`tests/test_runtime_bootstrap.py::test_uv_installed_runtime_works_outside_checkout`.
Er installiert das normale lokal gebaute Wheel offline, verwendet die installierte
API außerhalb des Checkouts und anschließend dessen eigene Core-PYZ ohne
Installation. Beide müssen denselben unveränderten Result vollständig validieren
und neue Patches packen. CI-Matrix und manuelle Auslösung bleiben unverändert;
CI startet ausschließlich Christian. Fehlt uv lokal, wird der vorhandene
plattformbezogene Skip ehrlich ausgewiesen, nicht als Installationsbeleg gewertet.

| Bisheriger Test | Heutiger Nachweis / Grund |
| --- | --- |
| `tests/test_captured_reference.py::test_capture_retains_actual_binding_suffix_and_exact_handoff` | `tests/test_captured_reference.py::test_capture_retains_actual_binding_suffix_and_exact_handoff`; Positive ohne-Handoff-Result-1-Varianten entfallen; alle Zustände und Dirty-Varianten bleiben mit Result-3-Handoff erhalten. |
| `tests/test_pack_candidate.py::test_candidate_preserves_exact_binding_and_is_natively_valid` | `tests/test_pack_candidate.py::test_candidate_preserves_exact_binding_and_is_natively_valid`; Alte Resultformat-1/2-Varianten entfallen; gleicher Kandidatvertrag für alle aktuellen Resultzustände. |
| `tests/test_python_variants.py::test_complete_frozen_130_reader_keeps_or_rejects_variant_without_mixed_modules` | `tests/test_compatibility_140.py::test_current_reader_preserves_original_reference_and_execution_facts`, `tests/test_compatibility_140.py::test_original_patches_retain_payload_modes_and_full_binding`, `tests/test_compatibility_140.py::test_original_partial_progress_and_dirty_snapshot_are_not_clean_success`, `tests/test_compatibility_140.py::test_pinned_original_pyz_operates_in_fresh_stdlib_process`, `tests/test_compatibility_140.py::test_fixture_capture_is_pinned_to_original_release_code_and_generator`; Die Vorwärtslesbarkeit des alten 1.3.0-Readers entfällt. Maßgeblich sind unveränderte Original-1.4.0-Referenzen und ihre eigene PYZ. |
| `tests/test_pyz_bootstrap.py::test_legacy_result_selects_explicit_previous_path` | `tests/test_pyz_bootstrap.py::test_unsupported_result_never_selects_an_execution_fallback`; Nicht unterstützte Formate erzeugen jetzt einen Fehler statt eines Ausführungs-Fallbacks. |
| `tests/test_result_format2.py::test_all_unavailable_reasons_are_readable_without_wheel` | `tests/test_result_format3.py::test_unavailable_runtime_preserves_known_or_unknown_producer_data`, `tests/test_result_format3.py::test_unavailable_is_not_a_permissive_repair_contract`; Aktuelle unavailable-Form deckt alle Gründe und falsche Artefaktbehauptungen ab. |
| `tests/test_result_format2.py::test_categorized_tool_failure_remains_a_reference_and_can_be_published` | `tests/test_result_reader_contracts.py::test_categorized_tool_failure_remains_a_reference_and_can_be_published`; Auf Result 3 übertragen; alte Formatparametrisierung entfällt, fachliche Grenze bleibt. |
| `tests/test_result_format2.py::test_cli_reference_validation_accepts_format2` | `tests/test_result_reader_contracts.py::test_cli_reference_validation_accepts_format3`; Auf Result 3 übertragen; alte Formatparametrisierung entfällt, fachliche Grenze bleibt. |
| `tests/test_result_format2.py::test_corrupt_format2_never_validates` | `tests/test_result_format3.py::test_corrupt_format3_never_becomes_a_full_native_reference`, `tests/test_result_capabilities.py::test_other_result_capabilities_are_rejected_without_output`; Deskriptor-, Schema-, Hash-, Provenienz-, Handoff- und Capability-Angriffe bleiben auf Result 3 geprüft; Wheel-Tags gehören nicht mehr zum Runtimeprofil. |
| `tests/test_result_format2.py::test_format2_reference_preserves_binding_and_separates_success_policy` | `tests/test_result_reader_contracts.py::test_format3_reference_preserves_binding_and_separates_success_policy`; Auf Result 3 übertragen; alte Formatparametrisierung entfällt, fachliche Grenze bleibt. |
| `tests/test_result_format2.py::test_inner_bytes_share_the_remaining_outer_request_budget` | `tests/test_result_reader_contracts.py::test_inner_bytes_share_the_remaining_outer_request_budget`; Auf Result 3 übertragen; alte Formatparametrisierung entfällt, fachliche Grenze bleibt. |
| `tests/test_result_format2.py::test_inner_entry_count_uses_request_limit_before_resource_reads` | `tests/test_result_reader_contracts.py::test_inner_entry_count_uses_request_limit_before_resource_reads`; Auf Result 3 übertragen; alte Formatparametrisierung entfällt, fachliche Grenze bleibt. |
| `tests/test_result_format2.py::test_metadata_budget_is_enforced_before_json_parse` | `tests/test_result_reader_contracts.py::test_metadata_budget_is_enforced_before_json_parse`; Auf Result 3 übertragen; alte Formatparametrisierung entfällt, fachliche Grenze bleibt. |
| `tests/test_result_format2.py::test_publication_verifies_format2_bytes_and_detects_corruption` | `tests/test_result_reader_contracts.py::test_publication_verifies_format3_bytes_and_detects_corruption`; Auf Result 3 übertragen; alte Formatparametrisierung entfällt, fachliche Grenze bleibt. |
| `tests/test_result_format2.py::test_reader_does_not_materialize_import_execute_or_write_runtime` | `tests/test_result_reader_contracts.py::test_reader_does_not_import_execute_or_write_runtime`; Auf Result 3 übertragen; alte Formatparametrisierung entfällt, fachliche Grenze bleibt. |
| `tests/test_result_format2.py::test_real_recovery_consumes_only_complete_successful_format2_evidence` | `tests/test_result_format3_consumers.py::test_real_recovery_requires_full_format3_success`; Recovery auf aktuelle Belege übertragen; alte Formate werden ausdrücklich abgelehnt. |
| `tests/test_result_format2.py::test_rehashed_noncanonical_or_corrupt_wheel_is_rejected` | `tests/test_runtime_pyz.py::test_noncanonical_zip_is_rejected_even_when_all_payload_hashes_match`, `tests/test_runtime_pyz.py::test_raw_zip_boundary_mutations_fail`; ZIP-Kanonizität bleibt auf PYZ geprüft; Runtime-Wheel-RECORD entfällt. |
| `tests/test_result_format2.py::test_repository_runtime_path_is_not_the_embedded_namespace` | `tests/test_result_reader_contracts.py::test_repository_runtime_path_is_not_the_embedded_namespace`; Auf Result 3 übertragen; alte Formatparametrisierung entfällt, fachliche Grenze bleibt. |
| `tests/test_result_format2.py::test_result_classification_is_only_a_type_hint_and_never_a_patch` | `tests/test_result_reader_contracts.py::test_result_classification_is_only_a_type_hint_and_never_a_patch`; Auf Result 3 übertragen; alte Formatparametrisierung entfällt, fachliche Grenze bleibt. |
| `tests/test_result_format2.py::test_snapshot_unicode_paths_work_for_classifier_and_archive_without_relaxing_patches` | `tests/test_result_reader_contracts.py::test_snapshot_unicode_paths_work_for_classifier_and_archive_without_relaxing_patches`; Auf Result 3 übertragen; alte Formatparametrisierung entfällt, fachliche Grenze bleibt. |
| `tests/test_result_format2.py::test_unavailable_is_a_closed_diagnosis_not_implicit_repair` | `tests/test_result_format3.py::test_unavailable_runtime_preserves_known_or_unknown_producer_data`, `tests/test_result_format3.py::test_unavailable_is_not_a_permissive_repair_contract`; Aktuelle unavailable-Form deckt alle Gründe und falsche Artefaktbehauptungen ab. |
| `tests/test_result_format3_consumers.py::test_actual_readers_keep_unproven_format3_and_standalone_pyz` | `tests/test_result_format3_consumers.py::test_actual_readers_keep_unproven_format3_and_standalone_pyz`; Alte ausgeführte Reader entfallen; aktueller Reader bewahrt alte Results ohne Archivierungsfreigabe. |
| `tests/test_result_format3_consumers.py::test_result3_publication_and_legacy_bootstrap_keep_strict_format_boundaries` | `tests/test_result_format3_consumers.py::test_result3_publication_and_bootstrap_keep_strict_format_boundaries`; Bootstrap-Durchstich auf aktuelle PYZ umgestellt; Publikationsfehler bleiben gleich. |
| `tests/test_result_robustness.py::test_mixed_exchange_uses_actual_current_and_frozen_reader_decisions` | `tests/test_result_format3_consumers.py::test_actual_readers_keep_unproven_format3_and_standalone_pyz`; Alte ausführbare Reader sind keine Supportpflicht. Aktueller Exchange hält alte/unbewiesene Ergebnisse und autonome Runtimes konservativ zurück. |
| `tests/test_result_robustness.py::test_wheel_and_recipe_limits_precede_their_reads` | `tests/test_result_robustness.py::test_pyz_and_recipe_limits_precede_their_reads`; Gleiche Größen-/Reihenfolgegrenze gegen PYZ statt Wheel. |
| `tests/test_runtime_artifact.py::test_bounded_native_file_reader` | `tests/test_runtime_resource_boundaries.py::test_bounded_native_file_reader`; Unveränderten allgemeinen Dateilimit-Test in aktuelle Grenztests verschoben. |
| `tests/test_runtime_artifact.py::test_canonical_archive_has_complete_valid_record_and_no_recursion` | `tests/test_runtime_pyz.py::test_pyz_profile_roundtrips_canonically_without_code_execution`, `tests/test_runtime_profiles.py::test_current_build_uses_only_anchored_data_helpers`; Runtime-Wheel/RECORD entfällt; aktuelle PYZ-Kanonizität und normales Installations-Wheel/RECORD bleiben geprüft. |
| `tests/test_runtime_artifact.py::test_consistently_rehashed_but_incompatible_metadata_is_rejected` | `tests/test_runtime_pyz.py::test_hash_consistent_forbidden_inventory_is_rejected`, `tests/test_python_variants.py::test_rehashed_variant_disagreements_never_become_valid_references`; Wheel-METADATA/Tag-Parser entfällt; fremde dist-info/Abhängigkeiten und widersprüchliche PYZ-Metadaten bleiben ungültig. |
| `tests/test_runtime_artifact.py::test_content_id_covers_changed_code_of_same_version` | `tests/test_runtime_pyz.py::test_producer_content_and_artifact_ids_follow_distinct_finite_contracts`; Identitätsänderung bei gleicher Produktversion bleibt geprüft. |
| `tests/test_runtime_artifact.py::test_missing_resource_produces_structured_unavailable` | `tests/test_pyz_resources.py::test_invalid_own_directory_resources_never_trigger_foreign_fallback`, `tests/test_pyz_resources.py::test_pinned_request_survives_update_but_old_producer_rejects_same_version_replacement`; Ressourcenintegrität, fehlende Dateien, Symlinks und Erzeugerbindung auf aktuelle PYZ übertragen. |
| `tests/test_runtime_artifact.py::test_modified_resource_is_rejected` | `tests/test_pyz_resources.py::test_invalid_own_directory_resources_never_trigger_foreign_fallback`, `tests/test_pyz_resources.py::test_pinned_request_survives_update_but_old_producer_rejects_same_version_replacement`; Ressourcenintegrität, fehlende Dateien, Symlinks und Erzeugerbindung auf aktuelle PYZ übertragen. |
| `tests/test_runtime_artifact.py::test_provider_does_not_write_or_start_processes` | `tests/test_pyz_resources.py::test_unprepared_source_does_not_scan_build_cache_or_other_installation`, `tests/test_pyz_resources.py::test_capture_performs_no_writes_external_processes_or_network`; Source-Ausfall und rein lesende request-lokale PYZ-Erfassung bleiben erhalten. |
| `tests/test_runtime_artifact.py::test_recipe_closed_schema_and_identity` | `tests/test_runtime_pyz.py::test_hash_consistent_forbidden_inventory_is_rejected`, `tests/test_runtime_pyz.py::test_even_rehashed_recipe_must_obey_closed_schema_inventory_and_identities`; Geschlossene Pfade, Schema, Inventar und Identität bleiben im PYZ-Profil geprüft. |
| `tests/test_runtime_artifact.py::test_recipe_inventory_and_budget` | `tests/test_runtime_pyz.py::test_hash_consistent_forbidden_inventory_is_rejected`, `tests/test_runtime_pyz.py::test_even_rehashed_recipe_must_obey_closed_schema_inventory_and_identities`; Geschlossene Pfade, Schema, Inventar und Identität bleiben im PYZ-Profil geprüft. |
| `tests/test_runtime_artifact.py::test_recipe_size_limit_precedes_parsing` | `tests/test_pyz_resources.py::test_invalid_own_directory_resources_never_trigger_foreign_fallback`; Zu großes Rezept bleibt vor unbegrenztem Einlesen abgelehnt. |
| `tests/test_runtime_artifact.py::test_repreparing_transport_replaces_stale_resources_without_mutating_input` | `tests/test_runtime_packaging.py::test_source_build_ignores_stale_build_outputs_and_preserves_prepared_metadata`; Alter Transportgenerator entfällt; aktueller Build bleibt gegen veraltete Outputs und fremde Module geprüft. |
| `tests/test_runtime_artifact.py::test_request_pins_once_and_fresh_request_rejects_changed_installation` | `tests/test_pyz_resources.py::test_invalid_own_directory_resources_never_trigger_foreign_fallback`, `tests/test_pyz_resources.py::test_pinned_request_survives_update_but_old_producer_rejects_same_version_replacement`; Ressourcenintegrität, fehlende Dateien, Symlinks und Erzeugerbindung auf aktuelle PYZ übertragen. |
| `tests/test_runtime_artifact.py::test_runtime_symlink_is_unavailable` | `tests/test_pyz_resources.py::test_invalid_own_directory_resources_never_trigger_foreign_fallback`, `tests/test_pyz_resources.py::test_pinned_request_survives_update_but_old_producer_rejects_same_version_replacement`; Ressourcenintegrität, fehlende Dateien, Symlinks und Erzeugerbindung auf aktuelle PYZ übertragen. |
| `tests/test_runtime_artifact.py::test_source_mode_does_not_build_or_search_caches` | `tests/test_pyz_resources.py::test_unprepared_source_does_not_scan_build_cache_or_other_installation`, `tests/test_pyz_resources.py::test_capture_performs_no_writes_external_processes_or_network`; Source-Ausfall und rein lesende request-lokale PYZ-Erfassung bleiben erhalten. |
| `tests/test_runtime_artifact.py::test_untrusted_inventory_paths_are_rejected_before_read` | `tests/test_runtime_pyz.py::test_hash_consistent_forbidden_inventory_is_rejected`, `tests/test_runtime_pyz.py::test_even_rehashed_recipe_must_obey_closed_schema_inventory_and_identities`; Geschlossene Pfade, Schema, Inventar und Identität bleiben im PYZ-Profil geprüft. |
| `tests/test_runtime_bootstrap.py::test_actual_offline_install_and_native_reference_check` | `tests/test_pyz_bootstrap.py::test_stdlib_precheck_is_readonly_and_does_not_claim_native_reference_success`, `tests/test_pyz_bootstrap.py::test_source_hash_mismatch_never_prepares_or_imports`, `tests/test_pyz_bootstrap.py::test_unavailable_runtime_does_not_erase_or_repair_the_original_result`, `tests/test_pyz_bootstrap.py::test_changed_prepared_file_is_rejected_before_import`, `tests/test_pyz_bootstrap.py::test_foreign_already_imported_core_is_kept_and_conflict_is_reported`, `tests/test_pyz_bootstrap.py::test_fresh_stdlib_only_process_prepares_imports_and_uses_built_pyz_without_subprocesses`, `tests/test_result3_embedded_bootstrap.py::test_own_embedded_bootstrap_runs_in_fresh_process_and_pack_uses_same_result`; Wheel-Installation/Prozessadapter entfällt. Aktueller Bootstrap installiert nichts, prüft Herkunft/Hashes/Import und verweigert falsche native Validierung. Installer-spezifische Fehler sind entfallen; ihre Pflicht, keinen Erfolg vorzutäuschen, bleibt. |
| `tests/test_runtime_bootstrap.py::test_assessment_is_read_only_and_unknown_source_never_installs` | `tests/test_pyz_bootstrap.py::test_stdlib_precheck_is_readonly_and_does_not_claim_native_reference_success`, `tests/test_pyz_bootstrap.py::test_source_hash_mismatch_never_prepares_or_imports`, `tests/test_pyz_bootstrap.py::test_unavailable_runtime_does_not_erase_or_repair_the_original_result`, `tests/test_pyz_bootstrap.py::test_changed_prepared_file_is_rejected_before_import`, `tests/test_pyz_bootstrap.py::test_foreign_already_imported_core_is_kept_and_conflict_is_reported`, `tests/test_pyz_bootstrap.py::test_fresh_stdlib_only_process_prepares_imports_and_uses_built_pyz_without_subprocesses`, `tests/test_result3_embedded_bootstrap.py::test_own_embedded_bootstrap_runs_in_fresh_process_and_pack_uses_same_result`; Wheel-Installation/Prozessadapter entfällt. Aktueller Bootstrap installiert nichts, prüft Herkunft/Hashes/Import und verweigert falsche native Validierung. Installer-spezifische Fehler sind entfallen; ihre Pflicht, keinen Erfolg vorzutäuschen, bleibt. |
| `tests/test_runtime_bootstrap.py::test_bad_repository_evidence_still_blocks_runtime_fallback` | `tests/test_pyz_bootstrap.py::test_stdlib_precheck_is_readonly_and_does_not_claim_native_reference_success`, `tests/test_pyz_bootstrap.py::test_source_hash_mismatch_never_prepares_or_imports`, `tests/test_pyz_bootstrap.py::test_unavailable_runtime_does_not_erase_or_repair_the_original_result`, `tests/test_pyz_bootstrap.py::test_changed_prepared_file_is_rejected_before_import`, `tests/test_pyz_bootstrap.py::test_foreign_already_imported_core_is_kept_and_conflict_is_reported`, `tests/test_pyz_bootstrap.py::test_fresh_stdlib_only_process_prepares_imports_and_uses_built_pyz_without_subprocesses`, `tests/test_result3_embedded_bootstrap.py::test_own_embedded_bootstrap_runs_in_fresh_process_and_pack_uses_same_result`; Wheel-Installation/Prozessadapter entfällt. Aktueller Bootstrap installiert nichts, prüft Herkunft/Hashes/Import und verweigert falsche native Validierung. Installer-spezifische Fehler sind entfallen; ihre Pflicht, keinen Erfolg vorzutäuschen, bleibt. |
| `tests/test_runtime_bootstrap.py::test_complete_python_requirement_is_enforced_before_installation` | `tests/test_pyz_bootstrap.py::test_stdlib_precheck_is_readonly_and_does_not_claim_native_reference_success`, `tests/test_pyz_bootstrap.py::test_source_hash_mismatch_never_prepares_or_imports`, `tests/test_pyz_bootstrap.py::test_unavailable_runtime_does_not_erase_or_repair_the_original_result`, `tests/test_pyz_bootstrap.py::test_changed_prepared_file_is_rejected_before_import`, `tests/test_pyz_bootstrap.py::test_foreign_already_imported_core_is_kept_and_conflict_is_reported`, `tests/test_pyz_bootstrap.py::test_fresh_stdlib_only_process_prepares_imports_and_uses_built_pyz_without_subprocesses`, `tests/test_result3_embedded_bootstrap.py::test_own_embedded_bootstrap_runs_in_fresh_process_and_pack_uses_same_result`; Wheel-Installation/Prozessadapter entfällt. Aktueller Bootstrap installiert nichts, prüft Herkunft/Hashes/Import und verweigert falsche native Validierung. Installer-spezifische Fehler sind entfallen; ihre Pflicht, keinen Erfolg vorzutäuschen, bleibt. |
| `tests/test_runtime_bootstrap.py::test_failed_bootstrap_has_one_attempt_and_uses_previous_handoff` | `tests/test_pyz_bootstrap.py::test_stdlib_precheck_is_readonly_and_does_not_claim_native_reference_success`, `tests/test_pyz_bootstrap.py::test_source_hash_mismatch_never_prepares_or_imports`, `tests/test_pyz_bootstrap.py::test_unavailable_runtime_does_not_erase_or_repair_the_original_result`, `tests/test_pyz_bootstrap.py::test_changed_prepared_file_is_rejected_before_import`, `tests/test_pyz_bootstrap.py::test_foreign_already_imported_core_is_kept_and_conflict_is_reported`, `tests/test_pyz_bootstrap.py::test_fresh_stdlib_only_process_prepares_imports_and_uses_built_pyz_without_subprocesses`, `tests/test_result3_embedded_bootstrap.py::test_own_embedded_bootstrap_runs_in_fresh_process_and_pack_uses_same_result`; Wheel-Installation/Prozessadapter entfällt. Aktueller Bootstrap installiert nichts, prüft Herkunft/Hashes/Import und verweigert falsche native Validierung. Installer-spezifische Fehler sind entfallen; ihre Pflicht, keinen Erfolg vorzutäuschen, bleibt. |
| `tests/test_runtime_bootstrap.py::test_forbidden_runtime_profile_never_executes_even_with_rehashed_outer_descriptors` | `tests/test_pyz_bootstrap.py::test_stdlib_precheck_is_readonly_and_does_not_claim_native_reference_success`, `tests/test_pyz_bootstrap.py::test_source_hash_mismatch_never_prepares_or_imports`, `tests/test_pyz_bootstrap.py::test_unavailable_runtime_does_not_erase_or_repair_the_original_result`, `tests/test_pyz_bootstrap.py::test_changed_prepared_file_is_rejected_before_import`, `tests/test_pyz_bootstrap.py::test_foreign_already_imported_core_is_kept_and_conflict_is_reported`, `tests/test_pyz_bootstrap.py::test_fresh_stdlib_only_process_prepares_imports_and_uses_built_pyz_without_subprocesses`, `tests/test_result3_embedded_bootstrap.py::test_own_embedded_bootstrap_runs_in_fresh_process_and_pack_uses_same_result`; Wheel-Installation/Prozessadapter entfällt. Aktueller Bootstrap installiert nichts, prüft Herkunft/Hashes/Import und verweigert falsche native Validierung. Installer-spezifische Fehler sind entfallen; ihre Pflicht, keinen Erfolg vorzutäuschen, bleibt. |
| `tests/test_runtime_bootstrap.py::test_invalid_or_changed_validation_inputs_never_receive_success` | `tests/test_pyz_bootstrap.py::test_stdlib_precheck_is_readonly_and_does_not_claim_native_reference_success`, `tests/test_pyz_bootstrap.py::test_source_hash_mismatch_never_prepares_or_imports`, `tests/test_pyz_bootstrap.py::test_unavailable_runtime_does_not_erase_or_repair_the_original_result`, `tests/test_pyz_bootstrap.py::test_changed_prepared_file_is_rejected_before_import`, `tests/test_pyz_bootstrap.py::test_foreign_already_imported_core_is_kept_and_conflict_is_reported`, `tests/test_pyz_bootstrap.py::test_fresh_stdlib_only_process_prepares_imports_and_uses_built_pyz_without_subprocesses`, `tests/test_result3_embedded_bootstrap.py::test_own_embedded_bootstrap_runs_in_fresh_process_and_pack_uses_same_result`; Wheel-Installation/Prozessadapter entfällt. Aktueller Bootstrap installiert nichts, prüft Herkunft/Hashes/Import und verweigert falsche native Validierung. Installer-spezifische Fehler sind entfallen; ihre Pflicht, keinen Erfolg vorzutäuschen, bleibt. |
| `tests/test_runtime_bootstrap.py::test_missing_installer_uses_previous_handoff` | `tests/test_pyz_bootstrap.py::test_stdlib_precheck_is_readonly_and_does_not_claim_native_reference_success`, `tests/test_pyz_bootstrap.py::test_source_hash_mismatch_never_prepares_or_imports`, `tests/test_pyz_bootstrap.py::test_unavailable_runtime_does_not_erase_or_repair_the_original_result`, `tests/test_pyz_bootstrap.py::test_changed_prepared_file_is_rejected_before_import`, `tests/test_pyz_bootstrap.py::test_foreign_already_imported_core_is_kept_and_conflict_is_reported`, `tests/test_pyz_bootstrap.py::test_fresh_stdlib_only_process_prepares_imports_and_uses_built_pyz_without_subprocesses`, `tests/test_result3_embedded_bootstrap.py::test_own_embedded_bootstrap_runs_in_fresh_process_and_pack_uses_same_result`; Wheel-Installation/Prozessadapter entfällt. Aktueller Bootstrap installiert nichts, prüft Herkunft/Hashes/Import und verweigert falsche native Validierung. Installer-spezifische Fehler sind entfallen; ihre Pflicht, keinen Erfolg vorzutäuschen, bleibt. |
| `tests/test_runtime_bootstrap.py::test_runtime_cannot_import_project_shadow_modules` | `tests/test_pyz_bootstrap.py::test_stdlib_precheck_is_readonly_and_does_not_claim_native_reference_success`, `tests/test_pyz_bootstrap.py::test_source_hash_mismatch_never_prepares_or_imports`, `tests/test_pyz_bootstrap.py::test_unavailable_runtime_does_not_erase_or_repair_the_original_result`, `tests/test_pyz_bootstrap.py::test_changed_prepared_file_is_rejected_before_import`, `tests/test_pyz_bootstrap.py::test_foreign_already_imported_core_is_kept_and_conflict_is_reported`, `tests/test_pyz_bootstrap.py::test_fresh_stdlib_only_process_prepares_imports_and_uses_built_pyz_without_subprocesses`, `tests/test_result3_embedded_bootstrap.py::test_own_embedded_bootstrap_runs_in_fresh_process_and_pack_uses_same_result`; Wheel-Installation/Prozessadapter entfällt. Aktueller Bootstrap installiert nichts, prüft Herkunft/Hashes/Import und verweigert falsche native Validierung. Installer-spezifische Fehler sind entfallen; ihre Pflicht, keinen Erfolg vorzutäuschen, bleibt. |
| `tests/test_runtime_bootstrap.py::test_runtime_only_defect_uses_original_reference_without_forging_native_success` | `tests/test_pyz_bootstrap.py::test_stdlib_precheck_is_readonly_and_does_not_claim_native_reference_success`, `tests/test_pyz_bootstrap.py::test_source_hash_mismatch_never_prepares_or_imports`, `tests/test_pyz_bootstrap.py::test_unavailable_runtime_does_not_erase_or_repair_the_original_result`, `tests/test_pyz_bootstrap.py::test_changed_prepared_file_is_rejected_before_import`, `tests/test_pyz_bootstrap.py::test_foreign_already_imported_core_is_kept_and_conflict_is_reported`, `tests/test_pyz_bootstrap.py::test_fresh_stdlib_only_process_prepares_imports_and_uses_built_pyz_without_subprocesses`, `tests/test_result3_embedded_bootstrap.py::test_own_embedded_bootstrap_runs_in_fresh_process_and_pack_uses_same_result`; Wheel-Installation/Prozessadapter entfällt. Aktueller Bootstrap installiert nichts, prüft Herkunft/Hashes/Import und verweigert falsche native Validierung. Installer-spezifische Fehler sind entfallen; ihre Pflicht, keinen Erfolg vorzutäuschen, bleibt. |
| `tests/test_runtime_bootstrap.py::test_technical_native_tool_failure_uses_previous_checks` | `tests/test_pyz_bootstrap.py::test_stdlib_precheck_is_readonly_and_does_not_claim_native_reference_success`, `tests/test_pyz_bootstrap.py::test_source_hash_mismatch_never_prepares_or_imports`, `tests/test_pyz_bootstrap.py::test_unavailable_runtime_does_not_erase_or_repair_the_original_result`, `tests/test_pyz_bootstrap.py::test_changed_prepared_file_is_rejected_before_import`, `tests/test_pyz_bootstrap.py::test_foreign_already_imported_core_is_kept_and_conflict_is_reported`, `tests/test_pyz_bootstrap.py::test_fresh_stdlib_only_process_prepares_imports_and_uses_built_pyz_without_subprocesses`, `tests/test_result3_embedded_bootstrap.py::test_own_embedded_bootstrap_runs_in_fresh_process_and_pack_uses_same_result`; Wheel-Installation/Prozessadapter entfällt. Aktueller Bootstrap installiert nichts, prüft Herkunft/Hashes/Import und verweigert falsche native Validierung. Installer-spezifische Fehler sind entfallen; ihre Pflicht, keinen Erfolg vorzutäuschen, bleibt. |
| `tests/test_runtime_profiles.py::test_current_build_uses_only_anchored_data_helpers` | `tests/test_runtime_profiles.py::test_current_build_uses_only_anchored_data_helpers`; Wheel-RECORD ist nur noch Build-Code im Buildbackend; die drei verbliebenen Runtime-Datenprimitive behalten die Importgrenze. |
| `tests/test_runtime_robustness.py::test_case_ambiguous_inventory_is_not_portable` | `tests/test_runtime_pyz.py::test_even_rehashed_recipe_must_obey_closed_schema_inventory_and_identities`, `tests/test_python_variants.py::test_rehashed_variant_disagreements_never_become_valid_references`; Portable Inventare und Identitätsdaten bleiben rein validierte Daten. |
| `tests/test_runtime_robustness.py::test_concurrent_requests_need_no_cache_or_temporary_files` | `tests/test_runtime_resource_boundaries.py::test_concurrent_requests_need_no_cache_or_temporary_files`; Bestehende Verhaltenserwartung auf PYZ/shared-resource-Pfad übertragen. |
| `tests/test_runtime_robustness.py::test_constructed_recipe_cannot_bypass_validated_bytes` | `tests/test_runtime_resource_boundaries.py::test_constructed_recipe_cannot_bypass_validated_bytes`; Bestehende Verhaltenserwartung auf PYZ/shared-resource-Pfad übertragen. |
| `tests/test_runtime_robustness.py::test_exact_archive_budget_includes_record_before_any_resource_read` | `tests/test_runtime_pyz.py::test_runtime_resource_and_shared_budgets_are_independent`; Runtime-Wheel-RECORD entfällt; Größe und innere/äußere PYZ-Budgets bleiben separat begrenzt. |
| `tests/test_runtime_robustness.py::test_installation_directory_named_src_is_supported` | `tests/test_runtime_resource_boundaries.py::test_installation_directory_named_src_is_supported`; Bestehende Verhaltenserwartung auf PYZ/shared-resource-Pfad übertragen. |
| `tests/test_runtime_robustness.py::test_invalid_json_never_reaches_resource_reads` | `tests/test_runtime_resource_boundaries.py::test_invalid_json_never_reaches_payload_reads`; Duplicate/NaN/tiefes JSON wird vor Payload-Lesen abgelehnt. |
| `tests/test_runtime_robustness.py::test_invalid_python_requirement_is_rejected` | `tests/test_python_variants.py::test_unknown_python_contract_is_rejected_even_with_recomputed_ids`, `tests/test_python_variants.py::test_both_closed_variants_pass_static_reference_and_bootstrap_without_import`; Allgemeiner Wheel-Requirements-Parser entfällt; die geschlossenen PYZ-Varianten bleiben strikt. |
| `tests/test_runtime_robustness.py::test_loaded_producer_rejects_coherent_same_version_replacement` | `tests/test_pyz_resources.py::test_pinned_request_survives_update_but_old_producer_rejects_same_version_replacement`; Derselbe Angriff gegen den aktiven PYZ-Provider. |
| `tests/test_runtime_robustness.py::test_oversized_installed_recipe_is_a_resource_limit` | `tests/test_pyz_resources.py::test_invalid_own_directory_resources_never_trigger_foreign_fallback`; Aktueller Provider liefert den begrenzten resource_limit-Fehler. |
| `tests/test_runtime_robustness.py::test_parent_directory_replaced_during_resource_read_is_rejected` | `tests/test_runtime_resource_boundaries.py::test_parent_directory_replaced_during_resource_read_is_rejected`; Bestehende Verhaltenserwartung auf PYZ/shared-resource-Pfad übertragen. |
| `tests/test_runtime_robustness.py::test_rehashed_identity_module_is_data_not_executed_code` | `tests/test_runtime_pyz.py::test_even_rehashed_recipe_must_obey_closed_schema_inventory_and_identities`, `tests/test_python_variants.py::test_rehashed_variant_disagreements_never_become_valid_references`; Portable Inventare und Identitätsdaten bleiben rein validierte Daten. |
| `tests/test_runtime_robustness.py::test_supported_python_requirement_profile` | `tests/test_python_variants.py::test_unknown_python_contract_is_rejected_even_with_recomputed_ids`, `tests/test_python_variants.py::test_both_closed_variants_pass_static_reference_and_bootstrap_without_import`; Allgemeiner Wheel-Requirements-Parser entfällt; die geschlossenen PYZ-Varianten bleiben strikt. |
| `tests/test_runtime_robustness.py::test_unavailable_capture_is_pinned_per_request` | `tests/test_runtime_resource_boundaries.py::test_unavailable_capture_is_pinned_per_request`; Bestehende Verhaltenserwartung auf PYZ/shared-resource-Pfad übertragen. |
| `tests/test_runtime_robustness.py::test_unexpected_errors_and_cancellation_are_visible_and_release_lock` | `tests/test_pyz_resources.py::test_programming_errors_and_cancellation_propagate_and_release_lock`; Programmierfehler/Abbruch werden nicht als unavailable verschluckt; Lock wird freigegeben. |

## Entfernte Dateien

Die Löschungen erfolgen ausschließlich durch den geprüften Apply-Entrypoint.
Er prüft vor der ersten Löschung **alle** betroffenen Originaldateien anhand ihrer
vollständigen Hashes und Modi sowie Branch, Base-Commit und den übrigen
Dateizustand. Fremde, fehlende, veränderte oder verlinkte Pfade führen zum Abbruch.
Er löscht nur die explizit aufgeführten regulären Dateien, keine Verzeichnisse.
Danach prüft er vollständigen Änderungsumfang, läuft das volle parallele Gate,
committet genau den geprüften Stand und pusht einmal normal.

- `scripts/runtime_bootstrap.py`
- `src/patchharbor/result_runtime.py`
- `src/patchharbor/runtime_artifact.py`
- `src/patchharbor/runtime_wheel.py`
- `src/patchharbor/wheel_record.py`
- `tests/bootstrap_process.py`
- `tests/fixtures/result_format1/archive_evidence.py`
- `tests/fixtures/result_format1/exchange.py`
- `tests/fixtures/result_format1/patch_inspection.py`
- `tests/fixtures/result_format1/provenance.json`
- `tests/fixtures/result_format1/result_reader.py`
- `tests/fixtures/result_format2/patchharbor-1.2.1-py3-none-any.whl`
- `tests/fixtures/result_format2/provenance.json`
- `tests/fixtures/result_runtime_unavailable.json`
- `tests/legacy_runtime_support.py`
- `tests/test_result_format2.py`
- `tests/test_runtime_artifact.py`
- `tests/test_runtime_robustness.py`

## Gezielte parallele Development-Auswahl

Development prüft ausschließlich die folgende Auswahl und die privaten
Verhaltenstests des tatsächlich erzeugten Entrypoints. Kein Development-
Volltestnachweis wird behauptet. Collection und Outcomes werden mit dem
vollständigen Apply-Bericht 062 verglichen; jede entfallene Node-ID benötigt
obige Zuordnung. Nicht verfügbare native Bedingungen werden gesondert berichtet.
Die vollständige parallele Suite läuft im Apply vor dem einen Commit.

- `tests/test_architecture.py`
- `tests/test_architecture_boundaries.py`
- `tests/test_runtime_profiles.py`
- `tests/test_runtime_pyz.py`
- `tests/test_runtime_resource_boundaries.py`
- `tests/test_pyz_resources.py`
- `tests/test_pyz_result_resources.py`
- `tests/test_pyz_result_e2e.py`
- `tests/test_reference_validation.py`
- `tests/test_reference_validation_errors.py`
- `tests/test_captured_reference.py`
- `tests/test_result_format3.py`
- `tests/test_result_capabilities.py`
- `tests/test_result_reader_contracts.py`
- `tests/test_result_format3_consumers.py`
- `tests/test_result_robustness.py`
- `tests/test_result3_embedded_bootstrap.py`
- `tests/test_runtime_packaging.py`
- `tests/test_runtime_bootstrap.py`
- `tests/test_packaging_e2e.py`
- `tests/test_python_variants.py`
- `tests/test_producer_compatibility.py`
- `tests/test_python_compat.py`
- `tests/test_bootstrap_python_compat.py`
- `tests/test_pyz_bootstrap.py`
- `tests/test_pack_api.py`
- `tests/test_pack_candidate.py`
- `tests/test_pack_sources.py`
- `tests/test_pack_cli.py`
- `tests/test_pack_examples.py`
- `tests/test_pack_exchange_e2e.py`
- `tests/test_result_runtime_roundtrip.py`
- `tests/test_result_runtime_writer.py`
- `tests/test_result_runtime_publication.py`
- `tests/test_bundle_handoff.py`
- `tests/test_chat_contract.py`
- `tests/test_release_audit.py`
- `tests/test_compatibility_140.py`
- `tests/test_archive_maintenance.py`
- `tests/test_exchange_recovery.py`
- `tests/test_result_verification.py`
- `tests/test_handoff_ci.py`
