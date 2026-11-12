# Integration mit PatchHarbor 2.0

Version 2 verwendet Task-Bundles (Format 2), Execute-Berichte (JSON-Version 2)
und Result-Bundles (Format 4). Ein bisheriges Result wird nicht durch Umbenennen
zu einem gültigen neuen Result. Die Installation oder der Import aktualisiert
keine andere Anwendung, keinen laufenden Watcher und keine gespeicherten Pins.

| Bisheriger Aufruf | Neuer Aufruf |
| --- | --- |
| `api.pack_patch(...)` | `api.pack_task(...)` |
| `api.inspect_patch(...)` / `api.validate_patch(...)` | `api.inspect_task(...)` / `api.validate_task(...)` |
| `api.apply(...)` | `api.execute(...)` |
| `api.apply_next(...)` / `api.apply_guarded(...)` | `api.execute_next(...)` / `api.execute_guarded(...)` |
| Python-Pfadparameter `patch=` | `task=` |
| CLI `patchharbor apply` | `patchharbor execute`; `apply` ist nur ein veralteter CLI-Alias |

Nach einer bewusst vorgenommenen Installation erzeugt `patchharbor bundle REPO`
ein frisches Result 4 direkt aus dem tatsächlichen Repository. Dafür ist kein
altes Result nötig. Die üblichen Registrierungs-, Exchange- und Sperrprüfungen
gelten weiterhin. Ein schmutziger Stand wird als solcher erfasst.

Der Verbraucher prüft die vollständige SHA-256 dieses Results aus seiner
vertrauenswürdigen Übergabe. Der im Result enthaltene ausführbare Bootstrap
prüft zunächst den Runtime-Deskriptor und bereitet die zugehörige Core-PYZ lokal
vor. Diese Vorprüfung ersetzt nicht die vollständige native Result-Prüfung beim
Packen. `api.pack_task(..., reference_bundle=result)` und
`api.validate_task(..., reference_bundle=result)` binden an genau dieses Result.
Die Core-PYZ benötigt keinen Watcher, keine Paketinstallation und keinen Download.

Eine erfolgreiche Diagnoseausführung muss keinen Commit erzeugen. Das nächste
Task-Bundle bindet an das tatsächlich zurückgelieferte Result, auch nach einem
fehlgeschlagenen Entrypoint mit erhaltenen Änderungen. Primärer Prozessausgang
und Result-Publikation sind getrennte Ergebnisse. Ein fehlgeschlagenes oder
unvollständiges Result ist kein bestätigter Übergabestand.

Integrationen müssen ihre Aufrufer, erwarteten Format-/Capability-Versionen und
gepinnten vollständigen Hashes bewusst umstellen. Laufende Aufträge behalten
ihre zu Beginn erfasste Runtime und Vorlage. Dieser Leitfaden und die Tests
ändern weder SpecRoad/Control noch globale Installationen oder Dienste.

## Bewusster Umstieg einer Installation

Zuerst laufende Aufträge auslaufen lassen und den alten Watcher vor dem Austausch
seiner Installation stoppen. Quellen, Wheel und Core-PYZ sind unterschiedliche
Installationswege; eine neue PYZ ersetzt keinen laufenden Watcher. Danach Version,
Capability-Verträge, die tatsächlich gestartete ausführbare Datei und die
Dienstargumente prüfen. Erst dann den gewünschten Event- oder Pollingbetrieb
wieder aufnehmen. Keine alte Runtime oder Vorlage während eines laufenden
Auftrags austauschen.

`patchharbor watcher poll` scannt standardmäßig alle vier Sekunden;
`patchharbor watcher poll --interval 2.5` wählt ausdrücklich das Intervall.
Das benötigt keine inotify-Ereignisse und eignet sich für entsprechende
CIFS-Mounts. Publikations- und Sperrprüfungen bleiben erforderlich. Eine
Konfigurationsänderung alleine beweist keine neue Dienstlaufzeit.

Result-/Task-Suffixe gehören zur Repositorykonfiguration. Beispielsweise kann
`patchharbor configure bundle-suffix .txt` eine zusätzliche Dateiendung erzeugen;
zum Packen, Prüfen und Execute immer den tatsächlich zurückgegebenen Pfad
verwenden. Suffixe ersetzen weder ZIP-Inhalt noch Hash- oder Formatprüfung.

Das ausführbare [Vorbereitungsbeispiel](examples/prepare_task.py) prüft ein Result
mit einer extern vertrauenswürdig erhaltenen vollständigen SHA-256 und erzeugt
eine native Task-ZIP in einem privaten, nicht überwachten Ausgabeverzeichnis.
Es führt keine Payload aus. Der Benutzer überträgt anschließend genau diese
geprüften Bytes oder startet ausdrücklich `patchharbor execute TASKPFAD`.
Die vorhandenen installierten CLI-/PYZ-Beispiele und Pollingtests decken die
Ausführungswege ab; die veralteten CLI-Namen akzeptieren keine alten Formate.

Alte Python-Aufrufer einschließlich `api.run` müssen geändert werden. Der
eigenständige Skriptweg heißt `api.run_scripts` mit `ScriptBundle` und bleibt
deprecated. Weder dieser Weg noch der CLI-Alias `apply` ist eine Migration für
alte Patch-Bundles. Alte Results bleiben unveränderte historische Belege.
