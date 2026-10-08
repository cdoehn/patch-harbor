# PP-08A: konkrete Testzuordnung

Jede Kennung aus der verbindlichen Revision-2-Matrix ist hier zugeordnet.
Funktions-Node-IDs bezeichnen jeweils sämtliche parametrisierten Varianten.
Die vollständige Sammlung, Interpreter, Worker, Skips und Ergebnisse stehen im
gebundenen JSON des vollständigen parallelen Laufs; diese Tabelle behauptet
keine Ausführung auf einem anderen Betriebssystem. Historische Übergangsgates
und redaktionelle Bewertungen bleiben ausdrücklich Reviewnachweise.

| Szenario | Ausführbarer Selektor / gesonderter Nachweis |
|---|---|
| Z-01 | `tests/test_pyz_bootstrap.py::test_fresh_stdlib_only_process_prepares_imports_and_uses_built_pyz_without_subprocesses` |
| Z-02 | `tests/test_runtime_pyz.py::test_built_pyz_entrypoint_imports_shared_cli_without_install_or_watcher`; `tests/test_pyz_result_e2e.py::test_first_production_result_uses_own_instruction_then_regular_pyz_apply` |
| Z-03 | `tests/test_pyz_bootstrap.py::test_direct_pyz_cli_pack_inspect_validate_outside_checkout` |
| Z-04 | `tests/test_pyz_bootstrap.py::test_fresh_stdlib_only_process_prepares_imports_and_uses_built_pyz_without_subprocesses` |
| Z-05 | `tests/test_runtime_pyz.py::test_normal_wheel_prepares_distinct_finite_profiles_without_watcher_in_pyz`; `tests/test_pyz_result_e2e.py::test_first_production_result_uses_own_instruction_then_regular_pyz_apply` |
| Z-06 | `tests/test_pyz_result_e2e.py::test_first_production_result_uses_own_instruction_then_regular_pyz_apply` |
| Z-07 | `tests/test_pyz_resources.py::test_resource_forms_materialize_identical_canonical_bytes_and_documents`; `tests/test_pyz_resources.py::test_invalid_executing_archive_has_no_directory_fallback`; `tests/test_pyz_resources.py::test_invalid_own_directory_resources_never_trigger_foreign_fallback` |
| Z-08 | `tests/test_runtime_pyz.py::test_generated_entrypoint_rejects_old_python_before_any_core_import`; `tests/test_runtime_pyz.py::test_even_rehashed_recipe_must_obey_closed_schema_inventory_and_identities`; `tests/test_pyz_resources.py::test_invalid_own_directory_resources_never_trigger_foreign_fallback` |
| Z-09 | `tests/test_pyz_bootstrap.py::test_foreign_already_imported_core_is_kept_and_conflict_is_reported`; `tests/test_pyz_bootstrap.py::test_fresh_stdlib_only_process_prepares_imports_and_uses_built_pyz_without_subprocesses` |
| Z-10 | `tests/test_runtime_packaging.py::test_standard_installation_and_three_offline_canonical_generations` |
| Z-11 | `tests/test_runtime_packaging.py::test_standard_installation_and_three_offline_canonical_generations` |
| Z-12 | `tests/test_runtime_packaging.py::test_standard_installation_and_three_offline_canonical_generations` |
| Z-13 | `tests/test_result_runtime_roundtrip.py::test_installed_self_update_pins_old_runtime_and_template_but_new_repository`; `tests/test_pyz_resources.py::test_pinned_request_survives_update_but_old_producer_rejects_same_version_replacement` |
| Z-14 | `tests/test_runtime_pyz.py::test_producer_content_and_artifact_ids_follow_distinct_finite_contracts` |
| Z-15 | `tests/test_runtime_pyz.py::test_hash_consistent_forbidden_inventory_is_rejected`; `tests/test_runtime_pyz.py::test_noncanonical_zip_is_rejected_even_when_all_payload_hashes_match`; `tests/test_runtime_pyz.py::test_raw_zip_boundary_mutations_fail`; `tests/test_runtime_pyz.py::test_false_small_directory_count_is_rejected_before_zipfile_allocation` |
| Z-16 | `tests/test_runtime_pyz.py::test_runtime_resource_and_shared_budgets_are_independent`; `tests/test_result_format3.py::test_shared_outer_inner_budget_is_exact_and_precedes_unbounded_expansion` |
| F-01 | `tests/test_captured_reference.py::test_capture_retains_actual_binding_suffix_and_exact_handoff`; `tests/test_result_format2.py::test_format2_reference_preserves_binding_and_separates_success_policy`; `tests/test_result_format3.py::test_new_reference_keeps_actual_state_and_explicit_full_runtime_facts` |
| F-02 | `tests/test_result_format2.py::test_reader_does_not_materialize_import_execute_or_write_runtime` |
| F-03 | `tests/test_result_format3.py::test_corrupt_format3_never_becomes_a_full_native_reference` |
| F-04 | `tests/test_result_format3.py::test_unavailable_runtime_preserves_known_or_unknown_producer_data`; `tests/test_result_format3.py::test_unavailable_is_not_a_permissive_repair_contract` |
| F-05 | `tests/test_result_format3.py::test_corrupt_format3_never_becomes_a_full_native_reference`; `tests/test_pyz_bootstrap.py::test_unknown_format_and_invalid_unavailable_are_errors_not_legacy_fallback` |
| F-06 | `tests/test_result_runtime_writer.py::test_all_result_routes_embed_same_producer_runtime`; `tests/test_result_runtime_publication.py::test_dirty_snapshot_and_explicit_target_survive_runtime_restrictions` |
| F-07 | `tests/test_pyz_result_resources.py::test_runtime_only_failure_keeps_snapshot_and_actual_failure_log`; `tests/test_pyz_result_resources.py::test_required_template_failure_still_preserves_actual_error_diagnostics`; `tests/test_pyz_result_resources.py::test_unexpected_provider_failures_and_cancellation_are_not_runtime_fallback` |
| F-08 | `tests/test_result_format3_consumers.py::test_real_recovery_requires_full_format3_success`; `tests/test_result_format3_consumers.py::test_actual_readers_keep_unproven_format3_and_standalone_pyz` |
| F-09 | `tests/test_result_format3_consumers.py::test_actual_readers_keep_unproven_format3_and_standalone_pyz` |
| F-10 | REVIEW: PP-05A/05B und PP-06A in Plan 1.17–1.20, anschließend tatsächlicher PP-06B-Apply; keine rückwirkende Behauptung des heutigen Writers. |
| F-11 | `tests/test_runtime_packaging.py::test_standard_installation_and_three_offline_canonical_generations`; `tests/test_runtime_pyz.py::test_normal_wheel_prepares_distinct_finite_profiles_without_watcher_in_pyz`; `tests/test_packaging_e2e.py::test_release_distributions_run_after_pipx_installation` |
| F-12 | `tests/test_state_fingerprint.py::test_empty_state_matches_the_normative_reference_vector`; `tests/test_payload_modes.py::test_existing_ordinary_mode_wins_over_zip_mode`; `tests/test_bundle_suffix_e2e.py::test_parameterless_failed_retry_and_successful_replay_remain_intact`; `tests/test_apply_repository_e2e.py::test_matching_manifest_resolves_exact_registered_repository_without_mutation` |
| F-13 | `tests/test_result3_publication_policy.py::test_new_runtime_states_keep_typed_retry_and_hash_publication_boundary`; `tests/test_result_verification.py::test_all_attempts_exhausted_preserve_safe_diagnostics`; `tests/test_result_verification.py::test_cancellation_during_retry_cleans_only_owned_temporary_file`; `tests/test_result_bundle_publication.py::test_result_digest_is_pinned_before_atomic_publication` |
| F-14 | `tests/test_pack_api.py::test_two_concurrent_requests_publish_exactly_one_complete_package`; `tests/test_pack_api.py::test_known_input_change_after_validation_fails_without_retry`; `tests/test_result_verification.py::test_real_initial_open_mismatch_is_retried_after_sync` |
| P-01 | `tests/test_pack_candidate.py::test_candidate_preserves_exact_binding_and_is_natively_valid`; `tests/test_pack_examples.py::test_documented_pack_workflows_preserve_execution_boundary` |
| P-02 | `tests/test_pack_examples.py::test_documented_pack_workflows_preserve_execution_boundary` |
| P-03 | `tests/test_pack_cli.py::test_cli_uses_public_api_once_with_exact_mode_mapping`; `tests/test_pack_examples.py::test_documented_pack_workflows_preserve_execution_boundary` |
| P-04 | `tests/test_pack_sources.py::test_pure_argument_type_errors_are_not_tool_errors`; `tests/test_pack_cli.py::test_missing_and_conflicting_arguments_are_usage_errors`; `tests/test_pack_cli.py::test_duplicate_mode_path_is_not_last_value_wins` |
| P-05 | `tests/test_pack_candidate.py::test_candidate_preserves_exact_binding_and_is_natively_valid`; `tests/test_captured_reference.py::test_internal_validation_does_not_skip_any_binding_comparison` |
| P-06 | `tests/test_captured_reference.py::test_capture_retains_actual_binding_suffix_and_exact_handoff`; `tests/test_result_format3.py::test_new_reference_keeps_actual_state_and_explicit_full_runtime_facts`; `tests/test_pack_api.py::test_invalid_reference_is_not_repaired_or_retried` |
| P-07 | `tests/test_result_format3.py::test_pack_uses_full_reader_and_never_the_private_diagnostic_fallback`; `tests/test_captured_reference.py::test_unavailable_runtime_is_still_a_complete_reference` |
| P-08 | `tests/test_pack_sources.py::test_reserved_root_inputs_are_not_silently_filtered`; `tests/test_pack_sources.py::test_missing_or_directory_entrypoint_keeps_package_error` |
| P-09 | `tests/test_pack_sources.py::test_complete_explicit_tree_preserves_bytes_and_default_modes` |
| P-10 | `tests/test_pack_sources.py::test_complete_explicit_tree_preserves_bytes_and_default_modes`; `tests/test_pack_sources.py::test_bad_entrypoint_keeps_shared_script_error` |
| P-11 | `tests/test_pack_sources.py::test_unsafe_requested_modes_keep_source_error`; `tests/test_pack_sources.py::test_modes_must_name_supplied_regular_files`; `tests/test_pack_candidate.py::test_candidate_profile_is_ordered_reproducible_and_uses_explicit_modes` |
| P-12 | `tests/test_pack_candidate.py::test_automatic_name_uses_own_uuid_utc_and_portable_display_prefix`; `tests/test_pack_candidate.py::test_legacy_name_uses_recorded_path_syntax_without_local_resolution` |
| P-13 | `tests/test_pack_candidate.py::test_explicit_name_is_preserved_but_request_metadata_still_exists`; `tests/test_pack_candidate.py::test_wrong_suffix_and_temporary_explicit_names_are_output_errors` |
| P-14 | `tests/test_captured_reference.py::test_capture_retains_actual_binding_suffix_and_exact_handoff`; `tests/test_pack_candidate.py::test_reference_rendered_instructions_are_not_the_new_template` |
| P-15 | `tests/test_captured_reference.py::test_missing_legacy_suffix_is_empty_and_does_not_invent_environment`; `tests/test_pack_candidate.py::test_reference_rendered_instructions_are_not_the_new_template` |
| P-16 | `tests/test_pack_api.py::test_pack_api_has_exact_typed_signature`; `tests/test_pack_cli.py::test_actual_cli_json_has_complete_reference_validation_and_published_hash` |
| P-17 | `tests/test_pack_api.py::test_explicit_name_and_automatic_name_have_independent_request_identities` |
| P-18 | `tests/test_pack_candidate.py::test_automatic_name_uses_own_uuid_utc_and_portable_display_prefix`; `tests/test_pack_api.py::test_explicit_name_and_automatic_name_have_independent_request_identities`; `tests/test_pack_examples.py::test_documented_pack_workflows_preserve_execution_boundary` |
| S-01 | `tests/test_pack_sources.py::test_existing_shared_path_rules_reject_unsafe_source_names`; `tests/test_pack_sources.py::test_case_collisions_are_rejected_before_file_reads` |
| S-02 | `tests/test_pack_sources.py::test_directory_swap_cannot_read_outside_root`; `tests/test_pack_sources.py::test_swap_at_open_cannot_follow_the_replacement` |
| S-03 | `tests/test_pack_sources.py::test_source_aliases_are_rejected`; `tests/test_pack_sources.py::test_special_files_are_rejected_without_blocking`; `tests/test_pack_sources.py::test_special_metadata_is_rejected_before_any_content_open` |
| S-04 | `tests/test_pack_sources.py::test_inflight_write_is_not_a_mixed_success`; `tests/test_pack_sources.py::test_final_inventory_revalidation_detects_known_mutation`; `tests/test_pack_api.py::test_known_input_change_after_validation_fails_without_retry` |
| S-05 | `tests/test_pack_sources.py::test_real_thousand_entry_boundary_reserves_all_three_generated_files`; `tests/test_pack_sources.py::test_real_ten_thousand_node_boundary_counts_empty_directories`; `tests/test_pack_candidate.py::test_generated_contents_and_compressed_output_share_budgets` |
| S-06 | `tests/test_pack_sources.py::test_output_cannot_alias_inputs_or_replace_files`; `tests/test_pack_api.py::test_destination_created_at_last_instant_is_never_overwritten` |
| S-07 | `tests/test_pack_api.py::test_two_concurrent_requests_publish_exactly_one_complete_package` |
| S-08 | `tests/test_pack_api.py::test_reservation_stream_failure_cleans_owned_file_and_handle`; `tests/test_pack_api.py::test_required_sync_and_unsupported_publication_are_output_failures` |
| S-09 | `tests/test_pack_api.py::test_mandatory_written_archive_validation_cannot_be_skipped_or_reclassified`; `tests/test_pack_api.py::test_valid_but_semantically_substituted_written_package_is_not_released` |
| S-10 | `tests/test_pack_api.py::test_output_mutation_after_validation_never_publishes_or_deletes_foreign_file` |
| S-11 | `tests/test_pack_api.py::test_interrupt_before_publication_has_130_and_no_partial_final`; `tests/test_pack_api.py::test_identity_loss_at_publication_keeps_source_error_and_foreign_file` |
| S-12 | `tests/test_pack_api.py::test_postpublication_cleanup_retains_complete_success_without_observer`; `tests/test_pack_cli.py::test_cleanup_warnings_are_full_json_success_without_observer` |
| S-13 | `tests/test_pack_exchange_e2e.py::test_automatic_exchange_consumer_ignores_partial_then_applies_complete_pack`; `tests/test_pack_api.py::test_watcher_can_take_final_file_before_api_returns_success`; `tests/test_pack_api.py::test_pack_does_not_run_tools_or_change_process_state` |
| S-14 | `tests/test_pack_api.py::test_pack_does_not_run_tools_or_change_process_state`; `tests/test_captured_reference.py::test_capture_and_internal_validation_are_read_only_without_git_registry_or_network` |
| S-15 | `tests/test_pack_api.py::test_shared_input_errors_keep_categories_before_any_output`; `tests/test_pack_cli.py::test_error_envelope_preserves_existing_failure_categories`; `tests/test_captured_reference.py::test_internal_validation_uses_actual_package_bytes_and_original_error_categories` |
| S-16 | `tests/test_pack_cli.py::test_output_failure_after_publication_never_rebuilds_or_emits_second_envelope` |
| S-17 | `tests/test_captured_reference.py::test_unstable_capture_is_one_source_error_without_retry`; `tests/test_pack_sources.py::test_detected_instability_is_not_retried`; `tests/test_pack_api.py::test_known_input_change_after_validation_fails_without_retry` |
| S-18 | `tests/test_pack_api.py::test_postpublication_cleanup_retains_complete_success_without_observer`; `tests/test_pack_api.py::test_watcher_can_take_final_file_before_api_returns_success` |
| E-01 | `tests/test_pyz_result_e2e.py::test_first_production_result_uses_own_instruction_then_regular_pyz_apply` |
| E-02 | `tests/test_pyz_result_e2e.py::test_first_production_result_uses_own_instruction_then_regular_pyz_apply` |
| E-03 | `tests/test_pack_cli.py::test_packed_payload_uses_regular_apply_and_rechecks_later_repository_state` |
| E-04 | `tests/test_pack_examples.py::test_documented_pack_workflows_preserve_execution_boundary` |
| E-05 | `tests/test_pyz_resources.py::test_real_built_producer_uses_only_own_resources_for_pack_from_readonly_runtime`; `tests/test_pyz_result_e2e.py::test_first_production_result_uses_own_instruction_then_regular_pyz_apply` |
| E-06 | `tests/test_pyz_bootstrap.py::test_fresh_stdlib_only_process_prepares_imports_and_uses_built_pyz_without_subprocesses`; `tests/test_pyz_bootstrap.py::test_old_python_refuses_execution_without_a_preparation_directory`; `tests/test_pyz_bootstrap.py::test_foreign_already_imported_core_is_kept_and_conflict_is_reported` |
| E-07 | `tests/test_pack_examples.py::test_documented_pack_workflows_preserve_execution_boundary` |
| E-08 | REVIEW: planning/pyz-pack/documentation-review.md; fachlicher Review, bewusst kein Prosa-/Layouttest. |
| E-09 | REVIEW: planning/pyz-pack/documentation-review.md; fachlicher Review, bewusst kein Prosa-/Layouttest. |
| E-10 | `tests/test_pyz_result_e2e.py::test_first_production_result_uses_own_instruction_then_regular_pyz_apply` |

