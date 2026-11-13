# Task / Execute / Result in PatchHarbor 2.0

Dieser Vertrag beschreibt den aktuellen PatchHarbor-Quellstand.
Verbindlich ist außerdem [genau eine Produktversion, keine Migration](../spec/CURRENT_PACKAGE_CONTRACT.md). Er ersetzt frühere Bundle-,
API- und Ausführungsverträge. Die Versionsangabe beweist keine Veröffentlichung. Eine
Produktversion ist keine Formatnummer. Alte Bundle-Formate werden abgelehnt;
es gibt keinen Konverter und keine alten Python-API-Aliase.

| Grenze | Aktueller Vertrag |
| --- | --- |
| Task | `task.json`, Marker `patch-harbor-task-bundle`, Format 3 |
| Result | `manifest.json`, Marker `patch-harbor-result-bundle`, Format 5 |
| Environment | Marker `patch-harbor-environment`, Format 3 mit separatem Helfer, `bundle_type: Task` bzw. `Result`, `filename_schemas.Task` |
| Runtime-Metadaten | Format 3, `task_formats: [3]`, `result_formats: [5]`, Operationen `inspect_task`, `validate_task`, `pack_task` |
| Execute JSON | `output_version: 2`, `command: execute` |
| Pack / Inspect / Validate JSON | `output_version: 4` |
| Integration / Snapshot / Guarded Execute | Je Vertrag 2; `guarded_execute_contract_version` |
| Replay-Ablage | Format 5 mit `task_bundle` und `execute_status`; ältere Schemata werden unverändert abgelehnt; keine Migration |
| Safe Reference | Weiterhin Vertrag 1; unveränderte Exportsemantik |
| Monitor | Envelope 2, Live-Daten 3; ältere Beobachtungen sind keine aktuellen Zustände |

Task enthält genau die acht Felder `marker`, `format_version`, `patchharbor_version`, `repo_id`,
`base_commit`, `state_fingerprint`, `fingerprint_algorithm`, `entrypoint`.
Vollständige Kennungen sind Maschineninput. Ein Task mit zusätzlichem altem
`patch.json` oder Result-`manifest.json` wird als gemischtes Paket abgelehnt.
Ein Umbenennen der ZIP ändert weder Format noch Bindung.

`api.pack_task`, `api.inspect_task` und `api.validate_task` liefern unveränderliche
Task-Facts. `api.execute`, `execute_guarded`, `execute_next` und
`execute_readiness` verwenden denselben bestehenden Ausführungskern. Der erste
Pfadparameter heißt `task`. `api.dry_run` delegiert an diesen Kern, führt aber
keinen Entrypoint aus und konsumiert keinen Replay-Versuch. Der neutrale
`RunReport` bleibt bestehen; seine Operation heißt `RunOperation.EXECUTE`,
seine Projektion `execute_json_envelope()`.

`patchharbor execute` ist der CLI-Hauptbefehl. `patchharbor apply` ist ein
veralteter CLI-Alias mit einem Hinweis auf stderr und identischer Verarbeitung,
identischen Sicherheitsprüfungen und demselben JSON-Vertrag. Er akzeptiert
keine alten Pakete. Python besitzt keinen entsprechenden Alias.

Result verbindet eine bekannte Task-Ausführung über `task_sha256` mit den
vollständigen geprüften Eingabebytes. `logs/run.json` beschreibt `operation:
execute`, den tatsächlichen Entrypoint-Ausgang und unabhängig davon die
Result-Publikation. Ein erfolgreicher Entrypoint behauptet keinen Commit.
`completed_commit` bleibt leer, solange ein tatsächlicher neuer, sauberer
Commit nicht über den vorhandenen Nachweis belegt ist. Teilfortschritt bei
Fehler, Timeout oder Abbruch bleibt sichtbar; es gibt keinen globalen Rollback.

Automatische Namen enthalten `_Task_Bundle_` beziehungsweise `_Result_Bundle_`.
Explizite zulässige Ausgabedateinamen bleiben erhalten. Suffix-, No-clobber-,
Pfad-, Hash-, ZIP-Budget-, Registry-, Replay- und Lockprüfungen gelten weiter.
Die physischen Lockidentitäten werden durch neue Python-Typnamen nicht verändert.

`ScriptBundle` und `api.run_scripts` sind der eigenständige, veraltete Skriptweg.
`fs run` bleibt ebenfalls deprecated. Beide sind keine alternativen Task-Leser.
Git-Deltas, `git apply`, `PatchHarbor`, `PATCHHARBOR_META` und `# PATCHHARBOR`
behalten ihre fachlich richtigen Namen. Die PYZ-Rezeptversion und das Core-Profil
ohne Watcher bleiben unverändert.

Die Begleitressourcen sind in [Chat-Handoff](chat-handoff.md) festgelegt.
Neue Resultate tragen `tools/pyz_bootstrap.py` im Root; Tasks ausschließlich unter
`PATCHHARBOR_META/tools/pyz_bootstrap.py`. Begleitdatenformat 3 hat einen Pflicht-
Deskriptor `bootstrap: {path, size, sha256}`. Hashprüfung authentifiziert keinen
Absender. Frühere Begleitdatenpaare werden abgelehnt. Task 3 und Result 5
tragen die exakte Produktversion; Replay-Schema 5 bleibt unverändert.
