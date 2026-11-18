# State Bundle – WRC-Weiterentwicklung auf dev

**Plan-ID:** PH-STATE · **Bundle:** 123 · **Stand:** 18. November 2026.
**Basis:** veröffentlichtes 2.0.1, Commit `90452415be3d0e522730ad22f07c0be28453734d`.
**Auftrag:** sechs verbleibende WRC-Commits einschließlich Größen-Override; drei Commits sind bereits abgeschlossen.
Apply ist ausdrücklich beauftragt. Keine Veröffentlichung, Versionsanhebung, Tags oder Pushes.
Dieser Quellplan belegt Vorbereitung; tatsächliche Commits und Tests belegen erst
die späteren Execute-Berichte. In Development ausschließlich statische Analyse.

## Vertrag

`patchharbor bundle` bleibt der Befehl. Er erzeugt ein **State Bundle** für den
ersten Einstieg oder die erneute Übernahme des aktuellen Repository-Arbeitsstands.
`execute` erzeugt ein **Result Bundle**, auch nach Fehlern und bei Dry-Run.
State und Result sind passive Referenzen für `pack` und `validate`; nur ein
Task Bundle ist ein ausführbarer Auftrag. Ein State ist kein Execute-Nachweis.

Aktuelle Ergänzung zu [CURRENT_PACKAGE_CONTRACT.md](../../spec/CURRENT_PACKAGE_CONTRACT.md):
beide Referenzarten verwenden Snapshotformat 5, eigene State-/Result-Marker und
exakte Produktversionen. Marker, Operation und Begleittyp müssen zusammenpassen.
Die gemeinsame Snapshotverarbeitung wird nicht dupliziert. Es gibt keine
Migration alter Pakete oder API-Kompatibilitätsschicht. CLI-Aliase bleiben bestehen.
Historische Release-Dokumente beschreiben weiterhin die damalige Version.

## Sechs aufeinanderfolgende Quellstände

| Schritt | WRC | Inhalt |
| --- | --- | --- |
| STATE-01.W | Work | State/Result in Erzeugung, Namen, Begleitdaten, Lesern, Runtime und Klassifikation unterscheiden. |
| STATE-01.R | Right | Widersprüche und falsche Execute-Belege abweisen; beide Referenzarten samt Fehler-/Dry-Run-Zuständen absichern. |
| STATE-01.C | Clean | Gemeinsame Referenzleser und Snapshot-API neutral benennen, verteilte Typentscheidungen vereinheitlichen. |
| STATE-02.W | Work | CLI, JSON, Hilfe, Fortschritt und Monitor zeigen den passenden Bundle-Typ. |
| STATE-02.R | Right | Anleitung, Spezifikation und Chat-Vertrag an den tatsächlichen Start-/Fortsetzungsablauf binden. |
| STATE-02.C | Clean | Aktuelle Beispiele, Kommentare und Terminologie abschließend bereinigen; historische Nachweise erhalten. |

Jeder Stand muss für sich funktionieren. Right-Commits härten die Fähigkeit;
sie legitimieren keine absichtlich unvollständigen oder unsicheren Work-Stände.
Apply führt vor **jedem** tatsächlichen Commit `tools/run_tests.py --suite all
--workers auto` aus, ohne zusätzliche Worker-Begrenzung. Ein Fehler stoppt die
Folge vor dem Commit; Tests, Repository-Bindung und exakte Bäume werden geprüft.
Ein erneut erzeugtes Bundle wird vor einer späteren Ausführung an den dann
tatsächlichen Zustand gebunden. Ein Draft reserviert oder konsumiert keine Referenz.

## Quellfortschritt

Vorbereiteter Stand: **STATE-02.W**. Apply- und Testnachweis: **ausstehend**.

## Reparatur nach Execute 121

Bundle 121 stoppte im ersten Volltest vor dem ersten Commit: 3.966 bestanden,
vier fehlgeschlagen, 16 übersprungen. Basis dieser Fortsetzung ist sein
verifiziertes Result `853a2aee-483c-4add-8c0b-6a388cb89de8` mit dem
uncommitteten Stand STATE-01.W; der HEAD bleibt `90452415be3d0e522730ad22f07c0be28453734d`.
Die Reparatur unterscheidet State-/Result-Erwartungen in Referenztests und
ergänzt die explizite Paket-Dateiliste um `reference_kind.py`, ab FORCE-01.W
auch um `bundle_limits.py`. Alle nachfolgenden Quellstände enthalten dieselben
Korrekturen. Der erste Commit umfasst den bereits angewandten Work-Stand samt
Reparatur; er entsteht erst nach erfolgreichem vollständigem Apply-Gate.
Dieses Dokument behauptet keinen bereits bestandenen Reparaturlauf.

## Fortsetzung nach Execute 122

STATE-01.W, STATE-01.R und STATE-01.C sind nach jeweils erfolgreichem
vollständigem Apply-Testlauf committed: `66009da`, `8981f4f`, `53382b1`.
Der vierte Schritt STATE-02.W stoppte vor dem Commit: 3.999 bestanden,
ein Test fehlgeschlagen, 16 übersprungen. Seine JSON-Fehlerfall-Erwartung
wird auf die bereits eingeführte Bundle-Ausgabeversion 2 berichtigt.
Alle sechs verbleibenden Quellstände enthalten diese Korrektur und
behalten die Reparaturen aus Bundle 122 bei. Ausgangspunkt ist dessen
verifiziertes Result `e9ccb080-b638-4419-8abd-44cecff6772b`, einschließlich
des uncommitteten STATE-02.W-Stands, auf HEAD
`53382b1fbdd91c16036c41cbb50207411063e3a6`.
Bundle 123 setzt dort fort; die drei vorhandenen Commits bleiben erhalten.
Vor jedem weiteren Commit läuft erneut die vollständige Suite in Apply
mit `--workers auto`. Für Bundle 123 liegt hier noch kein Testnachweis vor.