## Lanes und externe Grenzen

Core umfasst unmarkierte Daten-/Sicherheitsfälle. E2E/acceptance, platform und
packaging behalten ihre vorhandenen Marker. Die vollständige lokale Suite
umfasst alle vier Gruppen parallel. Der gesonderte Windows-PowerShell-7-Selektor
enthält zusätzlich die neuen Pack-/PYZ-Apply- und Roundtripmodule; die normalen
Windows- und Linux-Jobs behalten ihre bisherigen Lanes. Neue relevante native
Skripte wählen den vorgegebenen PowerShell-Engine ausdrücklich. Kein neuer
Workflow, Push-/PR-/Zeitplantrigger oder automatischer Dispatch wird eingeführt.

Linux-Fault-Injection beweist keine Windows-Handles, Reparse-Punkte, ACLs oder
Linux-zu-Windows-CIFS-Veröffentlichung. Echte Python-3.12-/Windows-/CIFS-Nachweise
bleiben PP-08B zugeordnet. Native Einschränkungen und Skips sind offenzulegen.
Legacy-Format-2-Tests verwenden die vollständige eingefrorene Distribution mit
festem Hash; keine Mischung historischer und aktueller Module.

## Messung

Die Roundtriptests erfassen kanonische PYZ-Größe, komprimierten Resultzuwachs und
Python-Spitzenspeicher pro Generation. Der separate Messfall erfasst drei reale
Prozessstarts und Pack-Läufe mit 1 MiB Eingabe, Interpreter/Plattform, Runtime-
Hash und Eingabegröße. Er schreibt strukturierte Messwerte im privaten Test-
Arbeitsordner, ohne enge Zeitlimits. Messwerte beschreiben diesen Testrechner und
seine Parallelbelastung; sie sind keine allgemeine Leistungszusage.
